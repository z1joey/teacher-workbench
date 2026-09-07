<script setup>
// 个人中心：资料、我的班级、教学足迹。退出登录需要确认，避免误触。
import { computed, onMounted, ref } from "vue"
import { useRouter } from "vue-router"
import Icon from "../components/Icon.vue"
import PageHeader from "../components/PageHeader.vue"
import AsyncState from "../components/AsyncState.vue"
import FormField from "../components/FormField.vue"
import api, { setToken } from "../api"
import { clearMe, me } from "../auth"
import { ask } from "../confirm"
import { notify } from "../feedback"
import { clearAll } from "../feedback"
import { friendlyError, genderLabel, t } from "../strings"

const router = useRouter()

const profile = ref(null)
const error = ref("")
const loading = ref(true)
const editing = ref(false)
const saving = ref(false)
const editForm = ref({ name: "", email: "" })
const errors = ref({})
const semesterForm = ref([])
const semesterErrors = ref({})
const savingSemesters = ref(false)

function newSemesterRow() {
  return {
    id: crypto.randomUUID(),
    name: "",
    start_date: "",
    end_date: "",
  }
}

function syncSemesterForm(rows) {
  semesterForm.value = (rows || []).map((row) => ({ ...row }))
}

async function load() {
  loading.value = true
  error.value = ""
  try {
    profile.value = await api.get("/profile")
    syncSemesterForm(profile.value.semesters)
  } catch (e) {
    error.value = friendlyError(e)
  } finally {
    loading.value = false
  }
}
onMounted(load)

function startEdit() {
  const user = profile.value.user
  editForm.value = { name: user.name || "", email: user.email || "" }
  errors.value = {}
  editing.value = true
}
function cancelEdit() {
  editing.value = false
  errors.value = {}
}

function validate() {
  const e = {}
  if (!editForm.value.name.trim()) e.name = t("login.name") + "不能为空"
  errors.value = e
  return !Object.keys(e).length
}

async function saveProfile() {
  if (!validate()) return
  saving.value = true
  error.value = ""
  try {
    const updated = await api.patch("/profile", {
      name: editForm.value.name.trim(),
      email: editForm.value.email.trim() || null,
    })
    profile.value.user = updated
    if (me.value) me.value = { ...me.value, ...updated } // keep the sidebar name in sync
    editing.value = false
    notify({ tone: "ok", title: t("profile.saved"), timeout: 2400 })
  } catch (e) {
    error.value = friendlyError(e)
  } finally {
    saving.value = false
  }
}

function addSemester() {
  semesterForm.value = [...semesterForm.value, newSemesterRow()]
}

function removeSemester(id) {
  semesterForm.value = semesterForm.value.filter((row) => row.id !== id)
}

function validateSemesters() {
  const e = {}
  semesterForm.value.forEach((row, i) => {
    if (!row.name.trim()) e[`name-${i}`] = t("profile.semesterNameRequired")
    if (!row.start_date || !row.end_date) e[`dates-${i}`] = t("profile.semesterDatesRequired")
    else if (row.end_date < row.start_date) e[`dates-${i}`] = t("profile.semesterEndInvalid")
  })
  semesterErrors.value = e
  return !Object.keys(e).length
}

async function saveSemesters() {
  if (!validateSemesters()) return
  savingSemesters.value = true
  error.value = ""
  try {
    const payload = semesterForm.value.map((row) => ({
      id: row.id,
      name: row.name.trim(),
      start_date: row.start_date,
      end_date: row.end_date,
    }))
    const updated = await api.patch("/profile/semesters", { semesters: payload })
    profile.value.semesters = updated.semesters
    syncSemesterForm(updated.semesters)
    notify({ tone: "ok", title: t("profile.semestersSaved"), timeout: 2400 })
  } catch (e) {
    error.value = friendlyError(e)
  } finally {
    savingSemesters.value = false
  }
}

async function logout() {
  const ok = await ask({
    title: "退出登录？",
    message: "退出后需要重新输入手机号和密码。",
    confirmLabel: t("auth.logout"),
    tone: "warn",
  })
  if (!ok) return
  try {
    await api.post("/auth/logout")
  } catch {
    // token already invalid — clearing locally is enough
  }
  setToken(null)
  clearMe()
  clearAll()
  router.push("/login")
}

const activity = computed(() => {
  if (!profile.value) return []
  const s = profile.value.stats
  return [
    { label: t("profile.recordsLogged"), value: s.interactions, icon: "checklist" },
    { label: t("profile.resultsEntered"), value: s.results_entered, icon: "clipboard" },
    { label: t("profile.notesAdded"), value: s.notes_added, icon: "note" },
  ]
})
</script>

