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
import { clearSearch } from "../search"
import { friendlyError, genderLabel, t } from "../strings"

const router = useRouter()

const profile = ref(null)
const error = ref("")
const loading = ref(true)
const editing = ref(false)
const saving = ref(false)
const editForm = ref({ name: "", phone: "" })
const errors = ref({})
const settingsSaving = ref(false)

function normalizePhone(phone) {
  return phone.replace(/[\s-]/g, "")
}

async function saveSettings() {
  if (!profile.value) return
  settingsSaving.value = true
  error.value = ""
  try {
    const updated = await api.patch("/profile", {
      name: profile.value.user.name,
      phone: profile.value.user.phone || null,
      auto_tags: profile.value.settings.auto_tags,
      calendar_birthdays: profile.value.settings.calendar_birthdays,
    })
    profile.value.settings = updated.settings
    profile.value.user = { ...profile.value.user, ...updated }
    if (me.value) {
      me.value = {
        ...me.value,
        name: updated.name,
        display_name: updated.display_name,
      }
    }
    notify({ tone: "ok", title: t("profile.settingsSaved"), timeout: 2400 })
  } catch (e) {
    error.value = friendlyError(e)
  } finally {
    settingsSaving.value = false
  }
}

async function load() {
  loading.value = true
  error.value = ""
  try {
    profile.value = await api.get("/profile")
  } catch (e) {
    profile.value = null
    error.value = friendlyError(e)
  } finally {
    loading.value = false
  }
}
onMounted(load)

function startEdit() {
  const user = profile.value.user
  editForm.value = { name: user.name || "", phone: user.phone || "" }
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
  const phone = normalizePhone(editForm.value.phone.trim())
  if (editForm.value.phone.trim() && !/^\d{6,15}$/.test(phone)) {
    e.phone = t("profile.phoneInvalid")
  }
  errors.value = e
  return !Object.keys(e).length
}

async function saveProfile() {
  if (!validate()) return
  saving.value = true
  error.value = ""
  try {
    const phoneRaw = editForm.value.phone.trim()
    const updated = await api.patch("/profile", {
      name: editForm.value.name.trim(),
      phone: phoneRaw ? normalizePhone(phoneRaw) : null,
    })
    profile.value.user = { ...profile.value.user, ...updated }
    if (me.value) {
      me.value = {
        ...me.value,
        name: updated.name,
        display_name: updated.display_name,
      }
    }
    editing.value = false
    notify({ tone: "ok", title: t("profile.saved"), timeout: 2400 })
  } catch (e) {
    error.value = friendlyError(e)
  } finally {
    saving.value = false
  }
}

async function logout() {
  const ok = await ask({
    title: "退出登录？",
    message: "退出后需要重新输入邮箱和密码。",
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
  clearSearch()
  clearAll()
  await router.replace("/login")
}

const activity = computed(() => {
  if (!profile.value) return []
  const s = profile.value.stats
  return [
    { label: t("profile.recordsLogged"), value: s.interactions, icon: "checklist" },
    { label: t("profile.resultsEntered"), value: s.results_entered, icon: "clipboard" },
    { label: t("profile.commentsWritten"), value: s.comments_written, icon: "note" },
  ]
})
</script>

<template>
  <PageHeader :title="t('profile.title')" :subtitle="t('profile.subtitle')" />

  <AsyncState
    :loading="loading"
    :error="error"
    :empty="!loading && !error && !profile"
    empty-title="个人资料没能加载"
    empty-desc="请检查网络连接后重试。"
    :rows="4"
    @retry="load"
  >
    <div class="split">
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
                  <span class="pill pill--outline">
                    {{ t("profile.loginEmail") }}：{{ profile.user.email }}
                  </span>
                  <span class="pill pill--outline">
                    {{ t("profile.phone") }}：{{ profile.user.phone || t("profile.phoneEmpty") }}
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
              <FormField
                :label="t('profile.phone')"
                optional
                :error="errors.phone || ''"
                :hint="t('profile.phoneHint')"
              >
                <input
                  v-model="editForm.phone"
                  class="input"
                  type="tel"
                  inputmode="numeric"
                  :aria-invalid="!!errors.phone"
                />
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

        <!-- 偏好设置 -->
        <div class="card">
          <div class="card__head">
            <h2 class="card__title"><Icon name="sliders" :size="16" /> {{ t("profile.settings") }}</h2>
          </div>
          <div class="card__body profile-panel">
            <div class="profile-section">
              <label class="check">
                <input
                  v-model="profile.settings.auto_tags"
                  type="checkbox"
                  :disabled="settingsSaving"
                  @change="saveSettings"
                />
                <span>{{ t("profile.autoTags") }}</span>
              </label>
              <p class="field__hint" style="margin-top: 8px">{{ t("profile.autoTagsHint") }}</p>
            </div>
            <div class="profile-section">
              <label class="check">
                <input
                  v-model="profile.settings.calendar_birthdays"
                  type="checkbox"
                  :disabled="settingsSaving"
                  @change="saveSettings"
                />
                <span>{{ t("profile.calendarBirthdays") }}</span>
              </label>
              <p class="field__hint" style="margin-top: 8px">{{ t("profile.calendarBirthdaysHint") }}</p>
            </div>
          </div>
        </div>

        <!-- 我的班级 -->
        <div class="card">
          <div class="card__head">
            <h2 class="card__title"><Icon name="building" :size="16" /> {{ t("profile.myClasses") }}</h2>
            <span class="pill pill--muted pill--count">{{ profile.classes.length }}</span>
          </div>
          <div class="card__body">
            <div v-if="!profile.classes.length" class="state state--in-card">
              <p class="state__desc">{{ t("profile.noClasses") }}</p>
            </div>
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
      <div class="form-actions" style="justify-content: center">
        <button type="button" class="btn btn--danger" @click="logout">
          <Icon name="logout" :size="15" /> {{ t("auth.logout") }}
        </button>
      </div>
  </AsyncState>
</template>
