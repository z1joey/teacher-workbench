<script setup>
// 首页月历：考试与跟进记录放在一起看。
// 有记录的日期可以点开；弹窗里 Esc / 点遮罩 / 点取消都能安全退出（用户控制与自由）。
import { computed, nextTick, onMounted, ref } from "vue"
import Icon from "./Icon.vue"
import api from "../api"
import { ask } from "../confirm"
import { runUndoable } from "../feedback"
import {
  dateLocale,
  describeEvent,
  eventTypeColor,
  eventTypeIcon,
  eventTypeLabel,
  friendlyError,
  recordableEventOptions,
  t,
} from "../strings"

const WEEKDAYS = ["一", "二", "三", "四", "五", "六", "日"]
const mounted = new Date()
const todayISO = isoOf(mounted.getFullYear(), mounted.getMonth() + 1, mounted.getDate())

const year = ref(mounted.getFullYear())
const month = ref(mounted.getMonth() + 1) // 1-12
const items = ref([])
const loading = ref(true)
const loadError = ref("")
const selectedDate = ref("")

const modal = ref(null) // { mode: "add" } | { mode: "edit", item } | null
const formSaving = ref(false)
const formError = ref("")
const studentOptions = ref([])
const form = ref(emptyForm())
const firstFieldEl = ref(null)

function emptyForm() {
  return {
    student_id: "",
    event_type: "home_visited",
    recurrence: "once",
    summary: "",
    purpose: "",
    follow_up_needed: false,
    follow_up_note: "",
  }
}

function isoOf(y, m, d) {
  return `${y}-${String(m).padStart(2, "0")}-${String(d).padStart(2, "0")}`
}

