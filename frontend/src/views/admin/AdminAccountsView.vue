<script setup>
import { computed, onMounted, ref } from "vue"
import api from "../../api"
import AdminAccountEditPanel from "../../components/admin/AdminAccountEditPanel.vue"
import AdminCellDetailModal from "../../components/admin/AdminCellDetailModal.vue"
import AdminCompactCell from "../../components/admin/AdminCompactCell.vue"
import Icon from "../../components/Icon.vue"
import PageHeader from "../../components/PageHeader.vue"
import { ask } from "../../confirm"
import { notify } from "../../feedback"
import { me } from "../../auth"
import { friendlyError, t } from "../../strings"
import { useAdminCellDetail } from "./adminTable"

const ROLE_SEGMENTS = [
  { value: "", labelKey: "admin.userFilterAll", countKey: "all" },
  { value: "teacher", labelKey: "admin.roleTeacher", countKey: "teacher" },
  { value: "admin", labelKey: "admin.roleAdmin", countKey: "admin" },
  { value: "student", labelKey: "admin.roleStudent", countKey: "student" },
  { value: "guardian", labelKey: "admin.roleGuardian", countKey: "guardian" },
]

const { cellDetail, openCellDetail, closeCellDetail } = useAdminCellDetail()

const allUsers = ref([])
const loadingUsers = ref(true)
const editingUserId = ref(null)
const editForm = ref({})
const newPassword = ref("")
const roleFilter = ref("")
const workspaceFilter = ref("")
const saving = ref(false)

async function loadUsers() {
  loadingUsers.value = true
  try {
    allUsers.value = await api.get("/admin/users")
  } catch (e) {
    notify({ tone: "error", title: "账号列表加载失败", detail: friendlyError(e) })
  }
  loadingUsers.value = false
}

const workspaceOptions = computed(() =>
  allUsers.value
    .filter((u) => u.role === "teacher")
    .map((u) => ({ id: u.id, label: u.workspace_label || u.name || u.id }))
    .sort((a, b) => a.label.localeCompare(b.label, "zh")),
)

const users = computed(() => {
  let list = allUsers.value
  if (roleFilter.value) list = list.filter((u) => u.role === roleFilter.value)
  if (workspaceFilter.value) {
    const owner = allUsers.value.find((u) => u.id === workspaceFilter.value)
    list = list.filter((u) => {
      if (u.role === "teacher") return u.id === workspaceFilter.value
      if (u.role === "admin") return false
      if (u.role === "student") return u.workspace_owner_id === workspaceFilter.value
      if (u.role === "guardian" && owner?.workspace_label) {
        return (u.workspace_label || "").includes(owner.workspace_label)
      }
      return u.workspace_owner_id === workspaceFilter.value
    })
  }
  return [...list].sort((a, b) => {
    const aw = a.workspace_label || ""
    const bw = b.workspace_label || ""
    if (aw !== bw) return aw.localeCompare(bw, "zh")
    return (a.name || "").localeCompare(b.name || "", "zh")
  })
})

const roleCounts = computed(() => {
  const counts = { all: allUsers.value.length, teacher: 0, admin: 0, student: 0, guardian: 0 }
  for (const u of allUsers.value) {
    if (u.role in counts) counts[u.role]++
  }
  return counts
})

function roleLabel(role) {
  const keys = {
    teacher: "admin.roleTeacher",
    admin: "admin.roleAdmin",
    student: "admin.roleStudent",
    guardian: "admin.roleGuardian",
  }
  return t(keys[role] || role)
}

function rolePillClass(role) {
  if (role === "admin") return ""
  if (role === "teacher") return "pill--muted"
  return "pill--outline"
}

function canManage(u) {
  return u.role === "teacher" || u.role === "admin"
}

function contactLine(u) {
  if (u.role === "student" && u.admission_no) return u.admission_no
  return u.phone || ""
}

