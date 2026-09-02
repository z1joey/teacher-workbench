<script setup>
import { ref, computed, onMounted } from "vue"
import api from "../api"
import Icon from "../components/Icon.vue"
import { t } from "../strings"
import { me } from "../auth"

// --- Overview ---
const stats = ref(null)
const loadingStats = ref(true)

async function loadStats() {
  loadingStats.value = true
  try {
    stats.value = await api.get("/admin/stats")
  } catch {}
  loadingStats.value = false
}

// --- Teachers ---
const teachers = ref([])
const loadingTeachers = ref(true)
const editingTeacherId = ref(null)
const editForm = ref({})
const newPassword = ref("")
const saving = ref(false)
const flash = ref("")

async function loadTeachers() {
  loadingTeachers.value = true
  try {
    teachers.value = await api.get("/admin/teachers")
  } catch {}
  loadingTeachers.value = false
}

function startEdit(t) {
  editingTeacherId.value = t.id
  editForm.value = { is_active: t.is_active, is_admin: t.is_admin }
  newPassword.value = ""
}

function cancelEdit() {
  editingTeacherId.value = null
  editForm.value = {}
  newPassword.value = ""
}

async function saveTeacher() {
  if (!editingTeacherId.value) return
  if (editForm.value.is_admin === false && editingTeacherId.value === me.value?.id) {
    flash.value = t("admin.teacherSelfDemote")
    return
  }
  saving.value = true
  try {
    const body = { ...editForm.value }
    if (newPassword.value) body.password = newPassword.value
    await api.patch(`/admin/teachers/${editingTeacherId.value}`, body)
    flash.value = t("admin.saved")
    cancelEdit()
    await loadTeachers()
    setTimeout(() => (flash.value = ""), 2000)
  } catch (e) {
    flash.value = e.message || t("admin.error")
  } finally {
    saving.value = false
  }
}

async function deleteTeacher(id) {
  if (!confirm(t("admin.teacherConfirmDelete"))) return
  try {
    await api.delete(`/admin/teachers/${id}`)
    await loadTeachers()
  } catch (e) {
    alert(e.message || t("admin.error"))
  }
}

// --- Sessions ---
const sessions = ref([])
const loadingSessions = ref(true)

async function loadSessions() {
  loadingSessions.value = true
  try {
    sessions.value = await api.get("/admin/sessions")
  } catch {}
  loadingSessions.value = false
}

async function killSession(prefix) {
  if (!confirm("终止此会话？该用户将被迫重新登录。")) return
  try {
    await api.delete(`/admin/sessions/${prefix}`)
    await loadSessions()
  } catch (e) {
    alert(e.message || t("admin.error"))
  }
}

async function killAllSessions() {
  if (!confirm("清空所有会话？所有人将被迫重新登录。")) return
  try {
    await api.post("/admin/sessions/kill-all")
    await loadSessions()
  } catch (e) {
    alert(e.message || t("admin.error"))
  }
}

// --- Inspect ---
const allTables = ref([])
const selectedTable = ref("")
const inspectLimit = ref(20)
const inspectResult = ref(null)
const inspectLoading = ref(false)

const DISCOVERED_TABLES = [
  "teacher", "student", "class", "enrollment", "exam", "exam_subject",
  "exam_result", "home_visit", "student_event", "auth_session",
]

async function runInspect() {
  if (!selectedTable.value) return
  inspectLoading.value = true
  inspectResult.value = null
  try {
    inspectResult.value = await api.post("/admin/inspect", {
      table: selectedTable.value,
      limit: inspectLimit.value,
    })
  } catch (e) {
    alert(e.message || t("admin.error"))
  } finally {
    inspectLoading.value = false
  }
}

// --- Danger zone ---
const resetting = ref(false)
async function resetDb() {
  if (!confirm(t("admin.resetDbWarn"))) return
  if (!confirm("再次确认：此操作不可逆！")) return
  resetting.value = true
  try {
    await api.post("/admin/db/reset")
    alert(t("admin.resetDbDone"))
    await loadStats()
    await loadTeachers()
    await loadSessions()
  } catch (e) {
    alert(e.message || t("admin.error"))
  } finally {
    resetting.value = false
  }
}

onMounted(async () => {
  selectedTable.value = DISCOVERED_TABLES[0]
  allTables.value = DISCOVERED_TABLES
  await Promise.all([loadStats(), loadTeachers(), loadSessions()])
})

