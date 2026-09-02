<script setup>
import Icon from "./Icon.vue"
import { describeEvent, eventTypeColor, eventTypeIcon, eventTypeLabel } from "../strings"

const props = defineProps({
  events: { type: Array, default: () => [] },
  clickable: { type: Boolean, default: false },
})
const emit = defineEmits(["select"])

function fmt(ts) {
  return new Date(ts).toLocaleString("zh-CN", {
    year: "numeric", month: "short", day: "numeric",
    hour: "2-digit", minute: "2-digit",
  })
}
function isClickableItem(e) {
  if (!props.clickable) return false
  // Only manually-created events (non-system, has actor_teacher_id path) are editable.
  // Also treat events with no is_system field as potentially clickable (be defensive).
  if (e.is_system === true) return false
  return true
}
function handleClick(e) {
  if (isClickableItem(e)) emit("select", e)
}
</script>

<template>
  <ol v-if="events.length" class="timeline">
    <li
      v-for="e in events"
      :key="e.id"
      class="timeline-item"
      :class="{ clickable: isClickableItem(e) }"
      @click="handleClick(e)"
    >
      <span class="timeline-dot" :style="{ background: eventTypeColor(e.event_type) }">
        <Icon :name="eventTypeIcon(e.event_type)" :size="15" />
      </span>
      <div class="timeline-card">
        <div class="timeline-head">
          <strong>{{ eventTypeLabel(e.event_type) }}</strong>
          <span v-if="e.actor" class="timeline-actor">{{ e.actor }}</span>
        </div>
        <p class="timeline-desc">{{ describeEvent(e.event_type, e.payload) }}</p>
        <time class="timeline-time">{{ fmt(e.occurred_at) }}</time>
      </div>
    </li>
  </ol>
  <p v-else class="empty">No events yet.</p>
</template>
