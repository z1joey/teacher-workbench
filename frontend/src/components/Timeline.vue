<script setup>
// 时间线：左侧竖轴，日期在图标左侧。
import { computed } from "vue"
import { useRouter } from "vue-router"
import Icon from "./Icon.vue"
import { openEvent, isEventClickable } from "../eventNav"
import {
  dateLocale,
  describeEvent,
  eventDisplayName,
  eventTypeColor,
  eventTypeIcon,
} from "../strings"

const props = defineProps({
  events: { type: Array, default: () => [] },
  studentId: { type: [String, Number], default: null },
})
const router = useRouter()

function eventTime(e) {
  return new Date(e.occurred_at).getTime()
}

const timelineEntries = computed(() => {
  const sorted = [...props.events].sort((a, b) => eventTime(b) - eventTime(a))
  const todayKey = dayStart(Date.now())
  return sorted.map((event) => ({
    event,
    isToday: dayStart(eventTime(event)) === todayKey,
    monthDay: monthDayLabel(eventTime(event)),
    title: eventDisplayName(event),
    desc: timelineDesc(event),
    icon: eventTypeIcon(event.event_type),
    color: eventTypeColor(event.event_type),
  }))
})

function dayStart(ts) {
  const d = new Date(ts)
  d.setHours(0, 0, 0, 0)
  return d.getTime()
}

function monthDayLabel(ts) {
  const d = new Date(ts)
  return d.toLocaleDateString(dateLocale(), { month: "numeric", day: "numeric" })
}

const NO_TIMELINE_DESC = new Set(["exam", "birthday"])

function timelineDesc(event) {
  // exam 节点默认不展示描述；学生档案页会在有成绩时带上 score_summary
  if (event.score_summary) return event.score_summary
  if (NO_TIMELINE_DESC.has(event.event_type)) return ""
  return describeEvent(event.event_type, event.payload)
}

function row(e) {
  return { ...e, student_id: props.studentId }
}

function open(event) {
  openEvent(router, row(event))
}
</script>

<template>
  <div v-if="events.length" class="timeline-rail">
    <article
      v-for="entry in timelineEntries"
      :key="entry.event.id"
      class="timeline-node"
      :class="{
        'timeline-node--today': entry.isToday,
        'timeline-node--title-only': !entry.desc,
        'is-clickable': isEventClickable(row(entry.event)),
      }"
      :tabindex="isEventClickable(row(entry.event)) ? 0 : undefined"
      :role="isEventClickable(row(entry.event)) ? 'button' : undefined"
      @click="open(entry.event)"
      @keydown.enter.prevent="open(entry.event)"
      @keydown.space.prevent="open(entry.event)"
    >
      <div class="timeline-node__marker">
        <time class="timeline-node__axis-date tnum" :datetime="entry.event.occurred_at">
          {{ entry.monthDay }}
        </time>
        <span
          class="timeline-node__icon"
          :style="{ '--event-color': entry.color }"
        >
          <Icon :name="entry.icon" :size="16" />
        </span>
      </div>
      <div class="timeline-node__body">
        <h3 class="timeline-node__title">{{ entry.title }}</h3>
        <p v-if="entry.desc" class="timeline-node__desc">{{ entry.desc }}</p>
      </div>
    </article>
  </div>
</template>