<template>
  <PageHeader :title="t('profile.title')" :subtitle="t('profile.subtitle')">
    <template #actions>
      <button class="btn btn--danger" @click="logout">
        <Icon name="logout" :size="15" /> {{ t("auth.logout") }}
      </button>
    </template>
  </PageHeader>

  <AsyncState :loading="loading" :error="error" :rows="4" @retry="load">
    <div v-if="profile" class="split">
      <div>
        <!-- 资料 -->
        <div class="card">
          <div class="card__head">
            <h2 class="card__title"><Icon name="user" :size="16" /> 基本资料</h2>
            <button v-if="!editing" class="btn btn--sm" @click="startEdit">
              <Icon name="pencil" :size="13" /> {{ t("profile.editInfo") }}
            </button>
          </div>

          <div v-if="!editing" class="card__body">
            <div class="row" style="gap: 14px; align-items: flex-start">
              <span class="avatar avatar--lg">{{ profile.user.name.charAt(0) }}</span>
              <div class="grow">
                <p style="font-size: 17px; font-weight: 600">{{ profile.user.name }}</p>
                <div class="row-wrap" style="margin-top: 6px">
                  <span class="pill pill--outline">{{ t("profile.loginPhone") }}：{{ profile.user.phone }}</span>
                  <span v-if="profile.user.email" class="pill pill--outline">
                    {{ t("profile.email") }}：{{ profile.user.email }}
                  </span>
                </div>
              </div>
            </div>
          </div>

          <form v-else class="card__body" @submit.prevent="saveProfile">
            <div class="form-grid">
              <FormField :label="t('login.name')" required :error="errors.name || ''">
                <input v-model="editForm.name" class="input" type="text" :aria-invalid="!!errors.name" />
              </FormField>
              <FormField :label="t('profile.email')" optional>
                <input v-model="editForm.email" class="input" type="email" />
              </FormField>
            </div>
            <div class="form-actions">
              <button type="submit" class="btn btn--primary" :disabled="saving">
                <span v-if="saving" class="spinner" />
                {{ saving ? t("action.saving") : t("action.save") }}
              </button>
              <button type="button" class="btn btn--ghost" @click="cancelEdit">
                {{ t("action.cancel") }}
              </button>
            </div>
          </form>
        </div>

        <!-- 学期设置 -->
        <div class="card">
          <div class="card__head">
            <div>
              <h2 class="card__title"><Icon name="calendar" :size="16" /> {{ t("profile.semesters") }}</h2>
              <p class="card__desc">{{ t("profile.semestersHint") }}</p>
            </div>
          </div>
          <form class="card__body" @submit.prevent="saveSemesters">
            <p v-if="!semesterForm.length" class="state__desc" style="margin: 0 0 12px">
              {{ t("profile.semestersEmpty") }}
            </p>
            <div v-for="(row, i) in semesterForm" :key="row.id" class="semester-row">
              <FormField
                :label="t('profile.semesterName')"
                required
                :error="semesterErrors[`name-${i}`] || ''"
              >
                <input v-model="row.name" class="input" type="text" maxlength="100" />
              </FormField>
              <FormField
                :label="t('profile.semesterStart')"
                required
                :error="semesterErrors[`dates-${i}`] || ''"
              >
                <input v-model="row.start_date" class="input" type="date" />
              </FormField>
              <FormField
                :label="t('profile.semesterEnd')"
                required
                :error="semesterErrors[`dates-${i}`] ? ' ' : ''"
              >
                <input v-model="row.end_date" class="input" type="date" />
              </FormField>
              <button
                type="button"
                class="btn btn--ghost btn--sm semester-row__remove"
                :aria-label="t('action.delete')"
                @click="removeSemester(row.id)"
              >
                <Icon name="trash" :size="14" />
              </button>
            </div>
            <div class="form-actions">
              <button type="button" class="btn" @click="addSemester">
                <Icon name="plus" :size="14" /> {{ t("profile.addSemester") }}
              </button>
              <button type="submit" class="btn btn--primary" :disabled="savingSemesters">
                <span v-if="savingSemesters" class="spinner" />
                {{ savingSemesters ? t("action.saving") : t("action.save") }}
              </button>
            </div>
          </form>
        </div>

        <!-- 我的班级 -->
        <div class="card">
          <div class="card__head">
            <h2 class="card__title"><Icon name="building" :size="16" /> {{ t("profile.myClasses") }}</h2>
            <span class="pill pill--muted pill--count">{{ profile.classes.length }}</span>
          </div>
          <div class="card__body">
            <p v-if="!profile.classes.length" class="state__desc" style="text-align: center; padding: 12px 0">
              {{ t("profile.noClasses") }}
            </p>
            <div v-for="c in profile.classes" :key="c.id" class="stack" style="gap: 8px; margin-bottom: 20px">
              <div class="row-wrap">
                <router-link :to="`/classes/${c.id}`" class="pill">{{ c.name }}</router-link>
                <span class="stat__sub">
                  {{ c.academic_year }} · {{ t("profile.studentsCount", { n: c.students.length }) }}
                </span>
              </div>
              <div class="chips">
                <router-link
                  v-for="s in c.students"
                  :key="s.id"
                  :to="`/students/${s.id}`"
                  class="chip"
                >
                  {{ s.name }}
                  <span class="muted" style="font-size: 12px">{{ genderLabel(s.gender) }}</span>
                </router-link>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 教学足迹 -->
      <div class="card">
        <div class="card__head">
          <h2 class="card__title"><Icon name="chart" :size="16" /> {{ t("profile.activity") }}</h2>
        </div>
        <div class="card__body">
          <div v-for="a in activity" :key="a.label" class="stat stat--plain">
            <div class="stat__label">{{ a.label }}</div>
            <div class="stat__value tnum">{{ a.value }}</div>
          </div>
        </div>
      </div>
    </div>
  </AsyncState>
</template>
