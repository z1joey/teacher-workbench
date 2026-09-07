<script setup>
import { useRouter } from "vue-router"
import Icon from "./Icon.vue"
import { openEvent, isEventClickable } from "../eventNav"
import { describeEvent, eventTypeColor, eventTypeIcon, eventTypeLabel } from "../strings"

const props = defineProps({
  events: { type: Array, default: () => [] },
  studentId: { type: [String, Number], default: null },
})
const router = useRouter()

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
  <ol v-if="events.length" class="timeline">
    <li
      v-for="e in events"
      :key="e.id"
      class="timeline__item"
      :class="{ 'is-clickable': isEventClickable(row(e)) }"
      :tabindex="isEventClickable(row(e)) ? 0 : undefined"
      :role="isEventClickable(row(e)) ? 'button' : undefined"
      :aria-label="isEventClickable(row(e)) ? `查看这条${eventTypeLabel(e.event_type)}记录` : undefined"
      @click="open(e)"
      @keydown.enter.prevent="open(e)"
      @keydown.space.prevent="open(e)"
    >
      <span class="timeline__dot" :style="{ background: eventTypeColor(e.event_type) }">
        <Icon :name="eventTypeIcon(e.event_type)" :size="15" />
      </span>
      <div class="timeline__card">
        <div class="timeline__head">
          <span class="timeline__title">{{ eventTypeLabel(e.event_type) }}</span>
          <span v-if="e.actor" class="timeline__actor">{{ e.actor }}</span>
        </div>
        <p class="timeline__desc">{{ describeEvent(e.event_type, e.payload) }}</p>
        <time class="timeline__time">{{ fmt(e.occurred_at) }}</time>
      </div>
    </li>
  </ol>
</template>
