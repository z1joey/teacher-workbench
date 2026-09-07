<script setup>
// 家访：我参与的家访记录，按时间倒序。
import { computed, onMounted, ref } from "vue"
import Icon from "../components/Icon.vue"
import PageHeader from "../components/PageHeader.vue"
import AsyncState from "../components/AsyncState.vue"
import FeedEventItem from "../components/FeedEventItem.vue"
import api from "../api"
import { notify } from "../feedback"
import { homeVisitPatchBody } from "../homeVisit"
import { friendlyError, t } from "../strings"

const visits = ref([])
const error = ref("")
const loading = ref(true)
const markingId = ref("")

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

const visitedStudents = computed(
  () => new Set(visits.value.map((v) => v.student_id).filter(Boolean)).size,
)

async function markDone(v, e) {
  e?.stopPropagation()
  if (!v.student_id || v.payload?.done || markingId.value) return
  markingId.value = v.id
  try {
    await api.patch(`/students/${v.student_id}/events/${v.id}`, homeVisitPatchBody(v.payload, true))
    v.payload = { ...(v.payload || {}), done: true }
    notify({ tone: "ok", title: t("visits.done"), timeout: 2400 })
  } catch (err) {
    notify({ tone: "error", title: friendlyError(err), timeout: 4000 })
  } finally {
    markingId.value = ""
  }
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

    <div class="card">
      <div class="card__body card__body--tight">
        <div class="feed">
          <FeedEventItem
            v-for="v in visits"
            :key="v.id"
            :event="v"
            student-first
            :show-type="false"
          >
            <template #actions>
              <button
                v-if="!v.payload?.done && v.student_id"
                type="button"
                class="btn btn--sm"
                :disabled="markingId === v.id"
                @click="markDone(v, $event)"
              >
                <span v-if="markingId === v.id" class="spinner" />
                {{ t("visits.markDone") }}
              </button>
            </template>
          </FeedEventItem>
        </div>
      </div>
    </div>
  </AsyncState>
</template>
