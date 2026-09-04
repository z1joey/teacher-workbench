<script setup>
// 班级：卡片上直接看到班均、家访情况和最近事件，不点进去也能判断要不要看。
// 学生名单默认只显示前 12 个，多的折叠 —— 不用 JS 量高度，窄屏也不会算错。
import { computed, onMounted, ref, watch } from "vue"
import { useRoute, useRouter } from "vue-router"
import Icon from "../components/Icon.vue"
import PageHeader from "../components/PageHeader.vue"
import AsyncState from "../components/AsyncState.vue"
import FormField from "../components/FormField.vue"
import api from "../api"
import { ask } from "../confirm"
import { notify, runUndoable } from "../feedback"
import { eventTypeLabel, friendlyError, subject, t } from "../strings"

const route = useRoute()
const router = useRouter()

const classes = ref([])
const teachers = ref([])
const loading = ref(true)
const error = ref("")

const showCreate = ref(false)
const creating = ref(false)
const createError = ref("")
const createForm = ref(emptyForm())

const CHIPS_VISIBLE = 12
const EVENTS_VISIBLE = 3
const expandedChips = ref({})
const expandedEvents = ref({})

function emptyForm() {
  return { name: "", grade_level: 7, academic_year: defaultYear(), homeroom_teacher_id: null }
}

function defaultYear() {
  const now = new Date()
  const start = now.getMonth() + 1 >= 8 ? now.getFullYear() : now.getFullYear() - 1
  return `${start}/${start + 1}`
}

async function load() {
  loading.value = true
  error.value = ""
  try {
    const [cs, ts] = await Promise.all([api.get("/classes"), api.get("/teachers")])
    classes.value = cs
    teachers.value = ts
  } catch (e) {
    error.value = friendlyError(e)
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await load()
  // 从命令面板或「还没有班级」引导过来时，直接把表单打开
  if (route.query.create === "1") showCreate.value = true
})
watch(() => route.query.create, (v) => {
  if (v === "1") showCreate.value = true
})

async function createClass() {
  createError.value = ""
  if (!createForm.value.name.trim()) {
    createError.value = t("classes.nameRequired")
    return
  }
  creating.value = true
  try {
    await api.post("/classes", {
      name: createForm.value.name.trim(),
      grade_level: Number(createForm.value.grade_level),
      academic_year: createForm.value.academic_year.trim(),
      homeroom_teacher_id: createForm.value.homeroom_teacher_id || null,
    })
    createForm.value = emptyForm()
    showCreate.value = false
    notify({ tone: "ok", title: "班级已创建", timeout: 2600 })
    await load()
  } catch (e) {
    createError.value = friendlyError(e)
  } finally {
    creating.value = false
  }
}

async function removeClass(c) {
  const ok = await ask({
    title: `删除班级「${c.name}」？`,
    consequences: [t("classes.deleteConfirm")],
    confirmLabel: t("action.delete"),
  })
  if (!ok) return

  const snapshot = classes.value
  classes.value = classes.value.filter((x) => x.id !== c.id)
  runUndoable({
    title: `已删除班级「${c.name}」`,
    run: () => api.delete(`/classes/${c.id}`),
    onUndo: () => {
      classes.value = snapshot
    },
    onDone: () => load(),
  })
}

const SUBJECT_ORDER = ["chinese", "math", "english", "politics", "history", "geography", "biology", "physics", "chemistry"]

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
    return { sub, label: subject(sub), avg, delta }
  })
}

function shortDate(ts) {
  return new Date(ts).toLocaleDateString("zh-CN", { month: "numeric", day: "numeric" })
}

function visibleStudents(c) {
  if (expandedChips.value[c.id]) return c.students
  return c.students.slice(0, CHIPS_VISIBLE)
}
function hiddenStudentCount(c) {
  return Math.max(0, c.students.length - CHIPS_VISIBLE)
}
function visibleEvents(c) {
  const evs = c.recent_events || []
  return expandedEvents.value[c.id] ? evs : evs.slice(0, EVENTS_VISIBLE)
}

const totalStudents = computed(() =>
  classes.value.reduce((n, c) => n + (c.student_count || 0), 0)
)
</script>

