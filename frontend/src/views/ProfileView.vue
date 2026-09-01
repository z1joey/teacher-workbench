<script setup>
import { ref, computed, onMounted } from "vue"
import { useRouter } from "vue-router"
import Icon from "../components/Icon.vue"
import api, { setToken } from "../api"
import { clearMe, me } from "../auth"
import { genderLabel, subject, t } from "../strings"

const router = useRouter()

async function logout() {
  try {
    await api.post("/auth/logout")
  } catch {
    // token already invalid — clearing locally is enough
  }
  setToken(null)
  clearMe()
  router.push("/login")
}

const profile = ref(null)
const error = ref("")
const editing = ref(false)
const saving = ref(false)
const saved = ref(false)
const editForm = ref({ name: "", email: "", subject: "" })

onMounted(load)

async function load() {
  error.value = ""
  try {
    profile.value = await api.get("/profile")
  } catch (e) {
    error.value = e.message
  }
}

function startEdit() {
  const teacher = profile.value.teacher
  editForm.value = { name: teacher.name, email: teacher.email || "", subject: teacher.subject || "" }
  saved.value = false
  editing.value = true
}

async function saveProfile() {
  saving.value = true
  error.value = ""
  try {
    const updated = await api.patch("/profile", {
      name: editForm.value.name,
      email: editForm.value.email || null,
      subject: editForm.value.subject || null,
    })
    profile.value.teacher = updated
    if (me.value) me.value = { ...me.value, ...updated } // keep the nav name in sync
    editing.value = false
    saved.value = true
    setTimeout(() => (saved.value = false), 2000)
  } catch (e) {
    error.value = e.message
  } finally {
    saving.value = false
  }
}

function fmtDate(d) {
  return d ? new Date(d).toLocaleDateString("zh-CN", { year: "numeric", month: "short", day: "numeric" }) : "—"
}

const activity = computed(() => {
  if (!profile.value) return []
  const s = profile.value.stats
  return [
    { label: t("profile.visitsRecorded"), value: s.home_visits },
    { label: t("profile.resultsEntered"), value: s.results_entered },
    { label: t("profile.notesAdded"), value: s.notes_added },
  ]
})
</script>

<template>
  <p v-if="error" class="error-text">{{ error }}</p>
  <p v-else-if="!profile" class="empty">{{ t("common.loading") }}</p>

  <template v-else>
    <h1>{{ t("profile.title") }}</h1>
    <p class="page-sub">{{ t("profile.subtitle") }}</p>

    <div class="two-col">
      <div>
        <!-- teacher card -->
        <div class="card">
          <div class="profile-head">
            <div class="avatar">{{ profile.teacher.name.charAt(0) }}</div>
            <div style="flex: 1">
              <h1 style="margin-bottom: 0">{{ profile.teacher.name }}</h1>
              <div class="profile-meta">
                <span class="badge">{{ t("profile.loginPhone") }}: {{ profile.teacher.phone }}</span>
                <span v-if="profile.teacher.email">{{ t("profile.email") }}: {{ profile.teacher.email }}</span>
                <span v-if="profile.teacher.subject">{{ t("profile.subject") }}: {{ subject(profile.teacher.subject) }}</span>
              </div>
            </div>
            <button v-if="!editing" class="small" @click="startEdit">{{ t("profile.editInfo") }}</button>
          </div>

          <form v-if="editing" style="margin-top: 14px" @submit.prevent="saveProfile">
            <div class="field">
              <label>{{ t("login.name") }} *</label>
              <input v-model="editForm.name" type="text" required />
            </div>
            <div class="field">
              <label>{{ t("profile.email") }}</label>
              <input v-model="editForm.email" type="email" />
            </div>
            <div class="field">
              <label>{{ t("profile.subject") }}</label>
              <input v-model="editForm.subject" type="text" />
            </div>
            <button type="submit" class="primary small" :disabled="saving">
              {{ saving ? t("new.saving") : t("action.save") }}
            </button>
            <button type="button" class="small" style="margin-left: 8px" @click="editing = false">
              {{ t("action.cancel") }}
            </button>
          </form>
          <p v-if="saved" class="error-text" style="color: var(--ok); display: inline-flex; align-items: center; gap: 4px">
            <Icon name="check" :size="13" /> {{ t("profile.saved") }}
          </p>
        </div>

        <!-- classes -->
        <div class="card">
          <h2>{{ t("profile.myClasses") }}</h2>
          <p v-if="!profile.classes.length" class="empty">{{ t("profile.noClasses") }}</p>
          <div v-for="c in profile.classes" :key="c.id" style="margin-bottom: 16px">
            <div style="display: flex; gap: 8px; align-items: center; margin-bottom: 8px">
              <span class="badge">{{ c.name }}</span>
              <span class="weakness-sub">{{ c.academic_year }} · {{ t("profile.studentsCount", { n: c.students.length }) }}</span>
            </div>
            <div class="student-chips">
              <router-link
                v-for="s in c.students"
                :key="s.id"
                :to="`/students/${s.id}`"
                class="student-chip"
              >
                {{ s.name }} <span class="weakness-sub">{{ genderLabel(s.gender) }}</span>
              </router-link>
            </div>
          </div>
        </div>
      </div>

      <div>
        <!-- activity -->
        <div class="card">
          <h2>{{ t("profile.activity") }}</h2>
          <div class="stat" style="box-shadow: none; border: none; padding: 6px 0" v-for="a in activity" :key="a.label">
            <div class="stat-label">{{ a.label }}</div>
            <div class="stat-value">{{ a.value }}</div>
          </div>
        </div>

        <div style="text-align: center">
          <button class="logout-btn" @click="logout">{{ t("auth.logout") }}</button>
        </div>
      </div>
    </div>
  </template>
</template>
