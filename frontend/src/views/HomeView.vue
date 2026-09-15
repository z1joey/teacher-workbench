<script setup>
// 首页 = 今天该做什么：日历、最新动态。
// 加载给骨架屏、失败给重试，不留空白也不甩一句「出错了」。
import { computed, onMounted, ref } from "vue"
import Icon from "../components/Icon.vue"
import PageHeader from "../components/PageHeader.vue"
import AsyncState from "../components/AsyncState.vue"
import MonthCalendar from "../components/MonthCalendar.vue"
import FeedEventItem from "../components/FeedEventItem.vue"
import api from "../api"
import { dateLocale, formatDateRange, friendlyError, t, todayStr } from "../strings"

const dashboard = ref(null)
const error = ref("")
const loading = ref(true)

async function load() {
  loading.value = true
  error.value = ""
  try {
    dashboard.value = await api.get("/dashboard")
  } catch (e) {
    dashboard.value = null
    error.value = friendlyError(e)
  } finally {
    loading.value = false
  }
}
onMounted(load)

const today = computed(() =>
  new Date().toLocaleDateString(dateLocale(), {
    weekday: "long",
    year: "numeric",
    month: "long",
    day: "numeric",
  })
)

// 只消费 /dashboard 已有的 counts 字段，缺的不编造
const stats = computed(() => {
  const c = dashboard.value?.counts || {}
  return [
    ["students", t("home.statStudents")],
    ["classes", t("home.statClasses")],
    ["exams", t("home.statExams")],
    ["interactions", t("home.statInteractions")],
  ]
    .filter(([key]) => typeof c[key] === "number")
    .map(([key, label]) => ({ label, value: c[key] }))
})

// 待办感（方案 A）：今日 / 临近考试用粉笔色标记 —— 危险红只留给真正的问题态
function urgency(exam) {
  const start = exam.exam_date
  if (!start) return ""
  if (start <= todayStr() && (!exam.end_date || todayStr() <= exam.end_date)) return "today"
  const days = (new Date(start) - new Date(todayStr())) / 86400000
  return 0 < days && days <= 3 ? "soon" : ""
}
</script>

<template>
  <AsyncState
    :loading="loading"
    :error="error"
    :empty="!loading && !error && !dashboard"
    :empty-title="t('home.loadEmptyTitle')"
    :empty-desc="t('home.loadEmptyDesc')"
    :rows="4"
    @retry="load"
  >
    <PageHeader
      :title="t('home.greeting', { name: dashboard.user.display_name || dashboard.user.name })"
      :subtitle="t('home.today', { date: today })"
    >
      <template #actions>
        <!-- 高频入口：只链已有路由，admin 用户被守卫挡在首页之外，天然不可见 -->
        <router-link :to="{ name: 'exams' }"><button class="btn btn--primary">{{ t("nav.exams") }}</button></router-link>
        <router-link :to="{ name: 'students' }"><button class="btn">{{ t("nav.students") }}</button></router-link>
        <router-link :to="{ name: 'visits' }"><button class="btn">{{ t("visits.title") }}</button></router-link>
      </template>
    </PageHeader>

    <div v-if="stats.length" class="stat-grid">
      <div v-for="s in stats" :key="s.label" class="stat">
        <div class="stat__label">{{ s.label }}</div>
        <div class="stat__value">{{ s.value }}</div>
      </div>
    </div>

    <!-- 即将考试（/dashboard upcoming_exams） -->
    <div class="card">
      <div class="card__head">
        <div>
          <h2 class="card__title">
            <Icon name="clipboard" :size="16" /> {{ t("home.upcoming") }}
            <span v-if="dashboard.upcoming_exams.length" class="pill pill--count">{{
              dashboard.upcoming_exams.length
            }}</span>
          </h2>
          <p class="card__desc">{{ t("home.upcomingSub") }}</p>
        </div>
      </div>
      <div class="card__body card__body--tight">
        <div v-if="!dashboard.upcoming_exams.length" class="state state--in-card">
          <p class="state__desc">{{ t("home.upcomingEmpty") }}</p>
        </div>
        <ul v-else class="stack">
          <li v-for="exam in dashboard.upcoming_exams" :key="exam.id">
            <router-link
              v-if="exam.id"
              class="row-link"
              :to="{ name: 'examDetail', params: { id: exam.id } }"
            >
              <span class="row-link__name">{{ exam.name }}</span>
              <span class="row-link__meta">
                <span v-if="urgency(exam) === 'today'" class="pill">{{ t("home.upcomingToday") }}</span>
                <span v-else-if="urgency(exam) === 'soon'" class="pill pill--outline">{{ t("home.upcomingSoon") }}</span>
                {{ formatDateRange(exam.exam_date, exam.end_date) }}
              </span>
            </router-link>
            <div v-else class="row-link row-link--static">
              <span class="row-link__name">{{ exam.name }}</span>
              <span class="row-link__meta">{{ formatDateRange(exam.exam_date, exam.end_date) }}</span>
            </div>
          </li>
        </ul>
      </div>
    </div>

    <div class="split">
      <div>
        <MonthCalendar />
      </div>

      <!-- 最新动态 -->
      <div class="card">
        <div class="card__head">
          <div>
            <h2 class="card__title"><Icon name="trending" :size="16" /> {{ t("home.recentEvents") }}</h2>
            <p class="card__desc">{{ t("home.recentEventsSub") }}</p>
          </div>
        </div>
        <div class="card__body card__body--tight">
          <div v-if="!dashboard.recent_events.length" class="state state--in-card">
            <p class="state__desc">{{ t("home.noRecentEvents") }}</p>
          </div>
          <div v-else class="feed">
            <FeedEventItem v-for="e in dashboard.recent_events" :key="e.id" :event="e" stacked />
          </div>
        </div>
      </div>
    </div>
  </AsyncState>
</template>
