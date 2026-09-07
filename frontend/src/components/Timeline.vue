<script setup>
import { computed } from "vue"
import { useRouter } from "vue-router"
import Icon from "./Icon.vue"
import { openEvent, isEventClickable } from "../eventNav"
import { describeEvent, eventTypeColor, eventTypeIcon, eventTypeLabel, t } from "../strings"

const props = defineProps({
  events: { type: Array, default: () => [] },
  studentId: { type: [String, Number], default: null },
})
const router = useRouter()

function eventTime(e) {
  return new Date(e.occurred_at).getTime()
}

function dayBounds() {
  const start = new Date()
  start.setHours(0, 0, 0, 0)
  const end = new Date()
  end.setHours(23, 59, 59, 999)
  return { start: start.getTime(), end: end.getTime() }
}

function sortAsc(a, b) {
  return eventTime(a) - eventTime(b)
}

function sortDesc(a, b) {
  return eventTime(b) - eventTime(a)
}

const timelineView = computed(() => {
  const { start, end } = dayBounds()
  const past = []
  const today = []
  const future = []

  for (const event of props.events) {
    const when = eventTime(event)
    if (when > end) future.push(event)
    else if (when >= start) today.push(event)
    else past.push(event)
  }

  future.sort(sortAsc)
  today.sort(sortAsc)
  past.sort(sortDesc)

  const rows = []
  for (const event of future) rows.push({ kind: "event", key: event.id, event })
  rows.push({ kind: "today", key: "today" })
  for (const event of today) rows.push({ kind: "event", key: event.id, event })
  for (const event of past) rows.push({ kind: "event", key: event.id, event })

  return { rows }
})

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
    <ol class="timeline">
      <template v-for="rowItem in timelineView.rows" :key="rowItem.key">
        <li v-if="rowItem.kind === 'today'" class="timeline__item timeline__item--today">
          <span class="timeline__dot timeline__dot--today">
            <Icon name="calendar" :size="15" />
          </span>
          <div class="timeline__card timeline__card--today">
            <span class="timeline__title">{{ t("detail.timelineToday") }}</span>
          </div>
        </li>
        <li
          v-else
          class="timeline__item"
          :class="{ 'is-clickable': isEventClickable(row(rowItem.event)) }"
          :tabindex="isEventClickable(row(rowItem.event)) ? 0 : undefined"
          :role="isEventClickable(row(rowItem.event)) ? 'button' : undefined"
          :aria-label="
            isEventClickable(row(rowItem.event))
              ? `查看这条${eventTypeLabel(rowItem.event.event_type, rowItem.event.payload)}记录`
              : undefined
          "
          @click="open(rowItem.event)"
          @keydown.enter.prevent="open(rowItem.event)"
          @keydown.space.prevent="open(rowItem.event)"
        >
          <span
            class="timeline__dot"
            :style="{ background: eventTypeColor(rowItem.event.event_type) }"
          >
            <Icon :name="eventTypeIcon(rowItem.event.event_type)" :size="15" />
          </span>
          <div class="timeline__card">
            <div class="timeline__head">
              <span class="timeline__title">{{
                eventTypeLabel(rowItem.event.event_type, rowItem.event.payload)
              }}</span>
              <span v-if="rowItem.event.actor" class="timeline__actor">{{ rowItem.event.actor }}</span>
            </div>
            <p class="timeline__desc">
              {{ describeEvent(rowItem.event.event_type, rowItem.event.payload) }}
            </p>
            <time class="timeline__time">{{ fmt(rowItem.event.occurred_at) }}</time>
          </div>
        </li>
      </template>
    </ol>
  </div>
</template>
