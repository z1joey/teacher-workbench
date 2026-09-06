<script setup>
// 普通事件详情：标题、时间、说明与参与者名单；可以编辑或删除。
import { onMounted, ref } from "vue"
import { useRouter } from "vue-router"
import Icon from "../components/Icon.vue"
import PageHeader from "../components/PageHeader.vue"
import AsyncState from "../components/AsyncState.vue"
import api from "../api"
import { ask } from "../confirm"
import { notify, runUndoable } from "../feedback"
import {
  dateLocale,
  eventTypeColor,
  eventTypeIcon,
  eventTypeLabel,
  friendlyError,
  t,
} from "../strings"

const props = defineProps({
  id: { type: String, required: true },
})
const router = useRouter()

const event = ref(null)
const loading = ref(true)
const error = ref("")
const notFound = ref(false)

async function load() {
  loading.value = true
  error.value = ""
  try {
    event.value = await api.get(`/events/${props.id}`)
  } catch (e) {
    if (/not found/i.test(e.message || "")) notFound.value = true
    else error.value = friendlyError(e)
  } finally {
    loading.value = false
  }
}
onMounted(load)

function fmtDate(ts) {
  return new Date(ts).toLocaleString(dateLocale(), {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  })
}

async function remove() {
  const ok = await ask({
    title: `删除「${event.value.title}」？`,
    consequences: ["事件会从所有参与者的记录中移除，删除后无法恢复。"],
    confirmLabel: t("action.delete"),
  })
  if (!ok) return

  const title = event.value.title
  runUndoable({
    title: `已删除「${title}」`,
    run: () => api.delete(`/events/${props.id}`),
    onDone: () => router.replace("/events"),
  })
}
</script>

<template>
  <!-- 事件已被删除：给一条明确的出路 -->
  <div v-if="notFound" class="nf-wrap">
    <div class="nf-board">
      <Icon name="alert" :size="30" />
      <p class="nf-title">{{ t("nf.eventGone") }}</p>
      <p class="nf-sub">{{ t("nf.eventGoneSub") }}</p>
    </div>
    <div class="nf-actions">
      <router-link to="/events">
        <button class="btn btn--primary">返回事件</button>
      </router-link>
    </div>
  </div>

  <template v-else>
    <PageHeader
      :title="event?.title ?? ''"
      :subtitle="eventTypeLabel(event?.event_type)"
    >
      <template #actions>
        <router-link :to="`/events/${props.id}/edit`">
          <button class="btn btn--sm"><Icon name="pencil" :size="13" /> {{ t("action.edit") }}</button>
        </router-link>
        <button class="btn btn--sm btn--danger" @click="remove">
          <Icon name="trash" :size="13" /> {{ t("action.delete") }}
        </button>
      </template>
    </PageHeader>

    <AsyncState :loading="loading" :error="error" :rows="3" @retry="load">
      <div class="card" style="max-width: 620px">
        <div class="card__body">
          <div class="row" style="gap: 12px; align-items: center">
            <span
              class="feed__dot"
              style="background: #0e7490; width: 30px; height: 30px; border-radius: 999px; display: inline-flex; align-items: center; justify-content: center"
            >
              <Icon :name="eventTypeIcon(event?.event_type)" :size="16" />
            </span>
            <div>
              <div class="row-wrap">
                <span class="pill pill--outline">{{ eventTypeLabel(event?.event_type) }}</span>
              </div>
              <p class="stat__sub" style="margin-top: 6px">
                <Icon name="calendar" :size="13" />
                {{ fmtDate(event?.occurred_at) }}
              </p>
            </div>
          </div>

          <div v-if="event?.notes" class="card card--nested" style="margin-top: 16px">
            <div class="card__body card__body--tight">
              <p class="section-title">说明</p>
              <p class="feed__desc">{{ event.notes }}</p>
            </div>
          </div>

          <div style="margin-top: 16px">
            <p class="section-title">
              参与学生 <span class="muted">（{{ event?.students.length }} 人）</span>
            </p>
            <p v-if="!event?.students.length" class="stat__sub">没有学生参与</p>
            <div v-else class="row-wrap" style="margin-top: 8px">
              <router-link
                v-for="s in event.students"
                :key="s.id"
                :to="`/students/${s.id}`"
                class="chip"
              >
                {{ s.name }}
              </router-link>
            </div>
          </div>
        </div>
      </div>
    </AsyncState>
  </template>
</template>
