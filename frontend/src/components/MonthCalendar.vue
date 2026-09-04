<script setup>
import { ref, computed, onMounted } from "vue"
import Icon from "./Icon.vue"
import api from "../api"
import {
  dateLocale,
  describeEvent,
  eventTypeColor,
  eventTypeIcon,
  eventTypeLabel,
  t,
} from "../strings"

const WEEKDAYS = ["一", "二", "三", "四", "五", "六", "日"]
const TYPE_OPTIONS = ["home_visited", "parent_call", "talk", "tutoring", "note_added"]
const mounted = new Date()
const todayISO = isoOf(mounted.getFullYear(), mounted.getMonth() + 1, mounted.getDate())

const year = ref(mounted.getFullYear())
const month = ref(mounted.getMonth() + 1) // 1-12
const items = ref([])
const loading = ref(true)
const selectedDate = ref("")

const modal = ref(null) // { mode: "add" } | { mode: "edit", item } | null
const formSaving = ref(false)
const formError = ref("")
const studentOptions = ref([])
const form = ref(emptyForm())

function emptyForm() {
  return { student_id: "", event_type: "home_visited", recurrence: "once", summary: "", purpose: "", follow_up_needed: false, follow_up_note: "" }
}

function isoOf(y, m, d) {
  return `${y}-${String(m).padStart(2, "0")}-${String(d).padStart(2, "0")}`
}

async function load() {
  loading.value = true
  try {
    const data = await api.get(`/calendar?year=${year.value}&month=${month.value}`)
    items.value = data.items
  } catch {
    items.value = []
  } finally {
    loading.value = false
  }
}

function shiftMonth(delta) {
  const m = month.value + delta
  if (m === 0) { year.value--; month.value = 12 } else if (m === 13) { year.value++; month.value = 1 } else month.value = m
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

async function selectDay(c) {
  selectedDate.value = selectedDate.value === c.iso ? "" : c.iso
  closeForm()
}

onMounted(load)

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
        month: "long", day: "numeric", weekday: "short",
      })
    : ""
)

function dotColor(it) {
  return it.kind === "exam" ? "#b42318" : eventTypeColor(it.event_type)
}

function fmtDate(ts) {
  return new Date(ts).toLocaleDateString(dateLocale(), {
    year: "numeric", month: "short", day: "numeric",
  })
}

// --- add / delete records straight from the calendar --------------------

async function openAdd() {
  modal.value = { mode: "add" }
  formError.value = ""
  form.value = emptyForm()
  if (!studentOptions.value.length) {
    try {
      studentOptions.value = await api.get("/students")
    } catch {
      studentOptions.value = []
    }
  }
}

function openEdit(it) {
  modal.value = { mode: "edit", item: it }
  formError.value = ""
  const p = it.payload || {}
  form.value = {
    student_id: it.student_id,
    event_type: it.event_type,
    summary: p.summary || "",
    purpose: p.purpose || "",
    follow_up_needed: !!p.follow_up_needed,
    follow_up_note: p.follow_up_note || "",
  }
  if (!studentOptions.value.length) {
    api.get("/students").then((s) => (studentOptions.value = s)).catch(() => {})
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
    formError.value = e.message
  } finally {
    formSaving.value = false
  }
}

function editRecord(it) {
  openEdit(it)
}

async function deleteRecord(it) {
  if (!window.confirm(t("action.deleteConfirm"))) return
  try {
    await api.delete(`/students/${it.student_id}/events/${it.id}`)
    if (modal.value?.mode === "edit" && modal.value.item.id === it.id) closeForm()
    await load()
  } catch (e) {
    alert(`删除失败：${e.message}`)
  }
}
</script>

