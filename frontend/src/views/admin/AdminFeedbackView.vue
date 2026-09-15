<script setup>
import { onMounted, ref } from "vue"
import api from "../../api"
import AdminCellDetailModal from "../../components/admin/AdminCellDetailModal.vue"
import AdminCompactCell from "../../components/admin/AdminCompactCell.vue"
import Icon from "../../components/Icon.vue"
import PageHeader from "../../components/PageHeader.vue"
import { refreshUnresolvedFeedbackCount } from "../../adminFeedback"
import { ask } from "../../confirm"
import { notify } from "../../feedback"
import { friendlyError, t } from "../../strings"
import { fmtTime } from "./fmt"
import { useAdminCellDetail } from "./adminTable"

const { cellDetail, openCellDetail, closeCellDetail } = useAdminCellDetail()

const feedback = ref([])
const loadingFeedback = ref(true)
const actingId = ref(null)

const FEATURE_LABEL_KEYS = {
  home: "feedback.featureHome",
  students: "feedback.featureStudents",
  classes: "feedback.featureClasses",
  exams: "feedback.featureExams",
  visits: "feedback.featureVisits",
  settings: "feedback.featureSettings",
  other: "feedback.featureOther",
}

function featureLabel(k) {
  const key = FEATURE_LABEL_KEYS[k]
  return key ? t(key) : k
}

function authorLine(f) {
  if (!f.author_email) return f.author_name || ""
  return `${f.author_name || "—"} · ${f.author_email}`
}

function rowLabel(f) {
  return `${featureLabel(f.feature)} · ${authorLine(f)}`
}

function statusValue(f) {
  return f.resolved_at ? "resolved" : "open"
}

async function loadFeedback() {
  loadingFeedback.value = true
  try {
    feedback.value = await api.get("/admin/feedback")
    await refreshUnresolvedFeedbackCount()
  } catch (e) {
    feedback.value = []
    notify({ tone: "error", title: "反馈加载失败", detail: friendlyError(e) })
  }
  loadingFeedback.value = false
}

async function updateStatus(f, value) {
  const resolved = value === "resolved"
  if (resolved === !!f.resolved_at) return
  actingId.value = f.id
  try {
    const updated = await api.patch(`/admin/feedback/${f.id}`, { resolved })
    const i = feedback.value.findIndex((row) => row.id === f.id)
    if (i >= 0) feedback.value[i] = updated
    await refreshUnresolvedFeedbackCount()
    notify({
      tone: "ok",
      title: resolved ? t("admin.feedbackResolved") : t("admin.feedbackReopened"),
      timeout: 2400,
    })
  } catch (e) {
    notify({ tone: "error", title: t("admin.error"), detail: friendlyError(e) })
  } finally {
    actingId.value = null
  }
}

async function deleteFeedback(f) {
  const ok = await ask({
    title: t("admin.feedbackDeleteTitle"),
    message: t("admin.feedbackDeleteConfirm"),
    confirmLabel: t("action.delete"),
    tone: "danger",
  })
  if (!ok) return
  actingId.value = f.id
  try {
    await api.delete(`/admin/feedback/${f.id}`)
    feedback.value = feedback.value.filter((row) => row.id !== f.id)
    await refreshUnresolvedFeedbackCount()
    notify({ tone: "ok", title: t("admin.feedbackDeleted"), timeout: 2400 })
  } catch (e) {
    notify({ tone: "error", title: t("admin.error"), detail: friendlyError(e) })
  } finally {
    actingId.value = null
  }
}

onMounted(loadFeedback)
</script>

