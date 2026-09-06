<script setup>
// 家访：我参与的家访记录，按时间倒序。家访常常带着「下次再确认」的承诺，
// 所以待跟进的可以直接筛出来，不用靠翻聊天记录回忆。
import { computed, onMounted, ref } from "vue"
import Icon from "../components/Icon.vue"
import PageHeader from "../components/PageHeader.vue"
import AsyncState from "../components/AsyncState.vue"
import api from "../api"
import { dateLocale, eventTypeColor, friendlyError, t } from "../strings"

const visits = ref([])
const error = ref("")
const loading = ref(true)
const filter = ref("all") // all | followUps

async function load() {
  loading.value = true
  error.value = ""
  try {
    visits.value = await api.get("/events?type=home_visited")
  } catch (e) {
    error.value = friendlyError(e)
  } finally {
    loading.value = false
  }
}
onMounted(load)

const shown = computed(() =>
  filter.value === "followUps"
    ? visits.value.filter((v) => v.payload?.follow_up)
    : visits.value,
)
const visitedStudents = computed(
  () => new Set(visits.value.map((v) => v.student_id).filter(Boolean)).size,
)
const followUpCount = computed(() => visits.value.filter((v) => v.payload?.follow_up).length)

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
    :title="t('visits.title')"
    :subtitle="t('visits.subtitle', { count: visits.length, students: visitedStudents })"
  >
    <template #actions>
      <router-link to="/students">
        <button class="btn"><Icon name="plus" :size="15" /> {{ t("visits.record") }}</button>
      </router-link>
    </template>
  </PageHeader>

  <AsyncState
    :loading="loading"
    :error="error"
    :empty="!loading && !visits.length"
    :empty-title="t('visits.emptyTitle')"
    :empty-desc="t('visits.emptyDesc')"
    empty-icon="map-pin"
    :rows="3"
    @retry="load"
  >
    <template #emptyAction>
      <router-link to="/students">
        <button class="btn btn--primary"><Icon name="users" :size="15" /> {{ t("visits.record") }}</button>
      </router-link>
    </template>

    <div v-if="followUpCount" class="segmented" role="tablist" style="margin-bottom: 16px">
      <button
        class="segmented__item"
        :class="{ 'is-active': filter === 'all' }"
        role="tab"
        :aria-selected="filter === 'all'"
        @click="filter = 'all'"
      >
        {{ t("visits.filterAll") }} {{ visits.length }}
      </button>
      <button
        class="segmented__item"
        :class="{ 'is-active': filter === 'followUps' }"
        role="tab"
        :aria-selected="filter === 'followUps'"
        @click="filter = 'followUps'"
      >
        {{ t("visits.filterFollowUps") }} {{ followUpCount }}
      </button>
    </div>

    <div class="card">
      <div class="card__body card__body--tight">
        <div class="feed">
          <div v-for="v in shown" :key="v.id" class="feed__item">
            <span class="feed__dot" :style="{ background: eventTypeColor('home_visited') }">
              <Icon name="map-pin" :size="13" />
            </span>
            <div class="feed__body">
              <div class="feed__head">
                <span>
                  <router-link v-if="v.student_id" :to="`/students/${v.student_id}`">{{ v.student_name }}</router-link>
                  <template v-if="v.payload?.guardian"> · {{ v.payload.guardian }}</template>
                  <span v-if="v.payload?.follow_up" class="pill pill--warn" style="margin-left: 8px">
                    {{ t("visits.followUp") }}
                  </span>
                </span>
                <time class="timeline__time">{{ fmtDate(v.occurred_at) }}</time>
              </div>
              <p class="feed__desc">{{ v.payload?.summary }}</p>
              <p v-if="v.payload?.follow_up" class="feed__desc" style="color: var(--warn)">
                {{ v.payload.follow_up }}
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  </AsyncState>
</template>
