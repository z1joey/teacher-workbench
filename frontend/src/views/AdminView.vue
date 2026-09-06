<script setup>
// 开发者后台：危险区域单独成块，重置数据库要求输入名称才能执行（防错）。
// 所有破坏性操作都改用确认对话框，不再用浏览器原生 confirm/alert。
import { computed, onMounted, ref } from "vue"
import api from "../api"
import Icon from "../components/Icon.vue"
import PageHeader from "../components/PageHeader.vue"
import { ask } from "../confirm"
import { notify } from "../feedback"
import { me } from "../auth"
import { friendlyError, t } from "../strings"

// --- Overview ---
const stats = ref(null)
const loadingStats = ref(true)

async function loadStats() {
  loadingStats.value = true
  try {
    stats.value = await api.get("/admin/stats")
  } catch (e) {
    notify({ tone: "error", title: "概览加载失败", detail: friendlyError(e) })
  }
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

async function loadUsers() {
  loadingUsers.value = true
  try {
    const qs = roleFilter.value ? `?role=${roleFilter.value}` : ""
    users.value = await api.get(`/admin/users${qs}`)
  } catch (e) {
    notify({ tone: "error", title: "账号列表加载失败", detail: friendlyError(e) })
  }
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
    notify({ tone: "error", title: t("admin.userSelfDemote") })
    return
  }
  saving.value = true
  try {
    const body = { ...editForm.value }
    if (newPassword.value) body.password = newPassword.value
    await api.patch(`/admin/users/${editingUserId.value}`, body)
    cancelEdit()
    await loadUsers()
    await loadStats()
    notify({ tone: "ok", title: t("admin.saved"), timeout: 2400 })
  } catch (e) {
    notify({ tone: "error", title: t("admin.error"), detail: friendlyError(e) })
  } finally {
    saving.value = false
  }
}

async function deleteUser(u) {
  const ok = await ask({
    title: `删除账号「${u.name}」？`,
    consequences: [t("admin.userConfirmDelete"), "他创建的数据会保留，但账号本身不可恢复。"],
    confirmLabel: t("admin.teacherDelete"),
  })
  if (!ok) return
  try {
    await api.delete(`/admin/users/${u.id}`)
    await loadUsers()
    await loadStats()
    notify({ tone: "ok", title: "账号已删除", timeout: 2600 })
  } catch (e) {
    notify({ tone: "error", title: t("admin.error"), detail: friendlyError(e) })
  }
}

// --- Sessions ---
const sessions = ref([])
const loadingSessions = ref(true)

async function loadSessions() {
  loadingSessions.value = true
  try {
    sessions.value = await api.get("/admin/sessions")
  } catch (e) {
    notify({ tone: "error", title: "会话列表加载失败", detail: friendlyError(e) })
  }
  loadingSessions.value = false
}

async function killSession(s) {
  const ok = await ask({
    title: "终止这个会话？",
    message: `${s.user_name} 会被强制退出，需要重新登录。`,
    confirmLabel: t("admin.sessionKill"),
    tone: "warn",
  })
  if (!ok) return
  try {
    await api.delete(`/admin/sessions/${s.token.replace("…", "")}`)
    await loadSessions()
    notify({ tone: "ok", title: "会话已终止", timeout: 2400 })
  } catch (e) {
    notify({ tone: "error", title: t("admin.error"), detail: friendlyError(e) })
  }
}

async function killAllSessions() {
  const ok = await ask({
    title: "清空所有会话？",
    message: "所有人（包括你自己）都会被强制退出，需要重新登录。",
    confirmLabel: t("admin.sessionKillAll"),
    tone: "warn",
  })
  if (!ok) return
  try {
    await api.post("/admin/sessions/kill-all")
    await loadSessions()
    notify({ tone: "ok", title: "所有会话已清空", timeout: 2400 })
  } catch (e) {
    notify({ tone: "error", title: t("admin.error"), detail: friendlyError(e) })
  }
}

// --- Inspect ---
const DISCOVERED_TABLES = [
  "user", "teacher_profile", "student", "class", "enrollment", "exam",
  "exam_subject", "exam_result", "student_event", "auth_session",
]
const selectedTable = ref(DISCOVERED_TABLES[0])
const inspectLimit = ref(20)
const inspectResult = ref(null)
const inspectLoading = ref(false)

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
    notify({ tone: "error", title: "预览失败", detail: friendlyError(e) })
  } finally {
    inspectLoading.value = false
  }
}

