<script setup>
// 班级内容主体：座位表 + 趋势 + 名单 + 各科平均 + 未分班区。
// 由 /classes（下拉选班）和 /classes/:id（深链接）两个宿主复用；
// 多班时页头出现下拉框切换，单班只显示班级名称。
import { computed, onMounted, ref, watch } from "vue"
import { useRouter } from "vue-router"
import api from "../api"
import Icon from "./Icon.vue"
import PageHeader from "./PageHeader.vue"
import AsyncState from "./AsyncState.vue"
import FormField from "./FormField.vue"
import LineChart from "./LineChart.vue"
import SeatingBoard from "./SeatingBoard.vue"
import { ask } from "../confirm"
import { notify, runUndoable } from "../feedback"
import { setPageTitle } from "../title"
import {
  classBreadcrumbLabel,
  friendlyError,
  genderLabel,
  subject,
  subjectColor,
  t,
} from "../strings"

const props = defineProps({ classId: { type: String, required: true } })
const emit = defineEmits(["switch", "create", "changed"])
const router = useRouter()

const detail = ref(null)
const loading = ref(true)
const error = ref("")

const allClasses = ref([]) // 仅供下拉框：>1 个班时显示
const duplicateNames = ref(new Set())

const editing = ref(false)
const editSaving = ref(false)
const editError = ref("")
const editForm = ref({})

function emptyEditForm(c) {
  return {
    name: c.name || "",
    academic_year: c.academic_year,
  }
}

async function load() {
  loading.value = true
  error.value = ""
  try {
    detail.value = await api.get(`/classes/${props.classId}`)
    setPageTitle(classBreadcrumbLabel(detail.value.class.name, detail.value.class.academic_year))
  } catch (e) {
    error.value = friendlyError(e)
  } finally {
    loading.value = false
  }
}

async function loadClassList() {
  try {
    allClasses.value = await api.get("/classes")
    const seen = new Map()
    for (const c of allClasses.value) seen.set(c.name, (seen.get(c.name) || 0) + 1)
    duplicateNames.value = new Set([...seen.entries()].filter(([, n]) => n > 1).map(([name]) => name))
  } catch {
    allClasses.value = [] // 下拉框数据失败不阻塞页面
  }
}

onMounted(() => {
  load()
  loadClassList()
  loadUnassigned()
})
watch(() => props.classId, load)

function classLabel(c) {
  return duplicateNames.value.has(c.name) ? `${c.name}（${c.academic_year}）` : c.name
}

function onPickClass(ev) {
  const id = ev.target.value
  if (id && id !== props.classId) emit("switch", id)
}

function startEdit() {
  editing.value = true
  editError.value = ""
  editForm.value = emptyEditForm(detail.value.class)
}
function cancelEdit() {
  editing.value = false
  editForm.value = {}
  editError.value = ""
}

async function saveEdit() {
  editError.value = ""
  if (!editForm.value.name.trim()) {
    editError.value = t("classes.nameRequired")
    return
  }
  editSaving.value = true
  try {
    const updated = await api.patch(`/classes/${props.classId}`, {
      name: editForm.value.name.trim(),
      academic_year: editForm.value.academic_year.trim(),
    })
    detail.value.class = { ...detail.value.class, ...updated }
    editing.value = false
    notify({ tone: "ok", title: t("common.saved"), timeout: 2400 })
    await load()
    await loadClassList()
  } catch (e) {
    editError.value = friendlyError(e)
  } finally {
    editSaving.value = false
  }
}

async function removeClass() {
  const name = detail.value.class.name
  const ok = await ask({
    title: `删除班级「${name}」？`,
    consequences: [t("classes.deleteConfirm"), "班级里还有学生时，系统会拒绝删除。"],
    confirmLabel: t("action.delete"),
  })
  if (!ok) return

  runUndoable({
    title: `已删除班级「${name}」`,
    run: () => api.delete(`/classes/${props.classId}`),
    onDone: () => {
      emit("changed")
      router.replace("/classes")
    },
  })
}

// 语数英 120 分、其余 100 分——原始分同轴比较不公平，统一画成得分率（%）
const trendChart = computed(() => {
  const trend = detail.value?.trend
  if (!trend || !trend.exams.length) return null
  // 本班各科都没成绩的考试（未录入/未参加）不进图表
  const kept = trend.exams
    .map((_, i) => i)
    .filter((i) => trend.series.some((s) => s.values[i] != null))
  if (!kept.length) return null
  const pick = (arr) => kept.map((i) => arr[i])
  const series = trend.series.map((s) => {
    const full = s.full_score || 100
    return {
      key: s.subject,
      label: subject(s.subject),
      color: subjectColor(s.subject),
      values: pick(s.values).map((v) => (v == null ? null : Math.round((v / full) * 1000) / 10)),
    }
  })
  return {
    labels: pick(trend.exams).map((e) => e.name),
    dates: pick(trend.exams).map((e) => e.exam_date),
    series,
    yMax: 100,
    formatTip: (s, pct, i) => {
      const origIdx = kept[i]
      const orig = trend.series.find((x) => x.subject === s.key)
      const raw = orig ? orig.values[origIdx] : null
      const full = orig ? orig.full_score || 100 : 100
      return raw != null ? `${pct}%（${raw}/${full} 分）` : `${pct}%`
    },
  }
})

