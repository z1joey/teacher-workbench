<script setup>
import { ref, onMounted, onBeforeUnmount, nextTick, watch } from "vue"
import { useRouter } from "vue-router"
import Icon from "../components/Icon.vue"
import api from "../api"
import { dateLocale, eventTypeLabel, subject, t } from "../strings"

const router = useRouter()

const classes = ref([])
const teachers = ref([])
const loading = ref(true)
const error = ref("")

const showCreate = ref(false)
const creating = ref(false)
const createError = ref("")
const createForm = ref(emptyForm())

function emptyForm() {
  return { name: "", grade_level: 7, academic_year: defaultYear(), homeroom_teacher_id: null }
}

function defaultYear() {
  const now = new Date()
  const start = now.getMonth() + 1 >= 8 ? now.getFullYear() : now.getFullYear() - 1
  return `${start}/${start + 1}`
}

onMounted(async () => {
  window.addEventListener("resize", measureAll)
  try {
    const [cs, ts] = await Promise.all([api.get("/classes"), api.get("/teachers")])
    classes.value = cs
    teachers.value = ts
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
    await nextTick()
    measureAll()
  }
})

onBeforeUnmount(() => window.removeEventListener("resize", measureAll))

async function load() {
  classes.value = await api.get("/classes")
}

function toBody(f) {
  return {
    name: (f.name || "").trim(),
    grade_level: Number(f.grade_level),
    academic_year: (f.academic_year || "").trim(),
    homeroom_teacher_id: f.homeroom_teacher_id || null,
  }
}

async function createClass() {
  createError.value = ""
  if (!(createForm.value.name || "").trim()) {
    createError.value = t("classes.nameRequired")
    return
  }
  creating.value = true
  try {
    await api.post("/classes", toBody(createForm.value))
    createForm.value = emptyForm()
    showCreate.value = false
    await load()
  } catch (e) {
    createError.value = e.message
  } finally {
    creating.value = false
  }
}

function className(c) {
  return c.name
}

const SUBJECT_ORDER = ["chinese", "math", "english", "physics", "chemistry"]

// per-subject class averages of the latest exam, with delta vs the previous one
function avgSummary(c) {
  const trend = c.avg_trend || []
  if (!trend.length) return []
  const last = trend[trend.length - 1]
  const prev = trend.length > 1 ? trend[trend.length - 2] : null
  const subs = Object.keys(last.averages).sort((a, b) => {
    const ia = SUBJECT_ORDER.indexOf(a)
    const ib = SUBJECT_ORDER.indexOf(b)
    return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib)
  })
  return subs.map((sub) => {
    const avg = last.averages[sub]
    const p = prev ? prev.averages[sub] : null
    const delta = p != null && avg != null ? Math.round((avg - p) * 10) / 10 : null
    return { sub, initial: subject(sub).charAt(0), avg, delta }
  })
}

function shortDate(ts) {
  return new Date(ts).toLocaleDateString(dateLocale(), { month: "short", day: "numeric" })
}

// chips cap at two rows, events cap at five — both expandable
const expandedChips = ref({})
const expandedEvents = ref({})
const chipsOverflow = ref({})
const cardEls = ref({})

function setChipsRef(cid) {
  return (el) => {
    if (el) {
      cardEls.value[cid] = { ...(cardEls.value[cid] || {}), chips: el }
      measure(cid)
    }
  }
}

function setEventsRef(cid) {
  return (el) => {
    if (el) {
      cardEls.value[cid] = { ...(cardEls.value[cid] || {}), events: el }
    }
  }
}

function measure(cid) {
  const el = cardEls.value[cid]?.chips
  if (el) chipsOverflow.value[cid] = el.scrollHeight > el.clientHeight + 1
}

function measureAll() {
  for (const cid of Object.keys(cardEls.value)) measure(Number(cid))
}

function visibleEvents(c) {
  const evs = c.recent_events || []
  return expandedEvents.value[c.id] ? evs : evs.slice(0, 5)
}

watch(classes, async () => {
  await nextTick()
  measureAll()
})
</script>

