<script setup>
// 首页月历：考试与跟进记录放在一起看；点日期展开列表，点记录进入详情页。
import { computed, onMounted, ref } from "vue"
import Icon from "./Icon.vue"
import FeedEventItem from "./FeedEventItem.vue"
import api from "../api"
import { dateLocale, eventTypeColor, friendlyError, t } from "../strings"

const WEEKDAYS = ["一", "二", "三", "四", "五", "六", "日"]
const mounted = new Date()
const todayISO = isoOf(mounted.getFullYear(), mounted.getMonth() + 1, mounted.getDate())

const year = ref(mounted.getFullYear())
const month = ref(mounted.getMonth() + 1) // 1-12
const items = ref([])
const nearTermItems = ref([])
const loading = ref(true)
const loadError = ref("")
const selectedDate = ref("")

function isoOf(y, m, d) {
  return `${y}-${String(m).padStart(2, "0")}-${String(d).padStart(2, "0")}`
}

function startOfWeek(d) {
  const copy = new Date(d)
  copy.setHours(12, 0, 0, 0)
  copy.setDate(copy.getDate() - ((copy.getDay() + 6) % 7))
  return copy
}

function addDays(d, days) {
  const copy = new Date(d)
  copy.setDate(copy.getDate() + days)
  return copy
}

function weekDates(start) {
  const dates = []
  for (let i = 0; i < 7; i++) {
    const d = addDays(start, i)
    dates.push(isoOf(d.getFullYear(), d.getMonth() + 1, d.getDate()))
  }
  return dates
}

async function loadNearTerm() {
  const start = startOfWeek(new Date())
  const seen = new Set()
  const fetches = []
  for (let i = 0; i < 14; i++) {
    const d = addDays(start, i)
    const y = d.getFullYear()
    const m = d.getMonth() + 1
    const key = `${y}-${m}`
    if (seen.has(key)) continue
    seen.add(key)
    fetches.push(api.get(`/calendar?year=${y}&month=${m}`))
  }
  const results = await Promise.all(fetches)
  nearTermItems.value = results.flatMap((r) => r.items)
}

async function load() {
  loading.value = true
  loadError.value = ""
  try {
    const [data] = await Promise.all([
      api.get(`/calendar?year=${year.value}&month=${month.value}`),
      loadNearTerm(),
    ])
    items.value = data.items
  } catch (e) {
    loadError.value = friendlyError(e)
  } finally {
    loading.value = false
  }
}

function shiftMonth(delta) {
  const m = month.value + delta
  if (m === 0) {
    year.value--
    month.value = 12
  } else if (m === 13) {
    year.value++
    month.value = 1
  } else month.value = m
  selectedDate.value = ""
  load()
}

function goToday() {
  year.value = mounted.getFullYear()
  month.value = mounted.getMonth() + 1
  selectedDate.value = todayISO
  load()
}

function selectDay(c) {
  selectedDate.value = selectedDate.value === c.iso ? "" : c.iso
}

onMounted(load)

const thisWeekStart = computed(() => startOfWeek(new Date(`${todayISO}T12:00:00`)))

function itemsInDates(dates) {
  const allowed = new Set(dates)
  const seen = new Set()
  const list = []
  for (const it of nearTermItems.value) {
    if (!allowed.has(it.date)) continue
    const key = `${it.kind}-${it.id}`
    if (seen.has(key)) continue
    seen.add(key)
    list.push(it)
  }
  return list.sort((a, b) => a.date.localeCompare(b.date))
}

const nearTermBlocks = computed(() =>
  [
    { key: "this", label: t("home.calNotifyThisWeek"), dates: weekDates(thisWeekStart.value) },
    {
      key: "next",
      label: t("home.calNotifyNextWeek"),
      dates: weekDates(addDays(thisWeekStart.value, 7)),
    },
  ]
    .map((block) => ({ ...block, items: itemsInDates(block.dates) }))
    .filter((block) => block.items.length > 0)
)

const isCurrentMonth = computed(
  () => year.value === mounted.getFullYear() && month.value === mounted.getMonth() + 1
)

const cells = computed(() => {
  const first = new Date(year.value, month.value - 1, 1)
  const days = new Date(year.value, month.value, 0).getDate()
  const offset = (first.getDay() + 6) % 7 // Monday-first grid
  const byDate = {}
  for (const it of items.value) (byDate[it.date] ??= []).push(it)
  const list = []
  for (let i = 0; i < offset; i++) list.push({ blank: true, key: `b${i}` })
  for (let d = 1; d <= days; d++) {
    const iso = isoOf(year.value, month.value, d)
    list.push({ key: iso, d, iso, items: byDate[iso] ?? [], today: iso === todayISO })
  }
  return list
})

