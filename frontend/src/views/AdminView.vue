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

// --- Accounts ---
const users = ref([])
const loadingUsers = ref(true)
const editingUserId = ref(null)
const editForm = ref({})
const newPassword = ref("")
const roleFilter = ref("")
const saving = ref(false)
const flash = ref("")

async function loadUsers() {
  loadingUsers.value = true
  try {
    const qs = roleFilter.value ? `?role=${roleFilter.value}` : ""
    users.value = await api.get(`/admin/users${qs}`)
  } catch {}
  loadingUsers.value = false
}

function startEdit(u) {
  editingUserId.value = u.id
  editForm.value = { is_active: u.is_active, role: u.role }
  newPassword.value = ""
}

function cancelEdit() {
  editingUserId.value = null
  editForm.value = {}
  newPassword.value = ""
}

async function saveUser() {
  if (!editingUserId.value) return
  if (editForm.value.role !== "admin" && editingUserId.value === me.value?.id) {
    flash.value = t("admin.userSelfDemote")
    return
  }
  saving.value = true
  try {
    const body = { ...editForm.value }
    if (newPassword.value) body.password = newPassword.value
    await api.patch(`/admin/users/${editingUserId.value}`, body)
    flash.value = t("admin.saved")
    cancelEdit()
    await loadUsers()
    await loadStats()
    setTimeout(() => (flash.value = ""), 2000)
  } catch (e) {
    flash.value = e.message || t("admin.error")
  } finally {
    saving.value = false
  }
}

async function deleteUser(id) {
  if (!confirm(t("admin.userConfirmDelete"))) return
  try {
    await api.delete(`/admin/users/${id}`)
    await loadUsers()
    await loadStats()
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
  "user", "teacher_profile", "student", "class", "enrollment", "exam",
  "exam_subject", "exam_result", "student_event", "auth_session",
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
    await loadUsers()
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
  await Promise.all([loadStats(), loadUsers(), loadSessions()])
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
    { label: t("admin.usersTotal"), value: stats.value.users_total },
    { label: t("admin.usersAdmins"), value: stats.value.users_admins },
    { label: t("admin.usersActive"), value: stats.value.users_active },
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
      <button class="small" @click="Promise.all([loadStats(), loadUsers(), loadSessions()])">
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

  <!-- Accounts -->
  <div class="card">
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
      <h2>{{ t("admin.sectionAccounts") }}</h2>
      <select v-model="roleFilter" class="small" style="padding: 4px 8px;" @change="loadUsers">
        <option value="">{{ t("admin.userFilterAll") }}</option>
        <option value="teacher">{{ t("admin.roleTeacher") }}</option>
        <option value="admin">{{ t("admin.roleAdmin") }}</option>
      </select>
    </div>
    <div v-if="loadingUsers" class="empty">{{ t("admin.loading") }}</div>
    <table v-else>
      <thead>
        <tr>
          <th>{{ t("admin.teacherId") }}</th>
          <th>{{ t("admin.teacherName") }}</th>
          <th>{{ t("admin.teacherPhone") }}</th>
          <th>{{ t("admin.teacherSubject") }}</th>
          <th>{{ t("admin.userRole") }}</th>
          <th>{{ t("admin.teacherStatus") }}</th>
          <th>{{ t("admin.teacherActions") }}</th>
        </tr>
      </thead>
      <tbody>
        <template v-for="u in users" :key="u.id">
          <tr v-if="editingUserId !== u.id">
            <td>#{{ u.id }}</td>
            <td>{{ u.name }}</td>
            <td>{{ u.phone }}</td>
            <td>{{ u.subject || "—" }}</td>
            <td>
              <span class="badge" :class="u.role === 'admin' ? '' : 'muted'">
                {{ u.role === "admin" ? "ADMIN" : t("admin.roleTeacher") }}
              </span>
            </td>
            <td>
              <span class="badge" :class="u.is_active ? 'ok' : 'muted'">
                {{ u.is_active ? "活跃" : "停用" }}
              </span>
            </td>
            <td>
              <div style="display: flex; gap: 6px;">
                <button class="small" @click="startEdit(u)">
                  <Icon name="pencil" :size="12" />
                </button>
                <button
                  v-if="u.id !== me?.id"
                  class="small"
                  style="color: var(--danger); border-color: #eecac5;"
                  @click="deleteUser(u.id)"
                >
                  {{ t("admin.teacherDelete") }}
                </button>
              </div>
            </td>
          </tr>
          <tr v-else>
            <td>#{{ u.id }}</td>
            <td colspan="5">
              <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px;">
                <div class="field checkbox-row">
                  <input type="checkbox" v-model="editForm.is_active" id="edit-active" />
                  <label for="edit-active">{{ t("admin.teacherStatus") }}: 活跃</label>
                </div>
                <div class="field">
                  <select v-model="editForm.role" id="edit-role" :disabled="u.id === me?.id">
                    <option value="teacher">{{ t("admin.roleTeacher") }}</option>
                    <option value="admin">{{ t("admin.roleAdmin") }}</option>
                  </select>
                </div>
                <div class="field">
                  <input
                    type="password"
                    v-model="newPassword"
                    :placeholder="t('admin.newPassword')"
                  />
                </div>
              </div>
            </td>
            <td>
              <div style="display: flex; gap: 6px;">
                <button class="small primary" :disabled="saving" @click="saveUser">
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
              <router-link :to="`/profile`">{{ s.user_name }}</router-link>
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