<template>
  <div style="display: flex; justify-content: space-between; align-items: center; gap: 12px">
    <div>
      <h1>{{ t("classes.title") }}</h1>
      <p class="page-sub">{{ t("classes.subtitle") }}</p>
    </div>
    <button class="primary" @click="showCreate = !showCreate">
      <Icon v-if="!showCreate" name="plus" :size="15" />
      {{ showCreate ? t("action.cancel") : t("classes.create") }}
    </button>
  </div>

  <p v-if="error" class="error-text">{{ error }}</p>
  <p v-else-if="loading" class="empty">{{ t("common.loading") }}</p>

  <template v-else>
    <!-- create form -->
    <div v-if="showCreate" class="card" style="max-width: 560px">
      <h2>{{ t("classes.create") }}</h2>
      <div style="display: flex; gap: 12px">
        <div class="field" style="flex: 1">
          <label>{{ t("classes.name") }} *</label>
          <input v-model="createForm.name" type="text" :placeholder="t('classes.name')" />
        </div>
        <div class="field" style="flex: 1">
          <label>{{ t("classes.grade") }}</label>
          <input v-model="createForm.grade_level" type="number" min="1" max="12" />
        </div>
      </div>
      <div style="display: flex; gap: 12px">
        <div class="field" style="flex: 1">
          <label>{{ t("classes.year") }}</label>
          <input v-model="createForm.academic_year" type="text" />
        </div>
        <div class="field" style="flex: 1">
          <label>{{ t("classes.homeroom") }}</label>
          <select v-model="createForm.homeroom_teacher_id">
            <option :value="null">{{ t("common.none") }}</option>
            <option v-for="teacher in teachers" :key="teacher.id" :value="teacher.id">
              {{ teacher.name }}
            </option>
          </select>
        </div>
      </div>
      <p v-if="createError" class="error-text">{{ createError }}</p>
      <button class="primary" :disabled="creating" @click="createClass">
        {{ creating ? t("classes.creating") : t("classes.create") }}
      </button>
    </div>

    <!-- class cards -->
    <div class="class-grid">
      <div v-for="c in classes" :key="c.id" class="card class-card">
        <router-link :to="`/classes/${c.id}`" style="text-decoration: none; color: inherit; display: block">
          <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 8px">
            <div>
              <h2 style="margin-bottom: 2px">{{ className(c) }}</h2>
              <span class="weakness-sub">
                {{ c.academic_year }} · {{ t("classes.homeroom") }}: {{ c.homeroom_teacher || "—" }} ·
                {{ t("profile.studentsCount", { n: c.student_count }) }}
              </span>
            </div>
            <button class="small icon-btn" title="查看 / 编辑 / 删除">…</button>
          </div>
          <div v-if="c.avg_trend && c.avg_trend.length" class="class-avg-row">
            <span class="weakness-sub">{{ t("classes.avgLabel") }}</span>
            <span v-for="a in avgSummary(c)" :key="a.sub" class="class-avg-item">
              <b>{{ a.initial }}</b> {{ a.avg }}
              <span v-if="a.delta !== null" class="delta" :class="a.delta >= 0 ? 'up' : 'down'">
                {{ a.delta > 0 ? "↑" : "↓" }}{{ Math.abs(a.delta) }}
              </span>
            </span>
          </div>

          <div v-if="(c.recent_events || []).length" class="class-events">
            <div v-for="ev in visibleEvents(c)" :key="`e${ev.id}`" class="class-event">
              <span class="weakness-sub">{{ shortDate(ev.occurred_at) }}</span>
              <router-link :to="`/students/${ev.student_id}`">{{ ev.student_name }}</router-link>
              · {{ eventTypeLabel(ev.event_type) }}
              <span v-if="ev.recurrence === 'yearly'" class="visited-mark">↻</span>
            </div>
          </div>
          <button
            v-if="(c.recent_events || []).length > 5 || expandedEvents[c.id]"
            class="small class-toggle"
            @click="expandedEvents[c.id] = !expandedEvents[c.id]"
          >
            {{ expandedEvents[c.id] ? t("action.collapse") : t("classes.showAllEvents") }}
          </button>

          <div
            v-if="c.students.length"
            :ref="setChipsRef(c.id)"
            class="student-chips"
            :class="{ collapsed: !expandedChips[c.id] }"
          >
            <span
              v-for="s in c.students"
              :key="s.id"
              class="student-chip"
              :title="`${s.admission_no} · ${s.home_visited ? t('classes.visitedYes') : t('classes.visitedNo')}`"
              @click.stop="(e) => { e.preventDefault(); e.stopPropagation(); router.push('/students/' + s.id) }"
            >
              {{ s.name }}<span v-if="s.home_visited" class="visited-mark" :title="t('classes.visitedYes')">✓</span>
            </span>
          </div>
          <p v-else class="empty">{{ t("classes.noStudents") }}</p>
          <button
            v-if="c.students.length && (chipsOverflow[c.id] || expandedChips[c.id])"
            class="small class-toggle"
            @click="expandedChips[c.id] = !expandedChips[c.id]"
          >
            {{ expandedChips[c.id] ? t("action.collapse") : t("classes.showAllStudents") }}
          </button>
        </router-link>
      </div>
    </div>
  </template>
</template>
