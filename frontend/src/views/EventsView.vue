<script setup>
// 事件：普通事件（比赛、活动等），只显示我参与的，按时间倒序。
// 点任意一条进入事件详情，可编辑或删除；学生名直达他的档案。
// 考试、家访有各自的页面，不在这里出现。
import { onMounted, ref } from "vue"
import { useRouter } from "vue-router"
import Icon from "../components/Icon.vue"
import PageHeader from "../components/PageHeader.vue"
import AsyncState from "../components/AsyncState.vue"
import api from "../api"
import {
  dateLocale,
  eventTypeColor,
  eventTypeIcon,
  eventTypeLabel,
  friendlyError,
  t,
} from "../strings"

const router = useRouter()
const events = ref([])
const error = ref("")
const loading = ref(true)

async function load() {
  loading.value = true
  error.value = ""
  try {
    events.value = await api.get("/events?type=activity")
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
    :title="t('events.title')"
    :subtitle="t('events.subtitle', { count: events.length })"
  >
    <template #actions>
      <router-link to="/events/new">
        <button class="btn btn--primary"><Icon name="plus" :size="15" /> {{ t("events.create") }}</button>
      </router-link>
    </template>
  </PageHeader>

  <AsyncState
    :loading="loading"
    :error="error"
    :empty="!loading && !events.length"
    :empty-title="t('events.emptyTitle')"
    :empty-desc="t('events.emptyDesc')"
    empty-icon="flag"
    :rows="3"
    @retry="load"
  >
    <template #emptyAction>
      <router-link to="/events/new">
        <button class="btn btn--primary"><Icon name="plus" :size="15" /> {{ t("events.create") }}</button>
      </router-link>
    </template>

    <div class="card">
      <div class="card__body card__body--tight">
        <div class="feed">
          <div
            v-for="r in events"
            :key="r.id"
            class="feed__item"
            style="cursor: pointer"
            @click="router.push(`/events/${r.id}`)"
          >
            <span class="feed__dot" :style="{ background: eventTypeColor(r.event_type) }">
              <Icon :name="eventTypeIcon(r.event_type)" :size="13" />
            </span>
            <div class="feed__body">
              <div class="feed__head">
                <span>
                  {{ r.title }}
                  · {{ eventTypeLabel(r.event_type) }}
                  <template v-if="r.actor"> · {{ r.actor }}</template>
                </span>
                <time class="timeline__time">{{ fmtDate(r.occurred_at) }}</time>
              </div>
              <p v-if="r.payload?.notes" class="feed__desc">{{ r.payload.notes }}</p>
              <p v-if="r.students.length" class="feed__desc">
                <template v-for="(s, i) in r.students" :key="s.id">
                  <router-link :to="`/students/${s.id}`" @click.stop>{{ s.name }}</router-link><template v-if="i < r.students.length - 1">、</template>
                </template>
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  </AsyncState>
</template>
