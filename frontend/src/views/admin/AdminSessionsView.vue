<script setup>
import { onMounted, ref } from "vue"
import api from "../../api"
import AdminCellDetailModal from "../../components/admin/AdminCellDetailModal.vue"
import AdminCompactCell from "../../components/admin/AdminCompactCell.vue"
import Icon from "../../components/Icon.vue"
import PageHeader from "../../components/PageHeader.vue"
import { ask } from "../../confirm"
import { notify } from "../../feedback"
import { friendlyError, t } from "../../strings"
import { fmtTime } from "./fmt"
import { useAdminCellDetail } from "./adminTable"

const { cellDetail, openCellDetail, closeCellDetail } = useAdminCellDetail()

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

onMounted(loadSessions)
</script>

<template>
  <PageHeader :title="t('admin.sectionSessions')" :subtitle="t('admin.subtitleSessions')">
    <template #actions>
      <button class="btn" @click="loadSessions">
        <Icon name="refresh" :size="15" /> {{ t("admin.refresh") }}
      </button>
    </template>
  </PageHeader>

  <div class="card">
    <div class="card__head">
      <h2 class="card__title"><Icon name="clock" :size="16" /> {{ t("admin.sectionSessions") }}</h2>
      <button v-if="sessions.length" class="btn btn--sm btn--danger" @click="killAllSessions">
        {{ t("admin.sessionKillAll") }}
      </button>
    </div>
    <div v-if="loadingSessions" class="card__body"><div class="skeleton skeleton--row" /></div>
    <p v-else-if="!sessions.length" class="state__desc" style="padding: 20px; text-align: center">
      {{ t("admin.inspectNoData") }}
    </p>
    <div v-else class="table-wrap admin-table-wrap">
      <table class="table table--admin">
        <colgroup>
          <col style="width: 22%" />
          <col style="width: 28%" />
          <col style="width: 30%" />
          <col style="width: 20%" />
        </colgroup>
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
            <td>
              <AdminCompactCell
                :value="s.token"
                :column="t('admin.sessionToken')"
                :row-label="s.user_name"
                monospace
                :show-null="false"
                @expand="openCellDetail"
              />
            </td>
            <td>
              <AdminCompactCell
                :value="s.user_name"
                :column="t('admin.sessionTeacher')"
                :row-label="s.token"
                :show-null="false"
                @expand="openCellDetail"
              />
            </td>
            <td class="tnum">
              <AdminCompactCell
                :value="fmtTime(s.created_at)"
                :column="t('admin.sessionCreated')"
                :row-label="s.user_name"
                :show-null="false"
                @expand="openCellDetail"
              />
            </td>
            <td>
              <button class="btn btn--sm btn--danger" @click="killSession(s)">
                {{ t("admin.sessionKill") }}
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>

  <AdminCellDetailModal :detail="cellDetail" @close="closeCellDetail" />
</template>
