<script setup>
import { onMounted, ref } from "vue"
import api from "../../api"
import AdminCellDetailModal from "../../components/admin/AdminCellDetailModal.vue"
import AdminCompactCell from "../../components/admin/AdminCompactCell.vue"
import Icon from "../../components/Icon.vue"
import PageHeader from "../../components/PageHeader.vue"
import { t } from "../../strings"
import { fmtTime } from "./fmt"
import { useAdminCellDetail } from "./adminTable"

const { cellDetail, openCellDetail, closeCellDetail } = useAdminCellDetail()

const feedback = ref([])
const loadingFeedback = ref(true)

const FEATURE_LABELS = {
  home: "首页", students: "学生", classes: "班级", exams: "考试",
  visits: "家访", settings: "个人中心 / 设置", other: "其他",
}

function featureLabel(k) {
  return FEATURE_LABELS[k] || k
}

function authorLine(f) {
  if (!f.author_email) return f.author_name || ""
  return `${f.author_name || "—"} · ${f.author_email}`
}

async function loadFeedback() {
  loadingFeedback.value = true
  try {
    feedback.value = await api.get("/admin/feedback")
  } catch {
    feedback.value = []
  }
  loadingFeedback.value = false
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
      还没有收到反馈
    </p>
    <div v-else class="table-wrap admin-table-wrap">
      <table class="table table--admin">
        <colgroup>
          <col style="width: 14%" />
          <col style="width: 46%" />
          <col style="width: 24%" />
          <col style="width: 16%" />
        </colgroup>
        <thead>
          <tr>
            <th>功能模块</th>
            <th>内容</th>
            <th>提交人</th>
            <th>时间</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="f in feedback" :key="f.id">
            <td><span class="pill pill--outline">{{ featureLabel(f.feature) }}</span></td>
            <td>
              <AdminCompactCell
                :value="f.content"
                column="内容"
                :row-label="authorLine(f)"
                :show-null="false"
                @expand="openCellDetail"
              />
            </td>
            <td>
              <AdminCompactCell
                :value="authorLine(f)"
                column="提交人"
                :row-label="fmtTime(f.created_at)"
                :show-null="false"
                @expand="openCellDetail"
              />
            </td>
            <td class="tnum">
              <AdminCompactCell
                :value="fmtTime(f.created_at)"
                column="时间"
                :row-label="authorLine(f)"
                :show-null="false"
                @expand="openCellDetail"
              />
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>

  <AdminCellDetailModal :detail="cellDetail" @close="closeCellDetail" />
</template>