const hasScores = computed(() => detail.value && detail.value.averages.length > 0)

// 各科平均成绩附上与上次考试相比的变化：取该科最近两场有成绩的平均分之差
const averagesWithDelta = computed(() => {
  if (!detail.value) return []
  const bySubject = new Map(
    (detail.value.trend?.series || []).map((s) => [s.subject, s.values.filter((v) => v != null)])
  )
  return detail.value.averages.map((a) => {
    const vals = bySubject.get(a.subject)
    const delta =
      vals && vals.length >= 2
        ? Math.round((vals[vals.length - 1] - vals[vals.length - 2]) * 10) / 10
        : null
    return { ...a, delta }
  })
})

function fmtDelta(delta) {
  return `${delta > 0 ? "↑" : "↓"}${Math.abs(delta).toFixed(1)}`
}

// ------------------------------------------------------------------ 学生进出班

const showAddStudent = ref(false)
const unassigned = ref([])
const addStudentLoading = ref(false)
const assigningId = ref("")
const addStudentError = ref("")

async function loadUnassigned() {
  const students = await api.get("/students")
  unassigned.value = students.filter((s) => s.status === "active" && !s.class)
}

async function openAddStudent() {
  showAddStudent.value = true
  addStudentError.value = ""
  addStudentLoading.value = true
  try {
    await loadUnassigned()
  } catch (e) {
    addStudentError.value = friendlyError(e)
  } finally {
    addStudentLoading.value = false
  }
}

function closeAddStudent() {
  showAddStudent.value = false
  addStudentError.value = ""
  assigningId.value = ""
}

async function assignStudent(student) {
  addStudentError.value = ""
  assigningId.value = student.id
  try {
    await api.patch(`/students/${student.id}`, { class_id: props.classId })
    notify({ tone: "ok", title: t("classdetail.studentAdded", { name: student.name }), timeout: 2400 })
    await Promise.all([load(), loadUnassigned()])
  } catch (e) {
    addStudentError.value = friendlyError(e)
  } finally {
    assigningId.value = ""
  }
}

// ------------------------------------------------------------------ 拖拽进出班

// 正在拖拽的学生 { id, name, from }；from 为班级 id，未分班是 null
const dragStudent = ref(null)
// 当前高亮的投放目标："roster"（名单，投放=入班）| "pool"（未分班，投放=出班）
const dropTarget = ref(null)
const dropTargetActive = computed(() => dragStudent.value !== null)

function onRosterDragStart(student, ev) {
  dragStudent.value = { id: student.id, name: student.name, from: detail.value.class.id }
  ev.dataTransfer.setData("application/x-student-move", JSON.stringify(dragStudent.value))
  ev.dataTransfer.effectAllowed = "move"
}

function onPoolDragStart(student, ev) {
  dragStudent.value = { id: student.id, name: student.name, from: null }
  ev.dataTransfer.setData("application/x-student-move", JSON.stringify(dragStudent.value))
  ev.dataTransfer.effectAllowed = "move"
}

function onDragEnd() {
  dragStudent.value = null
  dropTarget.value = null
}

function onDragLeave(target, ev) {
  // 在卡片子元素间移动也会触发 dragleave，只有真正离开卡片才熄灭高亮
  if (!ev.currentTarget.contains(ev.relatedTarget)) {
    if (dropTarget.value === target) dropTarget.value = null
  }
}

function onDropRoster() {
  const d = dragStudent.value
  dropTarget.value = null
  dragStudent.value = null
  if (!d || d.from === props.classId) return // 原班投放 = 什么都不做
  assignStudent(d)
}

async function onDropPool() {
  const d = dragStudent.value
  dropTarget.value = null
  dragStudent.value = null
  if (!d || d.from === null) return
  try {
    await api.patch(`/students/${d.id}`, { class_id: null })
    notify({ tone: "ok", title: `已把 ${d.name} 移出班级`, timeout: 3000 })
    await Promise.all([load(), loadUnassigned()])
  } catch (e) {
    notify({ tone: "danger", title: "移出失败", detail: friendlyError(e) })
  }
}