const selectedItems = computed(() =>
  selectedDate.value ? items.value.filter((it) => it.date === selectedDate.value) : []
)

const selectedLabel = computed(() =>
  selectedDate.value
    ? new Date(`${selectedDate.value}T00:00:00`).toLocaleDateString(dateLocale(), {
        month: "long",
        day: "numeric",
        weekday: "short",
      })
    : ""
)

function dotColor(it) {
  return it.kind === "exam" ? "#b42318" : eventTypeColor(it.event_type)
}

</script>

<template>
  <div class="card">
    <div class="card__head">
      <div>
        <h2 class="card__title"><Icon name="calendar" :size="16" /> {{ t("home.calendar") }}</h2>
        <p class="card__desc">有圆点的日子有记录，点开查看详情</p>
      </div>
      <button v-if="!isCurrentMonth" class="btn btn--sm btn--ghost" @click="goToday">
        {{ t("home.calToday") }}
      </button>
    </div>

    <div class="card__body">
      <div v-if="loadError" class="state state--in-card" style="padding: 16px 0">
        <p class="state__desc">{{ loadError }}</p>
        <div class="state__actions">
          <button class="btn btn--sm btn--primary" @click="load">
            <Icon name="refresh" :size="13" /> {{ t("action.retry") }}
          </button>
        </div>
      </div>

      <template v-else>
        <div class="cal-head">
          <button class="btn btn--sm btn--icon" :aria-label="t('home.calPrev')" @click="shiftMonth(-1)">
            <Icon name="chevron-left" :size="15" />
          </button>
          <span class="cal-head__label">{{ year }} 年 {{ month }} 月</span>
          <button class="btn btn--sm btn--icon" :aria-label="t('home.calNext')" @click="shiftMonth(1)">
            <Icon name="chevron-right" :size="15" />
          </button>
        </div>

        <div class="cal-grid" aria-hidden="true">
          <span v-for="w in WEEKDAYS" :key="w" class="cal-weekday">{{ w }}</span>
        </div>

        <div v-if="loading" class="stack" style="margin-top: 8px">
          <div class="skeleton skeleton--row" style="height: 44px" />
          <div class="skeleton skeleton--row" style="height: 44px" />
          <div class="skeleton skeleton--row" style="height: 44px" />
        </div>

        <div v-else class="cal-grid" role="grid">
          <template v-for="c in cells" :key="c.key">
            <span v-if="c.blank" class="cal-day" />
            <button
              v-else
              class="cal-day"
              :class="{
                'cal-day--today': c.today,
                'cal-day--selected': selectedDate === c.iso,
                'cal-day--has': c.items.length > 0,
              }"
              type="button"
              :aria-label="`${c.iso}，${c.items.length ? `${c.items.length} 条记录` : '无记录'}`"
              @click="selectDay(c)"
            >
              <span class="cal-day__num">{{ c.d }}</span>
              <span class="cal-day__dots">
                <i v-for="(it, i) in c.items.slice(0, 3)" :key="i" :style="{ background: dotColor(it) }" />
              </span>
            </button>
          </template>
        </div>

        <div v-if="!selectedDate && nearTermBlocks.length" class="cal-notify">
          <section v-for="block in nearTermBlocks" :key="block.key" class="cal-notify__block">
            <header class="cal-notify__head">
              <span class="cal-notify__label">{{ block.label }}</span>
              <span class="pill pill--muted pill--count">{{ block.items.length }}</span>
            </header>
            <div class="feed cal-notify__list">
              <FeedEventItem
                v-for="it in block.items"
                :key="`${it.kind}-${it.id}`"
                :event="it"
                student-first
              />
            </div>
          </section>
        </div>

        <!-- 选中日期的明细 -->
        <div v-if="selectedDate" class="cal-day-list">
          <div class="between" style="margin-bottom: 8px">
            <p style="font-weight: 600">{{ selectedLabel }}</p>
            <button class="btn btn--sm" @click="selectedDate = ''">
              <Icon name="close" :size="13" />
            </button>
          </div>

          <p v-if="!selectedItems.length" class="state__desc" style="padding: 8px 0">
            {{ t("home.calNothing") }}
          </p>

          <div v-else class="feed">
            <FeedEventItem
              v-for="it in selectedItems"
              :key="`${it.kind}-${it.id}`"
              :event="it"
              student-first
              date-format="none"
            />
          </div>
        </div>
      </template>
    </div>
  </div>
</template>
