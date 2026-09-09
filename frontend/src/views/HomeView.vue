<script setup>
// 首页 = 今天该做什么：日历、最新动态。
// 加载给骨架屏、失败给重试，不留空白也不甩一句「出错了」。
import { computed, onMounted, ref } from "vue"
import Icon from "../components/Icon.vue"
import PageHeader from "../components/PageHeader.vue"
import AsyncState from "../components/AsyncState.vue"
import MonthCalendar from "../components/MonthCalendar.vue"
import FeedEventItem from "../components/FeedEventItem.vue"
import api from "../api"
import { dateLocale, friendlyError, t } from "../strings"

const dashboard = ref(null)
const error = ref("")
const loading = ref(true)

async function load() {
  loading.value = true
  error.value = ""
  try {
    dashboard.value = await api.get("/dashboard")
  } catch (e) {
    dashboard.value = null
    error.value = friendlyError(e)
  } finally {
    loading.value = false
  }
}
onMounted(load)

const today = computed(() =>
  new Date().toLocaleDateString(dateLocale(), {
    weekday: "long",
    year: "numeric",
    month: "long",
    day: "numeric",
  })
)
</script>

<template>
  <AsyncState
    :loading="loading"
    :error="error"
    :empty="!loading && !error && !dashboard"
    empty-title="首页内容没能加载"
    empty-desc="请检查网络连接后重试。"
    :rows="4"
    @retry="load"
  >
    <PageHeader
      :title="t('home.greeting', { name: dashboard.user.display_name || dashboard.user.name })"
      :subtitle="t('home.today', { date: today })"
    />

    <div class="split">
      <div>
        <MonthCalendar />
      </div>

      <!-- 最新动态 -->
      <div class="card">
        <div class="card__head">
          <div>
            <h2 class="card__title"><Icon name="trending" :size="16" /> {{ t("home.recentEvents") }}</h2>
            <p class="card__desc">{{ t("home.recentEventsSub") }}</p>
          </div>
        </div>
        <div class="card__body card__body--tight">
          <div v-if="!dashboard.recent_events.length" class="state state--in-card">
            <p class="state__desc">{{ t("home.noRecentEvents") }}</p>
          </div>
          <div v-else class="feed">
            <FeedEventItem v-for="e in dashboard.recent_events" :key="e.id" :event="e" />
          </div>
        </div>
      </div>
    </div>
  </AsyncState>
</template>
