<script setup>
import { ref, computed, onMounted } from "vue"
import api from "../api"
import Icon from "../components/Icon.vue"
import {
  dateLocale,
  describeEvent,
  eventTypeColor,
  eventTypeIcon,
  eventTypeLabel,
  t,
} from "../strings"

const data = ref(null)
const error = ref("")

onMounted(async () => {
  try {
    data.value = await api.get("/dashboard")
  } catch (e) {
    error.value = e.message
  }
})

const today = computed(() =>
  new Date().toLocaleDateString(dateLocale(), {
    weekday: "long", year: "numeric", month: "long", day: "numeric",
  })
)

function fmtDate(ts) {
  return new Date(ts).toLocaleDateString(dateLocale(), {
    year: "numeric", month: "short", day: "numeric",
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

const stats = computed(() => {
  if (!data.value) return []
  const c = data.value.counts
  return [
    { label: t("home.statStudents"), value: c.students },
    { label: t("home.statClasses"), value: c.classes },
    { label: t("home.statExams"), value: c.exams },
    { label: t("home.statVisits"), value: c.home_visits },
  ]
})
</script>

<template>
  <p v-if="error" class="error-text">{{ error }}</p>
  <p v-else-if="!data" class="empty">{{ t("common.loading") }}</p>

  <template v-else>
    <h1>{{ t("home.greeting", { name: data.teacher.name }) }}</h1>
    <p class="page-sub">{{ t("home.today", { date: today }) }}</p>

    <div class="stat-grid">
      <div v-for="s in stats" :key="s.label" class="stat">
        <div class="stat-label">{{ s.label }}</div>
        <div class="stat-value">{{ s.value }}</div>
      </div>
    </div>

    <div class="two-col">
      <div class="card">
        <h2>{{ t("home.recentEvents") }}</h2>
        <div v-for="e in data.recent_events" :key="e.id" class="mini-event">
          <span class="mini-icon" :style="{ background: eventTypeColor(e.event_type) }">
            <Icon :name="eventTypeIcon(e.event_type)" :size="13" />
          </span>
          <div class="mini-body">
            <div class="mini-head">
              <span>
                <router-link :to="`/students/${e.student_id}`">{{ e.student_name }}</router-link>
                · {{ eventTypeLabel(e.event_type) }}
              </span>
              <time class="timeline-time">{{ fmtDate(e.occurred_at) }}</time>
            </div>
            <p class="mini-desc">{{ describeEvent(e.event_type, e.payload) }}</p>
          </div>
        </div>
      </div>

      <div>
        <div class="card">
          <h2>{{ t("home.countdown") }}</h2>
          <p v-if="!data.upcoming_exams.length" class="empty">{{ t("home.noCountdown") }}</p>
          <div v-for="e in data.upcoming_exams" :key="e.id" class="countdown-item">
            <div style="min-width: 0">
              <div style="font-weight: 600">{{ e.name }}</div>
              <div class="weakness-sub">
                {{ fmtDate(e.exam_date) }}
              </div>
            </div>
            <span class="badge" :class="daysUntil(e.exam_date) <= 1 ? 'warn' : ''">
              {{ countdownLabel(e.exam_date) }}
            </span>
          </div>
        </div>

        <div class="card">
          <h2>{{ t("home.followUps") }}</h2>
          <p v-if="!data.follow_ups.length" class="empty">{{ t("home.noFollowUps") }}</p>
          <div v-for="f in data.follow_ups" :key="`${f.student_id}-${f.visited_at}`" class="followup">
            <div>
              <router-link :to="`/students/${f.student_id}`">{{ f.student_name }}</router-link>
              · {{ f.purpose }}
            </div>
            <div class="weakness-sub">
              {{ t("home.followUpPrefix") }}: {{ f.follow_up_note || "…" }} · {{ fmtDate(f.visited_at) }}
            </div>
          </div>
        </div>
      </div>
    </div>
  </template>
</template>