<template>
  <div class="card">
    <h2>{{ t("home.calendar") }}</h2>

    <div class="cal-head">
      <button class="small" :aria-label="t('home.calPrev')" @click="shiftMonth(-1)">‹</button>
      <strong>{{ year }} 年 {{ month }} 月</strong>
      <button class="small" :aria-label="t('home.calNext')" @click="shiftMonth(1)">›</button>
    </div>

    <div class="cal-grid cal-week">
      <span v-for="w in WEEKDAYS" :key="w">{{ w }}</span>
    </div>
    <div class="cal-grid">
      <template v-for="c in cells" :key="c.key">
        <span v-if="c.blank" class="cal-day blank" />
        <button
          v-else
          class="cal-day"
          :class="{ today: c.today, sel: selectedDate === c.iso, has: c.items.length > 0 }"
          type="button"
          :aria-label="c.iso"
          @click="selectDay(c)"
        >
          <span class="cal-num">{{ c.d }}</span>
          <span class="cal-dots">
            <i v-for="(it, i) in c.items.slice(0, 3)" :key="i" :style="{ background: dotColor(it) }" />
          </span>
        </button>
      </template>
    </div>

    <div v-if="selectedDate" class="cal-items">
      <p class="cal-sel-date">{{ selectedLabel }}</p>

      <p v-if="!selectedItems.length" class="empty">{{ t("home.calNothing") }}</p>
      <div v-for="it in selectedItems" :key="`${it.kind}-${it.id}`" class="mini-event">
        <span class="mini-icon" :style="{ background: it.kind === 'exam' ? '#b42318' : eventTypeColor(it.event_type) }">
          <Icon :name="it.kind === 'exam' ? 'clipboard' : eventTypeIcon(it.event_type)" :size="13" />
        </span>
        <div class="mini-body">
          <div class="mini-head">
            <span v-if="it.kind === 'exam'">
              <router-link :to="`/exams/${it.id}`">{{ it.name }}</router-link>
            </span>
            <span v-else>
              <router-link :to="`/students/${it.student_id}`">{{ it.student_name }}</router-link>
              · {{ eventTypeLabel(it.event_type) }}<template v-if="it.actor"> · {{ it.actor }}</template>
            </span>
          </div>
          <p v-if="it.kind === 'record'" class="mini-desc">{{ describeEvent(it.event_type, it.payload) }}</p>
        </div>
        <div v-if="it.kind === 'record'" class="cal-item-actions">
          <button class="small" :title="t('action.edit')" @click="editRecord(it)">{{ t("action.edit") }}</button>
          <button class="small" :title="t('action.delete')" @click="deleteRecord(it)">{{ t("action.delete") }}</button>
        </div>
      </div>

      <button class="small cal-add" @click="openAdd">
        <Icon name="plus" :size="13" /> {{ t("home.calAdd") }}
      </button>
    </div>

    <div v-if="modal" class="event-detail-overlay" @click.self="closeForm">
      <div class="event-detail-modal">
        <div class="modal-head">
          <strong>{{ (modal.mode === "edit" ? t("action.edit") : t("home.calAdd")) + " · " + selectedLabel }}</strong>
          <button class="modal-close" :aria-label="t('action.cancel')" @click="closeForm">×</button>
        </div>

        <form class="cal-form" @submit.prevent="saveForm">
          <div class="field">
            <label>{{ t("home.calStudent") }} *</label>
            <select v-model="form.student_id" required :disabled="modal.mode === 'edit'">
              <option value="" disabled>—</option>
              <option v-for="s in studentOptions" :key="s.id" :value="s.id">
                {{ s.name }}{{ s.class ? `（${s.class.name}）` : "" }}
              </option>
            </select>
          </div>
          <div class="field">
            <label>{{ t("home.calType") }}</label>
            <select v-model="form.event_type">
              <option v-for="ty in TYPE_OPTIONS" :key="ty" :value="ty">{{ eventTypeLabel(ty) }}</option>
            </select>
          </div>
          <div class="field">
            <label>{{ t("home.calRecurrence") }}</label>
            <select v-model="form.recurrence">
              <option value="once">{{ t("home.calOnce") }}</option>
              <option value="yearly">{{ t("home.calYearly") }}</option>
            </select>
          </div>
          <div class="field">
            <label>{{ t("home.calSummary") }}</label>
            <input v-model="form.summary" type="text" required />
          </div>
          <div v-if="form.event_type === 'home_visited' || form.event_type === 'parent_call'" class="field">
            <label>{{ t("home.calPurpose") }}</label>
            <input v-model="form.purpose" type="text" />
          </div>
          <div v-if="form.event_type === 'home_visited'" class="field cal-check">
            <label style="display: flex; align-items: center; gap: 6px">
              <input v-model="form.follow_up_needed" type="checkbox" /> {{ t("home.calFollowUp") }}
            </label>
          </div>
          <div v-if="form.event_type === 'home_visited' && form.follow_up_needed" class="field">
            <label>{{ t("home.calFollowUpNote") }}</label>
            <input v-model="form.follow_up_note" type="text" />
          </div>
          <p v-if="formError" class="error-text">{{ formError }}</p>
          <div class="cal-form-actions">
            <button type="submit" class="primary" :disabled="formSaving">
              {{ formSaving ? t("new.saving") : t("action.save") }}
            </button>
            <button type="button" @click="closeForm">{{ t("action.cancel") }}</button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>