function fmtPct(score, full) {
  return full ? Math.round((score / full) * 100) : 0
}
</script>

<template>
  <AsyncState
    :loading="loading"
    :error="error"
    :empty="!loading && !error && !detail"
    empty-title="班级详情没能加载"
    :rows="4"
    @retry="load"
  >
      <PageHeader :title="detail.class.name">
        <template v-if="allClasses.length > 1" #title>
          <label class="class-switcher">
            <select
              class="class-switcher__select"
              :value="classId"
              aria-label="选择班级"
              @change="onPickClass"
            >
              <option v-for="c in allClasses" :key="c.id" :value="c.id">{{ classLabel(c) }}</option>
            </select>
            <Icon name="chevron-down" :size="18" class="class-switcher__chevron" />
          </label>
        </template>
        <template #actions>
          <button class="btn btn--ghost" @click="emit('create')">
            <Icon name="plus" :size="15" /> {{ t("classes.create") }}
          </button>
          <button v-if="!editing" class="btn" @click="startEdit">
            <Icon name="pencil" :size="15" /> {{ t("action.edit") }}
          </button>
        </template>
      </PageHeader>

      <!-- 就地编辑 -->
      <div v-if="editing" class="card" style="max-width: 720px">
        <div class="card__head">
          <h2 class="card__title">{{ t("action.edit") }} · {{ detail.class.name }}</h2>
        </div>
        <form class="card__body" @submit.prevent="saveEdit">
          <div class="form-grid">
            <FormField :label="t('classes.name')" required>
              <input v-model="editForm.name" class="input" type="text" maxlength="60" />
            </FormField>
            <FormField :label="t('classes.year')">
              <input v-model="editForm.academic_year" class="input" type="text" />
            </FormField>
          </div>

          <p v-if="editError" class="field__error" style="margin-bottom: 12px">
            <Icon name="alert-circle" :size="13" /> {{ editError }}
          </p>

          <div class="form-actions">
            <button type="submit" class="btn btn--primary" :disabled="editSaving">
              <span v-if="editSaving" class="spinner" />
              {{ editSaving ? t("action.saving") : t("action.save") }}
            </button>
            <button type="button" class="btn btn--ghost" @click="cancelEdit">
              {{ t("action.cancel") }}
            </button>
          </div>

          <div class="form-actions form-actions--danger">
            <button
              type="button"
              class="btn btn--danger"
              :disabled="editSaving"
              @click="removeClass"
            >
              <Icon name="trash" :size="14" /> {{ t("action.delete") }}
            </button>
          </div>
        </form>
      </div>

      <!-- 座位表：班级页默认显示，标题行带行列设置，就地拖拽编辑 -->
      <SeatingBoard :class-id="classId" :students="detail.students" />

      <div class="split">
        <div>
          <div class="card">
            <div class="card__head">
              <div>
                <h2 class="card__title"><Icon name="trending" :size="16" /> {{ t("classdetail.trendTitle") }}</h2>
                <p class="card__desc">{{ t("classdetail.trendSub") }}</p>
              </div>
            </div>
            <div class="card__body">
              <div v-if="!trendChart || !trendChart.series.length" class="state state--in-card">
                <p class="state__desc">{{ t("classdetail.noScores") }}</p>
              </div>
              <LineChart
                v-else
                :labels="trendChart.labels"
                :dates="trendChart.dates"
                :series="trendChart.series"
                :y-max="trendChart.yMax"
                :format-tip="trendChart.formatTip"
              />
            </div>
          </div>

          <div
            class="card"
            :class="{ 'card--drop': dropTargetActive && dropTarget === 'roster' && dragStudent.from !== classId }"
            @dragover.prevent="dropTarget = 'roster'"
            @dragleave="onDragLeave('roster', $event)"
            @drop.prevent="onDropRoster"
          >
            <div class="card__head">
              <h2 class="card__title"><Icon name="users" :size="16" /> {{ t("classdetail.roster") }}</h2>
              <span class="pill pill--muted pill--count">{{ detail.students.length }}</span>
            </div>
            <div class="card__body">
              <div v-if="detail.students.length" class="chips">
                <router-link
                  v-for="s in detail.students"
                  :key="s.id"
                  :to="`/students/${s.id}`"
                  class="chip"
                  :title="s.admission_no"
                  draggable="true"
                  @dragstart="onRosterDragStart(s, $event)"
                  @dragend="onDragEnd"
                >
                  {{ s.name }}
                  <span class="muted" style="font-size: 12px">{{ genderLabel(s.gender) }}</span>
                </router-link>
              </div>
              <div v-else class="state state--in-card">
                <p class="state__desc">{{ t("classes.noStudents") }}</p>
              </div>
            </div>
          </div>
        </div>

        <div class="card">
          <div class="card__head">
            <h2 class="card__title"><Icon name="chart" :size="16" /> {{ t("classdetail.averages") }}</h2>
          </div>
          <div class="card__body">
            <div v-if="!hasScores" class="state state--in-card">
              <p class="state__desc">{{ t("classdetail.noScores") }}</p>
            </div>
            <div v-for="a in averagesWithDelta" :key="a.subject" class="stat stat--plain">
              <div class="stat__label">{{ subject(a.subject) }}</div>
              <div class="stat__value tnum">
                {{ a.avg ?? t("common.none") }}
                <span
                  v-if="a.delta != null"
                  class="tnum score-pill__delta"
                  :style="{ color: a.delta >= 0 ? 'var(--ok)' : 'var(--warn)' }"
                  title="与上一场考试的平均分相比"
                >{{ fmtDelta(a.delta) }}</span>
              </div>
              <div class="stat__sub">
                {{ t("exam.outOf") }} {{ a.full_score }}（{{ fmtPct(a.avg, a.full_score) }}%） ·
                {{ t("exam.exams", { count: a.count }) }}
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 未分班：拖出班学生回到这里，也可从名单拖走 -->
      <section
        v-if="unassigned.length"
        class="card class-unassigned"
        :class="{ 'card--drop': dropTargetActive && dropTarget === 'pool' && dragStudent.from !== null }"
        style="margin-top: var(--sp-5)"
        @dragover.prevent="dropTarget = 'pool'"
        @dragleave="onDragLeave('pool', $event)"
        @drop.prevent="onDropPool"
      >
        <div class="card__head">
          <div class="grow">
            <h2 class="card__title" style="font-size: 16px">{{ t("students.ungrouped") }}</h2>
            <p class="card__desc">
              {{ t("profile.studentsCount", { n: unassigned.length }) }}
              · {{ t("classes.unassignedHint") }}
            </p>
          </div>
          <router-link to="/students" class="btn btn--sm btn--ghost">
            {{ t("classes.viewUnassigned") }}
          </router-link>
        </div>
        <div class="card__body card__body--tight">
          <div class="chips">
            <router-link
              v-for="s in unassigned"
              :key="s.id"
              :to="`/students/${s.id}`"
              class="chip"
              draggable="true"
              @dragstart="onPoolDragStart(s, $event)"
              @dragend="onDragEnd"
            >
              {{ s.name }}
              <span class="muted tnum" style="font-size: 12px">{{ s.admission_no }}</span>
            </router-link>
          </div>
        </div>
      </section>

      <div
        v-if="showAddStudent"
        class="overlay"
        role="dialog"
        aria-modal="true"
        :aria-label="t('classdetail.addStudentTitle')"
        @click.self="closeAddStudent"
      >
        <div class="modal">
          <div class="modal__head">
            <div class="grow">
              <h2 class="modal__title">{{ t("classdetail.addStudentTitle") }}</h2>
              <p class="card__desc" style="margin: 6px 0 0">{{ t("classdetail.addStudentHint") }}</p>
            </div>
            <button type="button" class="icon-btn" :aria-label="t('action.close')" @click="closeAddStudent">
              <Icon name="close" :size="16" />
            </button>
          </div>
          <div class="modal__body">
            <p v-if="addStudentLoading" class="state__desc" style="text-align: center; padding: 12px 0">
              {{ t("common.loading") }}
            </p>
            <p v-else-if="addStudentError" class="field__error">
              <Icon name="alert-circle" :size="13" /> {{ addStudentError }}
            </p>
            <div v-else-if="!unassigned.length" class="state state--in-card">
              <p class="state__desc">{{ t("classdetail.addStudentEmpty") }}</p>
            </div>
            <div v-else class="mention-picker__list card card--nested">
              <button
                v-for="s in unassigned"
                :key="s.id"
                type="button"
                class="mention-picker__row"
                :disabled="assigningId === s.id"
                @click="assignStudent(s)"
              >
                <span class="mention-picker__name">
                  {{ s.name }}
                  <span v-if="s.admission_no" class="muted" style="font-size: 12px">{{ s.admission_no }}</span>
                </span>
                <span v-if="assigningId === s.id" class="spinner" />
                <Icon v-else name="plus" :size="14" style="color: var(--muted)" />
              </button>
            </div>
          </div>
          <div class="modal__foot">
            <button type="button" class="btn btn--ghost" @click="closeAddStudent">
              {{ t("action.close") }}
            </button>
          </div>
        </div>
      </div>
  </AsyncState>
</template>
