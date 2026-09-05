<script setup>
// 事件：只显示我（当前登录老师）参与的事件，按时间倒序排列，点学生名直达他的时间线。
// 考试没有单一学生，主文案直接显示考试名。
import { onMounted, ref } from "vue"
import Icon from "../components/Icon.vue"
import PageHeader from "../components/PageHeader.vue"
import AsyncState from "../components/AsyncState.vue"
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

const records = ref([])
const error = ref("")
const loading = ref(true)

async function load() {
  loading.value = true
  error.value = ""
  try {
    records.value = await api.get("/records")
  } catch (e) {
    error.value = friendlyError(e)
  } finally {
    loading.value = false
  }
}
onMounted(load)

function fmtDate(ts) {
  return new Date(ts).toLocaleDateString(dateLocale(), {
    year: "numeric",
    month: "short",
    day: "numeric",
  })
}
</script>

<template>
  <PageHeader
    :title="t('records.title')"
    :subtitle="t('records.subtitle', { count: records.length })"
  />

  <AsyncState
    :loading="loading"
    :error="error"
    :empty="!loading && !records.length"
    :empty-title="t('records.emptyTitle')"
    :empty-desc="t('records.emptyDesc')"
    empty-icon="checklist"
    :rows="5"
    @retry="load"
  >
    <div class="card">
      <div class="card__body card__body--tight">
        <div class="feed">
          <div v-for="r in records" :key="r.id" class="feed__item">
            <span class="feed__dot" :style="{ background: eventTypeColor(r.event_type) }">
              <Icon :name="eventTypeIcon(r.event_type)" :size="13" />
            </span>
            <div class="feed__body">
              <div class="feed__head">
                <span>
                  <router-link v-if="r.student_id" :to="`/students/${r.student_id}`">{{ r.student_name }}</router-link>
                  <template v-else>{{ r.title }}</template>
                  · {{ eventTypeLabel(r.event_type) }}
                  <template v-if="r.actor"> · {{ r.actor }}</template>
                </span>
                <time class="timeline__time">{{ fmtDate(r.occurred_at) }}</time>
              </div>
              <p class="feed__desc">{{ describeEvent(r.event_type, r.payload) }}</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  </AsyncState>
</template>