// --- Danger zone ---
const resetting = ref(false)
async function resetDb() {
  const ok = await ask({
    title: t("admin.resetDb"),
    message: t("admin.resetDbWarn"),
    consequences: [
      "所有学生、班级、考试、成绩、跟进记录都会消失。",
      "账号也会一并清空，你需要重新注册。",
    ],
    confirmLabel: t("admin.resetDb"),
    // 极端操作：必须手动输入名称，防止手滑
    confirmWord: "重置数据库",
  })
  if (!ok) return
  resetting.value = true
  try {
    await api.post("/admin/db/reset")
    notify({ tone: "ok", title: t("admin.resetDbDone"), timeout: 4000 })
    await loadStats()
    await loadUsers()
    await loadSessions()
  } catch (e) {
    notify({ tone: "error", title: t("admin.error"), detail: friendlyError(e) })
  } finally {
    resetting.value = false
  }
}

onMounted(() => Promise.all([loadStats(), loadUsers(), loadSessions()]))

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

function fmtTime(v) {
  return new Date(v).toLocaleString("zh-CN")
}
</script>

<template>
  <PageHeader :title="t('admin.title')" :subtitle="t('admin.subtitle')">
    <template #actions>
      <button class="btn" @click="Promise.all([loadStats(), loadUsers(), loadSessions()])">
        <Icon name="refresh" :size="15" /> {{ t("admin.refresh") }}
      </button>
    </template>
  </PageHeader>

  <!-- Overview -->
  <div class="card">
    <div class="card__head">
      <h2 class="card__title"><Icon name="chart" :size="16" /> {{ t("admin.sectionOverview") }}</h2>
    </div>
    <div class="card__body">
      <div v-if="loadingStats" class="stack">
        <div class="skeleton skeleton--row" />
      </div>
      <template v-else-if="stats">
        <div class="stat-grid">
          <div v-for="s in overviewCards" :key="s.label" class="stat">
            <div class="stat__label">{{ s.label }}</div>
            <div class="stat__value tnum">{{ s.value }}</div>
          </div>
        </div>

        <h3 class="section-title" style="margin: 20px 0 12px">{{ t("admin.dbTables") }}</h3>
        <div class="table-wrap">
          <table class="table table--stack">
            <thead>
              <tr>
                <th>{{ t("admin.table") }}</th>
                <th class="cell-num">{{ t("admin.rows") }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="r in tableRows" :key="r.name">
                <td data-label="表名"><code>{{ r.name }}</code></td>
                <td data-label="行数" class="cell-num tnum">{{ r.count }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p class="stat__sub" style="margin-top: 12px">{{ t("admin.dbDriver") }}：{{ stats.database }}</p>
      </template>
    </div>
  </div>

  <!-- Accounts -->
  <div class="card">
    <div class="card__head">
      <h2 class="card__title"><Icon name="users" :size="16" /> {{ t("admin.sectionAccounts") }}</h2>
      <select v-model="roleFilter" class="select input--sm" style="width: auto" @change="loadUsers">
        <option value="">{{ t("admin.userFilterAll") }}</option>
        <option value="teacher">{{ t("admin.roleTeacher") }}</option>
        <option value="admin">{{ t("admin.roleAdmin") }}</option>
      </select>
    </div>
    <div class="table-wrap">
      <div v-if="loadingUsers" class="card__body"><div class="skeleton skeleton--row" /></div>
      <table v-else class="table table--stack">
        <thead>
          <tr>
            <th>{{ t("admin.teacherId") }}</th>
            <th>{{ t("admin.teacherName") }}</th>
            <th>{{ t("admin.teacherPhone") }}</th>
            <th>{{ t("admin.userRole") }}</th>
            <th>{{ t("admin.teacherStatus") }}</th>
            <th>{{ t("admin.teacherActions") }}</th>
          </tr>
        </thead>
        <tbody>
          <template v-for="u in users" :key="u.id">
            <tr v-if="editingUserId !== u.id">
              <td data-label="ID" class="muted tnum">#{{ u.id }}</td>
              <td data-label="姓名" class="cell-main">{{ u.name }}</td>
              <td data-label="手机号">{{ u.phone }}</td>
              <td data-label="角色">
                <span class="pill" :class="u.role === 'admin' ? '' : 'pill--muted'">
                  {{ u.role === "admin" ? t("admin.roleAdmin") : t("admin.roleTeacher") }}
                </span>
              </td>
              <td data-label="状态">
                <span class="pill" :class="u.is_active ? 'pill--ok' : 'pill--muted'">
                  {{ u.is_active ? "启用" : "停用" }}
                </span>
              </td>
              <td data-label="操作">
                <div class="row" style="gap: 6px">
                  <button class="icon-btn" :aria-label="`编辑 ${u.name}`" @click="startEdit(u)">
                    <Icon name="pencil" :size="14" />
                  </button>
                  <button
                    v-if="u.id !== me?.id"
                    class="icon-btn icon-btn--danger"
                    :aria-label="`删除 ${u.name}`"
                    @click="deleteUser(u)"
                  >
                    <Icon name="trash" :size="14" />
                  </button>
                </div>
              </td>
            </tr>

            <!-- 就地编辑账号 -->
            <tr v-else>
              <td data-label="ID" class="muted tnum">#{{ u.id }}</td>
              <td data-label="姓名">{{ u.name }}</td>
              <td :colspan="4" data-label="编辑">
                <div class="form-grid">
                  <label class="check">
                    <input v-model="editForm.is_active" type="checkbox" />
                    <span>启用这个账号</span>
                  </label>
                  <div class="field" style="margin: 0">
                    <span class="field__label">{{ t("admin.userRole") }}</span>
                    <select v-model="editForm.role" class="select" :disabled="u.id === me?.id">
                      <option value="teacher">{{ t("admin.roleTeacher") }}</option>
                      <option value="admin">{{ t("admin.roleAdmin") }}</option>
                    </select>
                    <span v-if="u.id === me?.id" class="field__hint">不能修改自己的角色</span>
                  </div>
                  <div class="field" style="margin: 0">
                    <span class="field__label">{{ t("admin.teacherResetPwd") }}</span>
                    <input
                      v-model="newPassword"
                      class="input input--sm"
                      type="password"
                      :placeholder="t('admin.newPassword')"
                      autocomplete="new-password"
                    />
                  </div>
                </div>
                <div class="row" style="margin-top: 12px">
                  <button class="btn btn--sm btn--primary" :disabled="saving" @click="saveUser">
                    {{ t("admin.teacherSave") }}
                  </button>
                  <button class="btn btn--sm btn--ghost" @click="cancelEdit">{{ t("action.cancel") }}</button>
                </div>
              </td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>
  </div>

  <!-- Sessions -->
  <div class="card">
    <div class="card__head">
      <h2 class="card__title"><Icon name="clock" :size="16" /> {{ t("admin.sectionSessions") }}</h2>
      <button v-if="sessions.length" class="btn btn--sm btn--danger" @click="killAllSessions">
        {{ t("admin.sessionKillAll") }}
      </button>
    </div>
    <div v-if="loadingSessions" class="card__body"><div class="skeleton skeleton--row" /></div>
    <template v-else-if="sessions.length">
      <div class="table-wrap">
        <table class="table table--stack">
          <thead>
            <tr>
              <th>{{ t("admin.sessionToken") }}</th>
              <th>{{ t("admin.sessionTeacher") }}</th>
              <th>{{ t("admin.sessionCreated") }}</th>
              <th />
            </tr>
          </thead>
          <tbody>
            <tr v-for="s in sessions" :key="s.token">
              <td data-label="Token"><code>{{ s.token }}</code></td>
              <td data-label="用户">{{ s.user_name }}</td>
              <td data-label="创建时间">{{ fmtTime(s.created_at) }}</td>
              <td data-hidden-mobile>
                <button class="btn btn--sm btn--danger" @click="killSession(s)">
                  {{ t("admin.sessionKill") }}
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
    <p v-else class="state__desc" style="padding: 20px; text-align: center">{{ t("admin.inspectNoData") }}</p>
  </div>

  <!-- Inspect -->
  <div class="card">
    <div class="card__head">
      <h2 class="card__title"><Icon name="search" :size="16" /> {{ t("admin.sectionInspect") }}</h2>
    </div>
    <div class="card__body">
      <div class="form-grid" style="align-items: end; margin-bottom: 16px">
        <div class="field" style="margin: 0">
          <span class="field__label">{{ t("admin.inspectTable") }}</span>
          <select v-model="selectedTable" class="select">
            <option v-for="tbl in DISCOVERED_TABLES" :key="tbl" :value="tbl">{{ tbl }}</option>
          </select>
        </div>
        <div class="field" style="margin: 0; max-width: 140px">
          <span class="field__label">{{ t("admin.inspectLimit") }}</span>
          <input v-model="inspectLimit" class="input" type="number" min="1" max="100" />
        </div>
        <button class="btn btn--primary" :disabled="inspectLoading" @click="runInspect">
          <span v-if="inspectLoading" class="spinner" />
          {{ inspectLoading ? t("admin.loading") : t("admin.inspectRun") }}
        </button>
      </div>

      <div v-if="inspectResult" class="table-wrap">
        <p v-if="!inspectResult.rows.length" class="state__desc" style="padding: 16px 0; text-align: center">
          {{ t("admin.inspectNoData") }}
        </p>
        <table v-else class="table">
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
                <span v-else class="pill pill--muted">null</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>

  <!-- Danger -->
  <div class="card card--danger">
    <div class="card__head">
      <div>
        <h2 class="card__title"><Icon name="alert" :size="16" /> {{ t("admin.sectionDanger") }}</h2>
        <p class="card__desc">这一区的操作不可撤销，执行前会要求你再次确认。</p>
      </div>
    </div>
    <div class="card__body">
      <button class="btn btn--danger-solid" :disabled="resetting" @click="resetDb">
        <Icon name="alert" :size="15" /> {{ t("admin.resetDb") }}
      </button>
    </div>
  </div>
</template>
