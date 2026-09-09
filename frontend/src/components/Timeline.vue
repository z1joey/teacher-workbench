<script setup>
// 时间线按天分组：一天一个容器，组内最新在前；
// 未来的日期排在今天上方（越近越靠下），过去的日子按越近越前排列；
// 今天的容器用底色强调。
import { computed } from "vue"
import { useRouter } from "vue-router"
import Icon from "./Icon.vue"
import { openEvent, isEventClickable } from "../eventNav"
import {
  dateLocale,
  describeEvent,
  eventTitle,
  eventTypeColor,
  eventTypeIcon,
  eventTypeLabel,
  t,
} from "../strings"

const props = defineProps({
  events: { type: Array, default: () => [] },
  studentId: { type: [String, Number], default: null },
})
const router = useRouter()

function eventTime(e) {
  return new Date(e.occurred_at).getTime()
}

function dayStart(ts) {
  const d = new Date(ts)
  d.setHours(0, 0, 0, 0)
  return d.getTime()
}

const timelineView = computed(() => {
  const todayKey = dayStart(Date.now())
  const byDay = new Map()
  for (const event of props.events) {
    const key = dayStart(eventTime(event))
    if (!byDay.has(key)) byDay.set(key, [])
    byDay.get(key).push(event)
  }

  const groups = [...byDay.entries()].map(([key, events]) => ({
    key,
    events,
    isToday: key === todayKey,
    isFuture: key > todayKey,
  }))
  // 组间：未来日期升序在前，其后是今天，过去的日子越近越前
  groups.sort((a, b) => {
    const rank = (g) => (g.isToday ? 0 : g.isFuture ? -1 : 1)
    if (rank(a) !== rank(b)) return rank(a) - rank(b)
    return a.isFuture ? a.key - b.key : b.key - a.key
  })
  // 组内：最新的事件在最上面
  for (const g of groups) g.events.sort((a, b) => eventTime(b) - eventTime(a))
  for (const g of groups) g.label = dayLabel(g.key, todayKey)
  return { groups }
})

function dayLabel(key, todayKey) {
  const diff = Math.round((key - todayKey) / 86_400_000)
  const d = new Date(key)
  const sameYear = d.getFullYear() === new Date().getFullYear()
  const date = d.toLocaleDateString(dateLocale(), {
    ...(sameYear ? {} : { year: "numeric" }),
    month: "short",
    day: "numeric",
    weekday: "short",
  })
  if (diff === 0) return `今天 · ${date}`
  if (diff === 1) return `明天 · ${date}`
  if (diff === -1) return `昨天 · ${date}`
  return date
}

function fmt(ts) {
  return new Date(ts).toLocaleString("zh-CN", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  })
}

function row(e) {
  return { ...e, student_id: props.studentId }
}

function open(e) {
  openEvent(router, row(e))
}
</script>

<template>
  <div v-if="events.length">
    <section
      v-for="group in timelineView.groups"
      :key="group.key"
      class="timeline__day"
      :class="{ 'timeline__day--today': group.isToday }"
    >
      <div class="timeline__day-head">
        <span class="timeline__day-label">{{ group.label }}</span>
        <span class="timeline__day-count">{{ group.events.length }} 条</span>
      </div>
      <ol class="timeline">
        <li
          v-for="event in group.events"
          :key="event.id"
          class="timeline__item"
          :class="{ 'is-clickable': isEventClickable(row(event)) }"
          :tabindex="isEventClickable(row(event)) ? 0 : undefined"
          :role="isEventClickable(row(event)) ? 'button' : undefined"
          :aria-label="
            isEventClickable(row(event))
              ? `查看这条${eventTypeLabel(event.event_type, event.payload)}记录`
              : undefined
          "
          @click="open(event)"
          @keydown.enter.prevent="open(event)"
          @keydown.space.prevent="open(event)"
        >
          <span
            class="timeline__dot"
            :style="{ background: eventTypeColor(event.event_type) }"
          >
            <Icon :name="eventTypeIcon(event.event_type)" :size="15" />
          </span>
          <div class="timeline__card">
            <div class="timeline__head">
              <span class="timeline__title">{{
                eventTitle(event.event_type, event.payload)
              }}</span>
              <span v-if="event.actor" class="timeline__actor">{{ event.actor }}</span>
            </div>
            <p v-if="describeEvent(event.event_type, event.payload)" class="timeline__desc">
              {{ describeEvent(event.event_type, event.payload) }}
            </p>
            <time class="timeline__time">{{ fmt(event.occurred_at) }}</time>
          </div>
        </li>
      </ol>
    </section>
  </div>
</template>
