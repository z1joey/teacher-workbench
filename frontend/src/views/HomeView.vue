<script setup>
// 首页 = 今天该做什么：日历、待跟进、最新动态。
// 加载给骨架屏、失败给重试，不留空白也不甩一句「出错了」。
import { computed, onMounted, ref } from "vue"
import { useRouter } from "vue-router"
import Icon from "../components/Icon.vue"
import PageHeader from "../components/PageHeader.vue"
import AsyncState from "../components/AsyncState.vue"
import MonthCalendar from "../components/MonthCalendar.vue"
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
import { isEventClickable, openEvent } from "../eventNav"

const router = useRouter()

const data = ref(null)
const error = ref("")
const loading = ref(true)

async function load() {
  loading.value = true
  error.value = ""
  try {
    data.value = await api.get("/dashboard")
  } catch (e) {
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

function fmtDate(ts) {
  return new Date(ts).toLocaleDateString(dateLocale(), {
    year: "numeric",
    month: "short",
    day: "numeric",
  })
}
</script>

<template>
  <AsyncState
    :loading="loading"
    :error="error"
    :rows="4"
    @retry="load"
  >
    <template v-if="data">
      <PageHeader
        :title="t('home.greeting', { name: data.user.name })"
        :subtitle="t('home.today', { date: today })"
      />

      <div class="split">
        <div>
          <MonthCalendar />
        </div>

        <!-- 待跟进：学生工作的收件箱 -->
        <div class="card">
          <div class="card__head">
            <div>
              <h2 class="card__title"><Icon name="checklist" :size="16" /> {{ t("home.followUps") }}</h2>
              <p class="card__desc">{{ t("home.followUpsSub") }}</p>
            </div>
            <span class="pill pill--count">{{ data.follow_ups.length }}</span>
          </div>
          <div class="card__body card__body--tight">
            <div v-if="!data.follow_ups.length" class="state state--in-card">
              <p class="state__desc">{{ t("home.noFollowUps") }}</p>
            </div>
            <div
              v-for="f in data.follow_ups"
              :key="`${f.student_id}-${f.occurred_at}`"
              class="feed__item"
              :class="{ 'feed__item--clickable': !!f.id }"
              @click="f.id && openEvent(router, { id: f.id, event_type: f.event_type, student_id: f.student_id, payload: { summary: f.summary, follow_up: f.follow_up_note } })"
            >
              <span class="feed__dot" :style="{ background: eventTypeColor(f.event_type) }">
                <Icon :name="eventTypeIcon(f.event_type)" :size="13" />
              </span>
              <div class="feed__body">
                <div class="feed__head">
                  <span>
                    <router-link :to="`/students/${f.student_id}`">{{ f.student_name }}</router-link>
                    · {{ eventTypeLabel(f.event_type) }}
                    <template v-if="f.purpose"> · {{ f.purpose }}</template>
                  </span>
                </div>
                <p class="feed__desc">
                  {{ t("home.followUpPrefix") }}: {{ f.follow_up_note || "…" }} · {{ fmtDate(f.occurred_at) }}
                </p>
              </div>
            </div>
          </div>
        </div>

        <!-- 最新动态 -->
        <div class="card" style="grid-column: 1 / -1">
          <div class="card__head">
            <div>
              <h2 class="card__title"><Icon name="trending" :size="16" /> {{ t("home.recentEvents") }}</h2>
              <p class="card__desc">{{ t("home.recentEventsSub") }}</p>
            </div>
          </div>
          <div class="card__body card__body--tight">
            <div class="feed">
              <!-- 按事件一行：单一学生的记录以学生名为首，多参与者显示标题和名单；
                   普通事件可点击进入详情 -->
              <div
                v-for="e in data.recent_events"
                :key="e.id"
                class="feed__item"
                :class="{ 'feed__item--clickable': isEventClickable(e) }"
                @click="openEvent(router, e)"
              >
                <span class="feed__dot" :style="{ background: eventTypeColor(e.event_type) }">
                  <Icon :name="eventTypeIcon(e.event_type)" :size="13" />
                </span>
                <div class="feed__body">
                  <div class="feed__head">
                    <span>
                      <router-link
                        v-if="e.students.length === 1"
                        :to="`/students/${e.students[0].id}`"
                      >{{ e.students[0].name }}</router-link>
                      <template v-else>{{ e.title }}</template>
                      · {{ eventTypeLabel(e.event_type) }}
                    </span>
                    <time class="timeline__time">{{ fmtDate(e.occurred_at) }}</time>
                  </div>
                  <p v-if="describeEvent(e.event_type, e.payload)" class="feed__desc">
                    {{ describeEvent(e.event_type, e.payload) }}
                  </p>
                  <p v-if="e.students.length > 1" class="feed__desc">
                    <template v-for="(s, i) in e.students" :key="s.id">
                      <router-link :to="`/students/${s.id}`" @click.stop>{{ s.name }}</router-link><template v-if="i < e.students.length - 1">、</template>
                    </template>
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>
  </AsyncState>
</template>
