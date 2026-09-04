<script setup>
// 首页 = 今天该做什么：日历、考试倒计时、待跟进、最新动态。
// 加载给骨架屏、失败给重试，不留空白也不甩一句「出错了」。
import { computed, onMounted, ref } from "vue"
import Icon from "../components/Icon.vue"
import PageHeader from "../components/PageHeader.vue"
import AsyncState from "../components/AsyncState.vue"
import MonthCalendar from "../components/MonthCalendar.vue"
import api from "../api"
import {
  dateLocale,
  describeEvent,
  eventTypeColor,
  eventTypeIcon,
  eventTypeLabel,
  friendlyError,
  t,
} from "../strings"

const data = ref(null)
const error = ref("")
const loading = ref(true)

async function load() {
  loading.value = true
  error.value = ""
  try {
    data.value = await api.get("/dashboard")
  } catch (e) {
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

function fmtDate(ts) {
  return new Date(ts).toLocaleDateString(dateLocale(), {
    year: "numeric",
    month: "short",
    day: "numeric",
  })
}

function daysUntil(d) {
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const target = new Date(`${d}T00:00:00`)
  return Math.round((target - today) / 86400000)
}

function countdownLabel(d) {
  const n = daysUntil(d)
  if (n <= 0) return t("home.examToday")
  if (n === 1) return t("home.examTomorrow")
  return t("home.inDays", { n })
}
</script>

<template>
  <AsyncState
    :loading="loading"
    :error="error"
    :rows="4"
    @retry="load"
  >
    <template v-if="data">
      <PageHeader
        :title="t('home.greeting', { name: data.user.name })"
        :subtitle="t('home.today', { date: today })"
      >
        <template #actions>
          <router-link to="/students">
            <button class="btn"><Icon name="users" :size="15" /> {{ t("nav.students") }}</button>
          </router-link>
          <router-link to="/exams/new">
            <button class="btn btn--primary"><Icon name="plus" :size="15" /> {{ t("exams.create") }}</button>
          </router-link>
        </template>
      </PageHeader>

      <div class="split">
        <div>
          <MonthCalendar />
        </div>

        <!-- 待跟进：学生工作的收件箱 -->
        <div class="card">
          <div class="card__head">
            <div>
              <h2 class="card__title"><Icon name="checklist" :size="16" /> {{ t("home.followUps") }}</h2>
              <p class="card__desc">{{ t("home.followUpsSub") }}</p>
            </div>
            <span class="pill pill--count">{{ data.follow_ups.length }}</span>
          </div>
          <div class="card__body card__body--tight">
            <p v-if="!data.follow_ups.length" class="state__desc" style="padding: 12px 8px; text-align: center">
              {{ t("home.noFollowUps") }}
            </p>
            <div v-for="f in data.follow_ups" :key="`${f.student_id}-${f.occurred_at}`" class="feed__item">
              <span class="feed__dot" :style="{ background: eventTypeColor(f.event_type) }">
                <Icon :name="eventTypeIcon(f.event_type)" :size="13" />
              </span>
              <div class="feed__body">
                <div class="feed__head">
                  <span>
                    <router-link :to="`/students/${f.student_id}`">{{ f.student_name }}</router-link>
                    · {{ eventTypeLabel(f.event_type) }}
                    <template v-if="f.purpose"> · {{ f.purpose }}</template>
                  </span>
                </div>
                <p class="feed__desc">
                  {{ t("home.followUpPrefix") }}: {{ f.follow_up_note || "…" }} · {{ fmtDate(f.occurred_at) }}
                </p>
              </div>
            </div>
          </div>
        </div>

        <!-- 最新动态 -->
        <div class="card" style="grid-column: 1 / -1">
          <div class="card__head">
            <div>
              <h2 class="card__title"><Icon name="trending" :size="16" /> {{ t("home.recentEvents") }}</h2>
              <p class="card__desc">{{ t("home.recentEventsSub") }}</p>
            </div>
            <router-link to="/records" class="btn btn--sm btn--ghost">
              {{ t("records.title") }} <Icon name="chevron-right" :size="13" />
            </router-link>
          </div>
          <div class="card__body card__body--tight">
            <div class="feed">
              <div v-for="e in data.recent_events" :key="e.id" class="feed__item">
                <span class="feed__dot" :style="{ background: eventTypeColor(e.event_type) }">
                  <Icon :name="eventTypeIcon(e.event_type)" :size="13" />
                </span>
                <div class="feed__body">
                  <div class="feed__head">
                    <span>
                      <router-link :to="`/students/${e.student_id}`">{{ e.student_name }}</router-link>
                      · {{ eventTypeLabel(e.event_type) }}
                    </span>
                    <time class="timeline__time">{{ fmtDate(e.occurred_at) }}</time>
                  </div>
                  <p class="feed__desc">{{ describeEvent(e.event_type, e.payload) }}</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 考试倒计时 -->
      <div class="card">
        <div class="card__head">
          <div>
            <h2 class="card__title"><Icon name="clock" :size="16" /> {{ t("home.countdown") }}</h2>
          </div>
        </div>
        <div class="card__body card__body--tight">
          <p v-if="!data.upcoming_exams.length" class="state__desc" style="padding: 12px 8px; text-align: center">
            {{ t("home.noCountdown") }}
          </p>
          <div class="grid grid--3">
            <router-link
              v-for="e in data.upcoming_exams"
              :key="e.id"
              :to="`/exams/${e.id}`"
              class="stat stat--link"
              style="margin: 0"
            >
              <div class="stat__label">{{ countdownLabel(e.exam_date) }}</div>
              <div class="stat__value" style="font-size: 18px">{{ e.name }}</div>
              <div class="stat__sub">{{ fmtDate(e.exam_date) }}</div>
            </router-link>
          </div>
        </div>
      </div>
    </template>
  </AsyncState>
</template>
