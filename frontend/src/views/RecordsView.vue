<script setup>
import { ref, onMounted } from "vue"
import Icon from "../components/Icon.vue"
import api from "../api"
import {
  dateLocale,
  describeEvent,
  eventTypeColor,
  eventTypeIcon,
  eventTypeLabel,
  t,
} from "../strings"

const records = ref([])
const error = ref("")
const loading = ref(true)

onMounted(async () => {
  try {
    records.value = await api.get("/records")
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
})

function fmtDate(ts) {
  return new Date(ts).toLocaleDateString(dateLocale(), {
    year: "numeric", month: "short", day: "numeric",
  })
}
</script>

<template>
  <p v-if="error" class="error-text">{{ error }}</p>
  <p v-else-if="loading" class="empty">{{ t("common.loading") }}</p>

  <template v-else>
    <h1>{{ t("records.title") }}</h1>
    <p class="page-sub">{{ t("records.subtitle", { count: records.length }) }}</p>

    <div class="card">
      <p v-if="!records.length" class="empty">{{ t("records.empty") }}</p>
      <div v-for="r in records" :key="r.id" class="mini-event">
        <span class="mini-icon" :style="{ background: eventTypeColor(r.event_type) }">
          <Icon :name="eventTypeIcon(r.event_type)" :size="13" />
        </span>
        <div class="mini-body">
          <div class="mini-head">
            <span>
              <router-link :to="`/students/${r.student_id}`">{{ r.student_name }}</router-link>
              · {{ eventTypeLabel(r.event_type) }}<template v-if="r.actor"> · {{ r.actor }}</template>
            </span>
            <time class="timeline-time">{{ fmtDate(r.occurred_at) }}</time>
          </div>
          <p class="mini-desc">{{ describeEvent(r.event_type, r.payload) }}</p>
        </div>
      </div>
    </div>
  </template>
</template>
