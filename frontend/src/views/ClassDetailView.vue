<script setup>
import { ref, computed, onMounted } from "vue"
import api from "../api"
import Icon from "../components/Icon.vue"
import LineChart from "../components/LineChart.vue"
import { genderLabel, subject, subjectColor, t } from "../strings"

const props = defineProps({ id: { type: String, required: true } })

const detail = ref(null)
const loading = ref(true)
const error = ref("")

onMounted(async () => {
  try {
    detail.value = await api.get(`/classes/${props.id}`)
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
})

const trendChart = computed(() => {
  if (!detail.value || !detail.value.trend.exams.length) return null
  const exams = detail.value.trend.exams
  const series = detail.value.trend.series.map((s) => ({
    key: s.subject,
    label: subject(s.subject),
    color: subjectColor(s.subject),
    values: s.values,
  }))
  const yMax = Math.max(100, ...detail.value.trend.series.map((s) => s.full_score || 0))
  return { labels: exams.map((e) => e.name), series, yMax }
})

const hasScores = computed(() => detail.value && detail.value.averages.length > 0)

function fmtPct(score, full) {
  return full ? Math.round((score / full) * 100) : 0
}
</script>

<template>
  <p v-if="error" class="error-text">{{ error }}</p>
  <p v-else-if="loading" class="empty">{{ t("common.loading") }}</p>

  <template v-else-if="detail">
    <router-link to="/classes" class="back-link"><Icon name="chevron-left" :size="14" /> {{ t("classdetail.back") }}</router-link>

    <div class="card" style="margin-top: 12px">
      <div class="profile-head">
        <div class="avatar">{{ detail.class.name.charAt(0) }}</div>
        <div>
          <h1 style="margin-bottom: 0">{{ detail.class.name }}</h1>
          <div class="profile-meta">
            <span class="badge">{{ detail.class.academic_year }}</span>
            <span>{{ t("classes.grade") }} {{ detail.class.grade_level }}</span>
            <span>{{ t("classes.homeroom") }}: {{ detail.class.homeroom_teacher || "—" }}</span>
            <span>{{ t("profile.studentsCount", { n: detail.students.length }) }}</span>
          </div>
        </div>
      </div>
    </div>

    <div class="two-col">
      <div>
        <div class="card">
          <h2>{{ t("classdetail.trendTitle") }}</h2>
          <p class="page-sub" style="margin-top: 0">{{ t("classdetail.trendSub") }}</p>
          <p v-if="!trendChart || !trendChart.series.length" class="empty">{{ t("classdetail.noScores") }}</p>
          <LineChart
            v-else
            :labels="trendChart.labels"
            :series="trendChart.series"
            :y-max="trendChart.yMax"
          />
        </div>

        <div class="card">
          <h2>{{ t("classdetail.roster") }}</h2>
          <div v-if="detail.students.length" class="student-chips">
            <router-link
              v-for="s in detail.students"
              :key="s.id"
              :to="`/students/${s.id}`"
              class="student-chip"
              :title="s.admission_no"
            >
              {{ s.name }} <span class="weakness-sub">{{ genderLabel(s.gender) }}</span>
            </router-link>
          </div>
          <p v-else class="empty">{{ t("classes.noStudents") }}</p>
        </div>
      </div>

      <div class="card">
        <h2>{{ t("classdetail.averages") }}</h2>
        <p v-if="!hasScores" class="empty">{{ t("classdetail.noScores") }}</p>
        <div v-for="a in detail.averages" :key="a.subject" class="stat" style="box-shadow: none; border: none; padding: 6px 0">
          <div class="stat-label">{{ subject(a.subject) }}</div>
          <div class="stat-value">{{ a.avg ?? "—" }}</div>
          <div class="stat-sub">
            {{ t("exam.outOf") }} {{ a.full_score }} ({{ fmtPct(a.avg, a.full_score) }}%) ·
            {{ t("exam.exams", { count: a.count }) }}
          </div>
        </div>
      </div>
    </div>
  </template>
</template>
