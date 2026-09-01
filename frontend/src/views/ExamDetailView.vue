<script setup>
import { ref, computed, onMounted } from "vue"
import api from "../api"
import LineChart from "../components/LineChart.vue"
import { subject, subjectColor, t } from "../strings"

const props = defineProps({ id: { type: String, required: true } })

const averages = ref(null)
const trendData = ref(null)
const loading = ref(true)
const error = ref("")

onMounted(async () => {
  try {
    const [av, tr] = await Promise.all([
      api.get(`/exams/${props.id}/averages`),
      api.get("/exams/trend"),
    ])
    averages.value = av
    trendData.value = tr
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
})

const trendChart = computed(() => {
  if (!trendData.value || !trendData.value.exams.length) return null
  const labels = trendData.value.exams.map((e) => e.name)
  const series = trendData.value.series.map((s) => ({
    key: s.subject,
    label: subject(s.subject),
    color: subjectColor(s.subject),
    values: s.values,
  }))
  const yMax = Math.max(100, ...trendData.value.series.map((s) => s.full_score || 0))
  const highlightIndex = trendData.value.exams.findIndex(
    (e) => averages.value && e.id === averages.value.exam.id
  )
  return { labels, series, yMax, highlightIndex }
})

const subjects = computed(() => (averages.value ? averages.value.school.map((s) => s.subject) : []))

const classRows = computed(() => {
  if (!averages.value) return []
  const byClass = {}
  for (const c of averages.value.classes) {
    byClass[c.class_name] = byClass[c.class_name] || {}
    byClass[c.class_name][c.subject] = c
  }
  return Object.entries(byClass).map(([name, cells]) => ({
    label: name,
    cells,
  }))
})

function fmtDate(d) {
  return new Date(d).toLocaleDateString("zh-CN", { year: "numeric", month: "short", day: "numeric" })
}

function pct(score, full) {
  return full ? Math.round((score / full) * 100) : 0
}
</script>

<template>
  <p v-if="error" class="error-text">{{ error }}</p>
  <p v-else-if="loading" class="empty">{{ t("common.loading") }}</p>

  <template v-else-if="averages">
    <h1>
      {{ averages.exam.name }} · {{ t("exam.averages") }}
    </h1>
    <p class="page-sub">
      {{ fmtDate(averages.exam.exam_date) }} · {{ t("exam.attributionNote") }}
    </p>

    <div class="card">
      <h2>{{ t("exam.trendTitle") }}</h2>
      <p class="page-sub" style="margin-top: 0">{{ t("exam.trendSub") }}</p>
      <LineChart
        v-if="trendChart"
        :labels="trendChart.labels"
        :series="trendChart.series"
        :y-max="trendChart.yMax"
        :highlight-index="trendChart.highlightIndex"
      />
    </div>

    <div class="stat-grid">
      <div v-for="s in averages.school" :key="s.subject" class="stat">
        <div class="stat-label">{{ subject(s.subject) }}</div>
        <div class="stat-value">{{ s.avg }}</div>
        <div class="stat-sub">
          {{ t("exam.outOf") }} {{ s.full_score }} ({{ pct(s.avg, s.full_score) }}%) ·
          {{ t("exam.students", { count: s.count }) }} ·
          {{ t("exam.min") }} {{ s.min }} · {{ t("exam.max") }} {{ s.max }}
        </div>
      </div>
    </div>

    <div class="card">
      <h2>{{ t("exam.perClass") }}</h2>
      <table>
        <thead>
          <tr>
            <th>{{ t("th.class") }}</th>
            <th v-for="subj in subjects" :key="subj">{{ subject(subj) }} {{ t("exam.avg") }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in classRows" :key="row.label">
            <td><span class="badge">{{ row.label }}</span></td>
            <td v-for="subj in subjects" :key="subj">
              <template v-if="row.cells[subj]">
                <strong>{{ row.cells[subj].avg }}</strong>
                <span class="page-sub" style="margin: 0">
                  ({{ t("exam.students", { count: row.cells[subj].count }) }})
                </span>
              </template>
              <template v-else>{{ t("common.none") }}</template>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </template>
</template>
