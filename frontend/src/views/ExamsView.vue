<script setup>
import { ref, onMounted } from "vue"
import Icon from "../components/Icon.vue"
import api from "../api"
import { exatypeLabel, subject, termLabel, t } from "../strings"

const exams = ref([])
const loading = ref(true)
const error = ref("")

onMounted(async () => {
  try {
    exams.value = await api.get("/exams")
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
})

function fmtDate(d) {
  return new Date(d).toLocaleDateString("zh-CN", { year: "numeric", month: "short", day: "numeric" })
}
</script>

<template>
  <div style="display: flex; justify-content: space-between; align-items: center; gap: 12px">
    <h1 style="margin-bottom: 0">{{ t("exams.title") }}</h1>
    <router-link to="/exams/new">
      <button class="primary"><Icon name="plus" :size="15" /> {{ t("exams.create") }}</button>
    </router-link>
  </div>
  <p class="page-sub"></p>

  <p v-if="error" class="error-text">{{ error }}</p>
  <p v-else-if="loading" class="empty">{{ t("common.loading") }}</p>
  <p v-else-if="!exams.length" class="empty">{{ t("common.none") }}</p>

  <div v-else v-for="e in exams" :key="e.id" class="card">
    <div style="display: flex; justify-content: space-between; align-items: baseline; flex-wrap: wrap; gap: 8px">
      <div>
        <h2 style="margin-bottom: 2px">
          {{ e.name }}
          <span class="badge muted" style="margin-left: 6px">{{ exatypeLabel(e.exam_type) }}</span>
        </h2>
        <span class="page-sub" style="margin: 0">
          {{ fmtDate(e.exam_date) }} · {{ termLabel(e.term) }} · {{ e.academic_year }}
        </span>
      </div>
      <router-link :to="`/exams/${e.id}`">
        <button class="primary small">{{ t("exams.viewAverages") }}</button>
      </router-link>
    </div>
    <div style="display: flex; gap: 8px; margin-top: 10px">
      <span v-for="s in e.subjects" :key="s.id" class="badge">
        {{ subject(s.subject) }} · {{ t("exams.fullScore") }} {{ s.full_score }}
      </span>
    </div>
  </div>
</template>