<template>
  <PageHeader
    :title="t('classes.title')"
    :subtitle="t('classes.subtitle')"
    :meta="classes.length ? [
      { label: '班级', value: classes.length },
      { label: '学生', value: totalStudents },
    ] : []"
  >
    <template #actions>
      <button class="btn btn--primary" @click="showCreate = !showCreate">
        <Icon :name="showCreate ? 'close' : 'plus'" :size="15" />
        {{ showCreate ? t("action.cancel") : t("classes.create") }}
      </button>
    </template>
  </PageHeader>

  <AsyncState
    :loading="loading"
    :error="error"
    :empty="!loading && !classes.length"
    :empty-title="t('classes.emptyTitle')"
    :empty-desc="t('classes.emptyDesc')"
    empty-icon="building"
    @retry="load"
  >
    <template #emptyAction>
      <button class="btn btn--primary" @click="showCreate = true">
        <Icon name="plus" :size="15" /> {{ t("classes.create") }}
      </button>
    </template>

    <!-- 新建班级 -->
    <div v-if="showCreate" class="card" style="max-width: 620px">
      <div class="card__head">
        <h2 class="card__title"><Icon name="building" :size="16" /> {{ t("classes.create") }}</h2>
      </div>
      <form class="card__body" @submit.prevent="createClass">
        <div class="form-grid">
          <FormField :label="t('classes.name')" required>
            <input v-model="createForm.name" class="input" type="text" maxlength="60" />
          </FormField>
          <FormField :label="t('classes.grade')">
            <input
              v-model="createForm.grade_level"
              class="input"
              type="number"
              min="1"
              max="12"
            />
          </FormField>
          <FormField :label="t('classes.year')" hint="跨年的学年，比如 2025/2026">
            <input v-model="createForm.academic_year" class="input" type="text" />
          </FormField>
          <FormField :label="t('classes.homeroom')" optional>
            <select v-model="createForm.homeroom_teacher_id" class="select">
              <option :value="null">{{ t("common.none") }}</option>
              <option v-for="teacher in teachers" :key="teacher.id" :value="teacher.id">
                {{ teacher.name }}
              </option>
            </select>
          </FormField>
        </div>

        <p v-if="createError" class="field__error" style="margin-bottom: 12px">
          <Icon name="alert-circle" :size="13" /> {{ createError }}
        </p>

        <div class="form-actions">
          <button type="submit" class="btn btn--primary" :disabled="creating">
            <span v-if="creating" class="spinner" />
            {{ creating ? t("classes.creating") : t("classes.create") }}
          </button>
          <button type="button" class="btn btn--ghost" @click="showCreate = false">
            {{ t("action.cancel") }}
          </button>
        </div>
      </form>
    </div>

    <!-- 班级卡片 -->
    <div class="grid grid--2">
      <article v-for="c in classes" :key="c.id" class="card">
        <div class="card__head">
          <div class="grow">
            <h2 class="card__title" style="font-size: 16px">
              <router-link :to="`/classes/${c.id}`">{{ c.name }}</router-link>
            </h2>
            <p class="card__desc">
              {{ c.academic_year }} · {{ t("classes.homeroom") }}：{{ c.homeroom_teacher || t("common.none") }}
              · {{ t("profile.studentsCount", { n: c.student_count }) }}
            </p>
          </div>
          <button
            class="icon-btn icon-btn--danger"
            :aria-label="`删除班级 ${c.name}`"
            :title="t('classes.delete')"
            @click="removeClass(c)"
          >
            <Icon name="trash" :size="15" />
          </button>
        </div>

        <div class="card__body">
          <!-- 班均 -->
          <div v-if="avgSummary(c).length" class="stat-grid" style="margin-bottom: 14px">
            <div v-for="a in avgSummary(c)" :key="a.sub" class="stat stat--plain" style="margin: 0">
              <div class="stat__label">{{ a.label }}</div>
              <div class="stat__value tnum" style="font-size: 20px">
                {{ a.avg }}
                <span
                  v-if="a.delta !== null"
                  class="stat__sub"
                  :style="{ color: a.delta >= 0 ? 'var(--ok)' : 'var(--warn)' }"
                >
                  {{ a.delta > 0 ? "↑" : "↓" }}{{ Math.abs(a.delta) }}
                </span>
              </div>
            </div>
          </div>

          <!-- 最近事件 -->
          <div v-if="(c.recent_events || []).length" class="stack" style="gap: 4px; margin-bottom: 12px">
            <div v-for="ev in visibleEvents(c)" :key="`e${ev.id}`" class="row" style="font-size: 13px">
              <span class="stat__sub nowrap">{{ shortDate(ev.occurred_at) }}</span>
              <router-link :to="`/students/${ev.student_id}`">{{ ev.student_name }}</router-link>
              <span class="muted">· {{ eventTypeLabel(ev.event_type) }}</span>
              <span v-if="ev.recurrence === 'yearly'" class="pill pill--muted">↻ 每年</span>
            </div>
            <button
              v-if="(c.recent_events || []).length > EVENTS_VISIBLE || expandedEvents[c.id]"
              class="btn btn--sm btn--quiet"
              style="align-self: flex-start"
              @click="expandedEvents[c.id] = !expandedEvents[c.id]"
            >
              {{ expandedEvents[c.id] ? t("action.collapse") : t("classes.showAllEvents") }}
            </button>
          </div>

          <!-- 学生名单 -->
          <template v-if="c.students.length">
            <div class="chips">
              <router-link
                v-for="s in visibleStudents(c)"
                :key="s.id"
                :to="`/students/${s.id}`"
                class="chip"
                :title="`${s.admission_no} · ${s.home_visited ? t('classes.visitedYes') : t('classes.visitedNo')}`"
              >
                {{ s.name }}
                <span v-if="s.home_visited" class="visited" :title="t('classes.visitedYes')">✓</span>
              </router-link>
            </div>
            <button
              v-if="hiddenStudentCount(c) > 0 || expandedChips[c.id]"
              class="btn btn--sm btn--quiet"
              style="margin-top: 8px"
              @click="expandedChips[c.id] = !expandedChips[c.id]"
            >
              <Icon :name="expandedChips[c.id] ? 'chevron-up' : 'chevron-down'" :size="13" />
              {{
                expandedChips[c.id]
                  ? t("action.collapse")
                  : `${t("classes.showAllStudents")}（还有 ${hiddenStudentCount(c)} 人）`
              }}
            </button>
          </template>
          <p v-else class="state__desc">{{ t("classes.noStudents") }}</p>
        </div>

        <div class="card__foot">
          <router-link :to="`/classes/${c.id}`" class="btn btn--sm btn--ghost">
            {{ t("classes.viewDetail") }} <Icon name="chevron-right" :size="13" />
          </router-link>
        </div>
      </article>
    </div>
  </AsyncState>
</template>
