<script setup>
import { useRouter } from "vue-router"
import Icon from "./Icon.vue"
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

// 系统自动生成的记录（入学、转班、考试、生日）不可编辑 —— 只能看
function isEditable(e) {
  return e.is_system !== true && props.studentId != null
}

function open(e) {
  if (!isEditable(e)) return
  router.push(`/students/${props.studentId}/events/${e.id}`)
}
</script>

<template>
  <ol v-if="events.length" class="timeline">
    <li
      v-for="e in events"
      :key="e.id"
      class="timeline__item"
      :class="{ 'is-clickable': isEditable(e) }"
      :tabindex="isEditable(e) ? 0 : undefined"
      :role="isEditable(e) ? 'button' : undefined"
      :aria-label="isEditable(e) ? `编辑这条${eventTypeLabel(e.event_type)}记录` : undefined"
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
