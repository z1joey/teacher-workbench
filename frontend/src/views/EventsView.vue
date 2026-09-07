<script setup>
// 事件：普通事件（比赛、活动等），只显示我参与的，按时间倒序。
// 点任意一条进入事件详情，可编辑或删除；学生名直达他的档案。
// 考试、家访有各自的页面，不在这里出现。
import { onMounted, ref } from "vue"
import Icon from "../components/Icon.vue"
import PageHeader from "../components/PageHeader.vue"
import AsyncState from "../components/AsyncState.vue"
import FeedEventItem from "../components/FeedEventItem.vue"
import api from "../api"
import { friendlyError, t } from "../strings"
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
          <FeedEventItem v-for="r in events" :key="r.id" :event="r" />
        </div>
      </div>
    </div>
  </AsyncState>
</template>