async function load() {
  loading.value = true
  loadError.value = ""
  try {
    const data = await api.get(`/calendar?year=${year.value}&month=${month.value}`)
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
  closeForm()
  load()
}

function goToday() {
  year.value = mounted.getFullYear()
  month.value = mounted.getMonth() + 1
  selectedDate.value = todayISO
  closeForm()
  load()
}

function selectDay(c) {
  selectedDate.value = selectedDate.value === c.iso ? "" : c.iso
  closeForm()
}

onMounted(load)

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

const typeOptions = computed(() => recordableEventOptions())

function needsPurpose(type) {
  return type === "home_visited" || type === "parent_call"
}
function needsFollowUp(type) {
  return type === "home_visited"
}

// ------------------------------------------------------------ 新增 / 编辑

async function openAdd() {
  modal.value = { mode: "add" }
  formError.value = ""
  form.value = emptyForm()
  await ensureStudents()
  await nextTick()
  firstFieldEl.value?.focus()
}

async function openEdit(it) {
  modal.value = { mode: "edit", item: it }
  formError.value = ""
  const p = it.payload || {}
  form.value = {
    student_id: it.student_id,
    event_type: it.event_type,
    recurrence: it.recurrence || "once",
    summary: p.summary || "",
    purpose: p.purpose || "",
    follow_up_needed: !!p.follow_up_needed,
    follow_up_note: p.follow_up_note || "",
  }
  await ensureStudents()
  await nextTick()
  firstFieldEl.value?.focus()
}

async function ensureStudents() {
  if (studentOptions.value.length) return
  try {
    studentOptions.value = await api.get("/students")
  } catch {
    studentOptions.value = []
  }
}

function closeForm() {
  modal.value = null
  formError.value = ""
}

async function saveForm() {
  formError.value = ""
  if (!form.value.student_id) {
    formError.value = t("home.calStudentRequired")
    return
  }
  if (!form.value.summary.trim()) {
    formError.value = t("home.calSummaryRequired")
    return
  }
  formSaving.value = true
  try {
    const body = {
      event_type: form.value.event_type,
      summary: form.value.summary.trim(),
      purpose: form.value.purpose.trim() || null,
      follow_up_needed: form.value.follow_up_needed,
      follow_up_note: form.value.follow_up_note.trim() || null,
    }
    if (modal.value?.mode === "edit") {
      // keep the original time; only the content is editable here
      body.occurred_at = modal.value.item.occurred_at
      await api.patch(`/students/${form.value.student_id}/events/${modal.value.item.id}`, body)
    } else {
      body.occurred_at = new Date(`${selectedDate.value}T09:00`).toISOString()
      await api.post(`/students/${form.value.student_id}/events`, body)
    }
    closeForm()
    await load()
  } catch (e) {
    formError.value = friendlyError(e)
  } finally {
    formSaving.value = false
  }
}

// 每年重复的事件（生日）自动生成的记录只读 —— 直接说明原因，而不是静默禁用
const readOnlyEvent = computed(
  () =>
    modal.value?.mode === "edit" &&
    (modal.value.item.recurrence === "yearly" || modal.value.item.event_type === "birthday")
)

async function deleteRecord(it) {
  const ok = await ask({
    title: `删除这条${eventTypeLabel(it.event_type)}记录？`,
    message: `${it.student_name} · ${selectedLabel.value}`,
    consequences: [t("event.deleteConfirm")],
    confirmLabel: t("action.delete"),
  })
  if (!ok) return

  const snapshot = items.value
  items.value = items.value.filter((x) => !(x.kind === it.kind && x.id === it.id))
  if (modal.value?.mode === "edit") closeForm()

  runUndoable({
    title: `已删除「${it.student_name}」的${eventTypeLabel(it.event_type)}记录`,
    run: () => api.delete(`/students/${it.student_id}/events/${it.id}`),
    onUndo: () => {
      items.value = snapshot
    },
    onDone: () => load(),
  })
}
</script>

<template>
  <div class="card">
    <div class="card__head">
      <div>
        <h2 class="card__title"><Icon name="calendar" :size="16" /> {{ t("home.calendar") }}</h2>
        <p class="card__desc">有圆点的日子有记录，点开查看详情或补充</p>
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

        <div class="cal-legend">
          <span class="cal-legend__item">
            <i class="cal-legend__swatch" style="background: #b42318" /> {{ t("home.calLegendExam") }}
          </span>
          <span class="cal-legend__item">
            <i class="cal-legend__swatch" style="background: var(--primary)" /> {{ t("home.calLegendRecord") }}
          </span>
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

          <div v-for="it in selectedItems" :key="`${it.kind}-${it.id}`" class="feed__item">
            <span
              class="feed__dot"
              :style="{ background: it.kind === 'exam' ? '#b42318' : eventTypeColor(it.event_type) }"
            >
              <Icon :name="it.kind === 'exam' ? 'clipboard' : eventTypeIcon(it.event_type)" :size="13" />
            </span>
            <div class="feed__body">
              <div class="feed__head">
                <span v-if="it.kind === 'exam'">
                  <router-link :to="`/exams/${it.id}`">{{ it.name }}</router-link>
                </span>
                <span v-else>
                  <router-link :to="`/students/${it.student_id}`">{{ it.student_name }}</router-link>
                  · {{ eventTypeLabel(it.event_type) }}
                  <template v-if="it.actor"> · {{ it.actor }}</template>
                </span>
              </div>
              <p v-if="it.kind === 'record'" class="feed__desc">
                {{ describeEvent(it.event_type, it.payload) }}
              </p>
            </div>
            <button
              v-if="it.kind === 'record'"
              class="icon-btn"
              :aria-label="`编辑这条记录`"
              @click="openEdit(it)"
            >
              <Icon name="dots" :size="16" />
            </button>
          </div>

          <button class="btn btn--sm btn--block" style="margin-top: 12px" @click="openAdd">
            <Icon name="plus" :size="14" /> {{ t("home.calAdd") }}
          </button>
        </div>
      </template>
    </div>

    <!-- 新增 / 编辑记录 -->
    <div
      v-if="modal"
      class="overlay"
      role="dialog"
      aria-modal="true"
      :aria-label="modal.mode === 'edit' ? '编辑记录' : '添加记录'"
      @click.self="closeForm"
    >
      <div class="modal">
        <div class="modal__head">
          <div class="grow">
            <h2 class="modal__title">
              {{ (modal.mode === "edit" ? t("action.edit") : t("home.calAdd")) + " · " + selectedLabel }}
            </h2>
          </div>
          <button class="icon-btn" :aria-label="t('action.close')" @click="closeForm">
            <Icon name="close" :size="16" />
          </button>
        </div>

        <form class="modal__body" @submit.prevent="saveForm">
          <p v-if="readOnlyEvent" class="pill pill--warn" style="margin-bottom: 14px">
            <Icon name="info" :size="12" /> {{ t("home.calReadOnly") }}
          </p>

          <div class="field">
            <label class="field__label" for="cal-student">
              {{ t("home.calStudent") }} <span class="field__req">*</span>
            </label>
            <select
              id="cal-student"
              ref="firstFieldEl"
              v-model="form.student_id"
              class="select"
              required
              :disabled="modal.mode === 'edit' || readOnlyEvent"
            >
              <option value="" disabled>—</option>
              <option v-for="s in studentOptions" :key="s.id" :value="s.id">
                {{ s.name }}{{ s.class ? `（${s.class.name}）` : "" }}
              </option>
            </select>
          </div>

          <div class="field">
            <label class="field__label" for="cal-type">{{ t("home.calType") }}</label>
            <select
              id="cal-type"
              v-model="form.event_type"
              class="select"
              :disabled="readOnlyEvent"
            >
              <option v-for="ty in typeOptions" :key="ty.value" :value="ty.value">{{ ty.label }}</option>
            </select>
          </div>

          <div class="field">
            <label class="field__label" for="cal-recurrence">{{ t("home.calRecurrence") }}</label>
            <select
              id="cal-recurrence"
              v-model="form.recurrence"
              class="select"
              :disabled="readOnlyEvent || modal.mode === 'edit'"
            >
              <option value="once">{{ t("home.calOnce") }}</option>
              <option value="yearly">{{ t("home.calYearly") }}</option>
            </select>
          </div>

          <div class="field">
            <label class="field__label" for="cal-summary">
              {{ t("home.calSummary") }} <span class="field__req">*</span>
            </label>
            <input
              id="cal-summary"
              v-model="form.summary"
              class="input"
              type="text"
              required
              :disabled="readOnlyEvent"
              :aria-invalid="!!formError"
            />
          </div>

          <div v-if="needsPurpose(form.event_type)" class="field">
            <label class="field__label" for="cal-purpose">{{ t("home.calPurpose") }}</label>
            <input id="cal-purpose" v-model="form.purpose" class="input" type="text" />
          </div>

          <div v-if="needsFollowUp(form.event_type)" class="field">
            <label class="check">
              <input v-model="form.follow_up_needed" type="checkbox" />
              <span>{{ t("home.calFollowUp") }}</span>
            </label>
            <span class="field__hint">{{ t("event.followUpHint") }}</span>
          </div>

          <div v-if="needsFollowUp(form.event_type) && form.follow_up_needed" class="field">
            <label class="field__label" for="cal-followup">{{ t("home.calFollowUpNote") }}</label>
            <input id="cal-followup" v-model="form.follow_up_note" class="input" type="text" />
          </div>

          <p v-if="formError" class="field__error" style="margin-bottom: 12px">
            <Icon name="alert-circle" :size="12" /> {{ formError }}
          </p>

          <div class="modal__foot" style="padding: 16px 0 0">
            <button
              v-if="modal.mode === 'edit'"
              type="button"
              class="btn btn--danger"
              :disabled="formSaving"
              @click="deleteRecord(modal.item)"
            >
              <Icon name="trash" :size="14" /> {{ t("action.delete") }}
            </button>
            <span class="form-actions__spacer" />
            <button type="button" class="btn" @click="closeForm">{{ t("action.cancel") }}</button>
            <button v-if="!readOnlyEvent" type="submit" class="btn btn--primary" :disabled="formSaving">
              <span v-if="formSaving" class="spinner" />
              {{ formSaving ? t("action.saving") : t("action.save") }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>