<template>
  <PageHeader :title="t('admin.sectionFeedback')" :subtitle="t('admin.subtitleFeedback')">
    <template #actions>
      <button class="btn" @click="loadFeedback">
        <Icon name="refresh" :size="15" /> {{ t("admin.refresh") }}
      </button>
    </template>
  </PageHeader>

  <div class="card">
    <div class="card__head">
      <h2 class="card__title"><Icon name="flag" :size="16" /> {{ t("admin.sectionFeedback") }}</h2>
    </div>
    <div v-if="loadingFeedback" class="card__body"><div class="skeleton skeleton--row" /></div>
    <p v-else-if="!feedback.length" class="card__body" style="color: var(--muted)">
      {{ t("admin.feedbackEmpty") }}
    </p>
    <template v-else>
      <div class="table-wrap admin-table-wrap admin-feedback-table">
        <table class="table table--admin">
          <colgroup>
            <col style="width: 9rem" />
            <col />
            <col style="width: 11rem" />
            <col style="width: 9.5rem" />
            <col style="width: 7.5rem" />
            <col style="width: 3rem" />
          </colgroup>
          <thead>
            <tr>
              <th>功能模块</th>
              <th>内容</th>
              <th>提交人</th>
              <th>时间</th>
              <th>{{ t("admin.teacherStatus") }}</th>
              <th />
            </tr>
          </thead>
          <tbody>
            <tr v-for="f in feedback" :key="f.id" :class="{ 'admin-feedback-row--resolved': f.resolved_at }">
              <td>
                <span class="admin-feedback-feature">{{ featureLabel(f.feature) }}</span>
              </td>
              <td>
                <AdminCompactCell
                  :value="f.content"
                  column="内容"
                  :row-label="rowLabel(f)"
                  always-expand
                  :show-null="false"
                  @expand="openCellDetail"
                />
              </td>
              <td>
                <AdminCompactCell
                  :value="authorLine(f)"
                  column="提交人"
                  :row-label="rowLabel(f)"
                  always-expand
                  :show-null="false"
                  @expand="openCellDetail"
                />
              </td>
              <td class="tnum">
                <AdminCompactCell
                  :value="fmtTime(f.created_at)"
                  column="时间"
                  :row-label="rowLabel(f)"
                  always-expand
                  :show-null="false"
                  @expand="openCellDetail"
                />
              </td>
              <td>
                <select
                  class="select admin-feedback-status"
                  :value="statusValue(f)"
                  :disabled="actingId === f.id"
                  @change="updateStatus(f, $event.target.value)"
                >
                  <option value="open">{{ t("admin.feedbackOpenLabel") }}</option>
                  <option value="resolved">{{ t("admin.feedbackResolvedLabel") }}</option>
                </select>
              </td>
              <td>
                <button
                  class="icon-btn icon-btn--danger"
                  :disabled="actingId === f.id"
                  :aria-label="t('action.delete')"
                  @click="deleteFeedback(f)"
                >
                  <Icon name="trash" :size="14" />
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="admin-feedback-cards">
        <article
          v-for="f in feedback"
          :key="f.id"
          class="admin-feedback-card"
          :class="{ 'admin-feedback-card--resolved': f.resolved_at }"
        >
          <header class="admin-feedback-card__head">
            <span class="admin-feedback-card__feature">{{ featureLabel(f.feature) }}</span>
            <div class="admin-feedback-card__tools">
              <select
                class="select admin-feedback-status"
                :value="statusValue(f)"
                :disabled="actingId === f.id"
                @change="updateStatus(f, $event.target.value)"
              >
                <option value="open">{{ t("admin.feedbackOpenLabel") }}</option>
                <option value="resolved">{{ t("admin.feedbackResolvedLabel") }}</option>
              </select>
              <button
                class="icon-btn icon-btn--danger"
                :disabled="actingId === f.id"
                :aria-label="t('action.delete')"
                @click="deleteFeedback(f)"
              >
                <Icon name="trash" :size="14" />
              </button>
            </div>
          </header>

          <div class="admin-feedback-card__content">
            <AdminCompactCell
              :value="f.content"
              column="内容"
              :row-label="rowLabel(f)"
              always-expand
              :show-null="false"
              @expand="openCellDetail"
            />
          </div>

          <dl class="admin-feedback-card__rows">
            <div class="admin-feedback-card__row">
              <dt class="admin-feedback-card__label">提交人</dt>
              <dd class="admin-feedback-card__value">
                <AdminCompactCell
                  :value="authorLine(f)"
                  column="提交人"
                  :row-label="rowLabel(f)"
                  always-expand
                  :show-null="false"
                  @expand="openCellDetail"
                />
              </dd>
            </div>
            <div class="admin-feedback-card__row">
              <dt class="admin-feedback-card__label">时间</dt>
              <dd class="admin-feedback-card__value tnum">
                <AdminCompactCell
                  :value="fmtTime(f.created_at)"
                  column="时间"
                  :row-label="rowLabel(f)"
                  always-expand
                  :show-null="false"
                  @expand="openCellDetail"
                />
              </dd>
            </div>
          </dl>
        </article>
      </div>
    </template>
  </div>

  <AdminCellDetailModal :detail="cellDetail" @close="closeCellDetail" />
</template>