const tableRows = computed(() => {
  if (!stats.value?.tables) return []
  return Object.entries(stats.value.tables)
    .map(([name, count]) => ({ name, count }))
    .sort((a, b) => b.count - a.count)
})

const overviewCards = computed(() => {
  if (!stats.value) return []
  return [
    { label: t("admin.teachersTotal"), value: stats.value.teachers_total },
    { label: t("admin.teachersAdmins"), value: stats.value.teachers_admins },
    { label: t("admin.teachersActive"), value: stats.value.teachers_active },
    { label: t("admin.sessionsActive"), value: stats.value.sessions_active },
  ]
})
</script>

<template>
  <h1>{{ t("admin.title") }}</h1>
  <p class="page-sub">{{ t("admin.subtitle") }}</p>
  <p v-if="flash" class="error-text" :style="{ color: flash === t('admin.saved') ? 'var(--ok)' : 'var(--danger)' }">{{ flash }}</p>

  <!-- Overview -->
  <div class="card">
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
      <h2>{{ t("admin.sectionOverview") }}</h2>
      <button class="small" @click="Promise.all([loadStats(), loadTeachers(), loadSessions()])">
        <Icon name="swap" :size="13" /> {{ t("admin.refresh") }}
      </button>
    </div>

    <div v-if="loadingStats" class="empty">{{ t("admin.loading") }}</div>
    <template v-else-if="stats">
      <div class="stat-grid">
        <div v-for="s in overviewCards" :key="s.label" class="stat">
          <div class="stat-label">{{ s.label }}</div>
          <div class="stat-value">{{ s.value }}</div>
        </div>
        <div class="stat">
          <div class="stat-label">{{ t("admin.dbDriver") }}</div>
          <div class="stat-value" style="font-size: 18px;">{{ stats.database }}</div>
        </div>
      </div>

      <h2 style="margin-top: 18px;">{{ t("admin.dbTables") }}</h2>
      <table>
        <thead>
          <tr>
            <th>{{ t("admin.table") }}</th>
            <th style="text-align: right;">{{ t("admin.rows") }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in tableRows" :key="r.name">
            <td><code>{{ r.name }}</code></td>
            <td style="text-align: right; font-variant-numeric: tabular-nums;">{{ r.count }}</td>
          </tr>
        </tbody>
      </table>
    </template>
  </div>

  <!-- Teachers -->
  <div class="card">
    <h2>{{ t("admin.sectionTeachers") }}</h2>
    <div v-if="loadingTeachers" class="empty">{{ t("admin.loading") }}</div>
    <table v-else>
      <thead>
        <tr>
          <th>{{ t("admin.teacherId") }}</th>
          <th>{{ t("admin.teacherName") }}</th>
          <th>{{ t("admin.teacherPhone") }}</th>
          <th>{{ t("admin.teacherSubject") }}</th>
          <th>{{ t("admin.teacherStatus") }}</th>
          <th>{{ t("admin.teacherAdmin") }}</th>
          <th>{{ t("admin.teacherActions") }}</th>
        </tr>
      </thead>
      <tbody>
        <template v-for="t2 in teachers" :key="t2.id">
          <tr v-if="editingTeacherId !== t2.id">
            <td>#{{ t2.id }}</td>
            <td>{{ t2.name }}</td>
            <td>{{ t2.phone }}</td>
            <td>{{ t2.subject || "—" }}</td>
            <td>
              <span class="badge" :class="t2.is_active ? 'ok' : 'muted'">
                {{ t2.is_active ? "活跃" : "停用" }}
              </span>
            </td>
            <td>
              <span v-if="t2.is_admin" class="badge">ADMIN</span>
              <span v-else class="badge muted">—</span>
            </td>
            <td>
              <div style="display: flex; gap: 6px;">
                <button class="small" @click="startEdit(t2)">
                  <Icon name="pencil" :size="12" />
                </button>
                <button
                  v-if="t2.id !== me?.id"
                  class="small"
                  style="color: var(--danger); border-color: #eecac5;"
                  @click="deleteTeacher(t2.id)"
                >
                  {{ t("admin.teacherDelete") }}
                </button>
              </div>
            </td>
          </tr>
          <tr v-else>
            <td>#{{ t2.id }}</td>
            <td colspan="4">
              <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px;">
                <div class="field checkbox-row">
                  <input type="checkbox" v-model="editForm.is_active" id="edit-active" />
                  <label for="edit-active">{{ t("admin.teacherStatus") }}: 活跃</label>
                </div>
                <div class="field checkbox-row">
                  <input type="checkbox" v-model="editForm.is_admin" id="edit-admin"
                    :disabled="t2.id === me?.id" />
                  <label for="edit-admin">{{ t("admin.teacherAdmin") }}</label>
                </div>
                <div class="field">
                  <input
                    type="password"
                    v-model="newPassword"
                    :placeholder="t2.password ? t('admin.newPassword') : t('admin.newPassword')"
                  />
                </div>
              </div>
            </td>
            <td>
              <div style="display: flex; gap: 6px;">
                <button class="small primary" :disabled="saving" @click="saveTeacher">
                  {{ t("admin.teacherSave") }}
                </button>
                <button class="small" @click="cancelEdit">取消</button>
              </div>
            </td>
          </tr>
        </template>
      </tbody>
    </table>
  </div>

  <!-- Sessions -->
  <div class="card">
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
      <h2>{{ t("admin.sectionSessions") }}</h2>
      <button
        v-if="sessions.length"
        class="small"
        style="color: var(--danger); border-color: #eecac5;"
        @click="killAllSessions"
      >
        {{ t("admin.sessionKillAll") }}
      </button>
    </div>
    <div v-if="loadingSessions" class="empty">{{ t("admin.loading") }}</div>
    <template v-else-if="sessions.length">
      <table>
        <thead>
          <tr>
            <th>{{ t("admin.sessionToken") }}</th>
            <th>{{ t("admin.sessionTeacher") }}</th>
            <th>{{ t("admin.sessionCreated") }}</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="s in sessions" :key="s.token">
            <td><code>{{ s.token }}</code></td>
            <td>
              <router-link :to="`/profile`">{{ s.teacher_name }}</router-link>
            </td>
            <td>{{ new Date(s.created_at).toLocaleString() }}</td>
            <td>
              <button class="small" style="color: var(--danger); border-color: #eecac5;"
                @click="killSession(s.token.replace('…', ''))">
                {{ t("admin.sessionKill") }}
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </template>
    <p v-else class="empty">{{ t("admin.inspectNoData") }}</p>
  </div>

  <!-- Inspect -->
  <div class="card">
    <h2>{{ t("admin.sectionInspect") }}</h2>
    <div style="display: flex; gap: 10px; align-items: end; flex-wrap: wrap; margin-bottom: 14px;">
      <div class="field" style="margin: 0; flex: 1; min-width: 200px;">
        <label>{{ t("admin.inspectTable") }}</label>
        <select v-model="selectedTable">
          <option v-for="tbl in allTables" :key="tbl" :value="tbl">{{ tbl }}</option>
        </select>
      </div>
      <div class="field" style="margin: 0; width: 120px;">
        <label>{{ t("admin.inspectLimit") }}</label>
        <input type="number" v-model="inspectLimit" min="1" max="100" />
      </div>
      <button class="primary" :disabled="inspectLoading" @click="runInspect">
        {{ inspectLoading ? t("admin.loading") : t("admin.inspectRun") }}
      </button>
    </div>
    <template v-if="inspectResult">
      <p v-if="!inspectResult.rows.length" class="empty">{{ t("admin.inspectNoData") }}</p>
      <table v-else>
        <thead>
          <tr>
            <th v-for="(col, i) in inspectResult.columns" :key="i">{{ col }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, ri) in inspectResult.rows" :key="ri">
            <td v-for="(cell, ci) in row" :key="ci">
              <code v-if="typeof cell === 'string' && cell.length > 30" :title="cell">
                {{ cell.slice(0, 27) }}…
              </code>
              <code v-else-if="cell !== null && cell !== undefined">{{ cell }}</code>
              <span v-else class="badge muted">null</span>
            </td>
          </tr>
        </tbody>
      </table>
    </template>
  </div>

  <!-- Danger -->
  <div class="card" style="border-color: #eecac5;">
    <h2 style="color: var(--danger);">{{ t("admin.sectionDanger") }}</h2>
    <button
      :disabled="resetting"
      style="color: var(--danger); border-color: var(--danger);"
      @click="resetDb"
    >
      <Icon name="alert" :size="14" /> {{ t("admin.resetDb") }}
    </button>
  </div>
</template>