function contactLabel(u) {
  if (u.role === "student" && u.admission_no) return "学号"
  return t("admin.teacherPhone")
}

function rowLabel(u) {
  return u.name || u.email || u.id
}

function displayValue(value) {
  if (value === null || value === undefined || value === "") return "—"
  return String(value)
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
    notify({ tone: "ok", title: "账号已删除", timeout: 2600 })
  } catch (e) {
    notify({ tone: "error", title: t("admin.error"), detail: friendlyError(e) })
  }
}

onMounted(loadUsers)
</script>

<template>
  <PageHeader :title="t('admin.sectionAccounts')" :subtitle="t('admin.subtitleAccounts')">
    <template #actions>
      <button class="btn" @click="loadUsers">
        <Icon name="refresh" :size="15" /> {{ t("admin.refresh") }}
      </button>
    </template>
  </PageHeader>

  <div class="segmented-scroll">
    <div class="segmented" role="radiogroup" :aria-label="t('admin.userRole')">
      <button
        v-for="seg in ROLE_SEGMENTS"
        :key="seg.value || 'all'"
        type="button"
        class="segmented__item"
        :class="{ 'is-active': roleFilter === seg.value }"
        @click="roleFilter = seg.value"
      >
        {{ t(seg.labelKey) }}
        <span class="muted">({{ roleCounts[seg.countKey] }})</span>
      </button>
    </div>
  </div>

  <div v-if="workspaceOptions.length" class="admin-workspace-filter">
    <label class="admin-workspace-filter__label muted" for="admin-workspace-filter">
      {{ t("admin.workspaceOwner") }}
    </label>
    <select id="admin-workspace-filter" v-model="workspaceFilter" class="input admin-workspace-filter__select">
      <option value="">{{ t("admin.workspaceFilterAll") }}</option>
      <option v-for="ws in workspaceOptions" :key="ws.id" :value="ws.id">{{ ws.label }}</option>
    </select>
  </div>

  <div class="card">
    <div class="card__head">
      <h2 class="card__title"><Icon name="users" :size="16" /> {{ t("admin.sectionAccounts") }}</h2>
    </div>
    <div v-if="loadingUsers" class="card__body"><div class="skeleton skeleton--row" /></div>
    <p v-else-if="!users.length" class="card__body" style="color: var(--muted)">
      {{ t("admin.inspectNoData") }}
    </p>
    <template v-else>
      <div class="table-wrap admin-table-wrap admin-accounts-table">
        <table class="table table--admin">
          <colgroup>
            <col style="width: 10%" />
            <col style="width: 11%" />
            <col style="width: 14%" />
            <col style="width: 11%" />
            <col style="width: 16%" />
            <col style="width: 9%" />
            <col style="width: 8%" />
            <col style="width: 10%" />
          </colgroup>
          <thead>
            <tr>
              <th>{{ t("admin.teacherId") }}</th>
              <th>{{ t("admin.teacherName") }}</th>
              <th>{{ t("admin.workspaceOwner") }}</th>
              <th>{{ t("admin.teacherPhone") }}</th>
              <th>{{ t("admin.accountEmail") }}</th>
              <th>{{ t("admin.userRole") }}</th>
              <th>{{ t("admin.teacherStatus") }}</th>
              <th>{{ t("admin.teacherActions") }}</th>
            </tr>
          </thead>
          <tbody>
            <template v-for="u in users" :key="u.id">
              <tr v-if="editingUserId !== u.id">
                <td class="muted tnum">
                  <AdminCompactCell
                    :value="u.id"
                    :column="t('admin.teacherId')"
                    :row-label="rowLabel(u)"
                    monospace
                    :show-null="false"
                    @expand="openCellDetail"
                  />
                </td>
                <td class="cell-main">
                  <AdminCompactCell
                    :value="u.name"
                    :column="t('admin.teacherName')"
                    :row-label="rowLabel(u)"
                    :show-null="false"
                    @expand="openCellDetail"
                  />
                </td>
                <td>
                  <AdminCompactCell
                    :value="u.workspace_label"
                    :column="t('admin.workspaceOwner')"
                    :row-label="rowLabel(u)"
                    :show-null="false"
                    @expand="openCellDetail"
                  />
                </td>
                <td>
                  <AdminCompactCell
                    :value="contactLine(u)"
                    :column="t('admin.teacherPhone')"
                    :row-label="rowLabel(u)"
                    :show-null="false"
                    @expand="openCellDetail"
                  />
                </td>
                <td>
                  <AdminCompactCell
                    :value="u.email"
                    :column="t('admin.accountEmail')"
                    :row-label="rowLabel(u)"
                    :show-null="false"
                    @expand="openCellDetail"
                  />
                </td>
                <td>
                  <span class="pill" :class="rolePillClass(u.role)">{{ roleLabel(u.role) }}</span>
                </td>
                <td>
                  <span class="pill" :class="u.is_active ? 'pill--ok' : 'pill--muted'">
                    {{ u.is_active ? "启用" : "停用" }}
                  </span>
                </td>
                <td>
                  <div v-if="canManage(u)" class="row" style="gap: 6px">
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

              <tr v-else class="admin-accounts-edit-row">
                <td colspan="8">
                  <AdminAccountEditPanel
                    :user="u"
                    :form="editForm"
                    :password="newPassword"
                    :saving="saving"
                    :self-id="me?.id"
                    @save="saveUser"
                    @cancel="cancelEdit"
                    @update:password="newPassword = $event"
                  />
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>

      <div class="admin-accounts-cards">
        <article
          v-for="u in users"
          :key="u.id"
          class="admin-account-card"
          :class="{ 'admin-account-card--editing': editingUserId === u.id }"
        >
          <AdminAccountEditPanel
            v-if="editingUserId === u.id"
            :user="u"
            :form="editForm"
            :password="newPassword"
            :saving="saving"
            :self-id="me?.id"
            @save="saveUser"
            @cancel="cancelEdit"
            @update:password="newPassword = $event"
          />

          <template v-else>
            <header class="admin-account-card__head">
              <div class="admin-account-card__identity">
                <h3 class="admin-account-card__name">{{ displayValue(u.name) }}</h3>
                <div class="admin-account-card__badges">
                  <span class="pill" :class="rolePillClass(u.role)">{{ roleLabel(u.role) }}</span>
                  <span class="pill" :class="u.is_active ? 'pill--ok' : 'pill--muted'">
                    {{ u.is_active ? "启用" : "停用" }}
                  </span>
                </div>
              </div>
              <div v-if="canManage(u)" class="admin-account-card__actions">
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
            </header>

            <dl class="admin-account-card__rows">
              <div v-if="u.workspace_label" class="admin-account-card__row">
                <dt class="admin-account-card__label">{{ t("admin.workspaceOwner") }}</dt>
                <dd class="admin-account-card__value">{{ u.workspace_label }}</dd>
              </div>
              <div v-if="contactLine(u)" class="admin-account-card__row">
                <dt class="admin-account-card__label">{{ contactLabel(u) }}</dt>
                <dd class="admin-account-card__value tnum">{{ contactLine(u) }}</dd>
              </div>
              <div v-if="u.email" class="admin-account-card__row">
                <dt class="admin-account-card__label">{{ t("admin.accountEmail") }}</dt>
                <dd class="admin-account-card__value">{{ u.email }}</dd>
              </div>
              <div class="admin-account-card__row">
                <dt class="admin-account-card__label">{{ t("admin.teacherId") }}</dt>
                <dd class="admin-account-card__value tnum muted">{{ u.id }}</dd>
              </div>
            </dl>
          </template>
        </article>
      </div>
    </template>
  </div>

  <AdminCellDetailModal :detail="cellDetail" @close="closeCellDetail" />
</template>
