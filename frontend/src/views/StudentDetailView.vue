<script setup>
// 学生档案：资料、标签、成绩、时间线。
// 所有删除都走「撤销窗口」，成绩更正会留下痕迹，标签可一键复用。
import { computed, onMounted, ref, watch } from "vue"
import { useRouter } from "vue-router"
import api from "../api"
import Icon from "../components/Icon.vue"
import PageHeader from "../components/PageHeader.vue"
import AsyncState from "../components/AsyncState.vue"
import FormField from "../components/FormField.vue"
import LineChart from "../components/LineChart.vue"
import Timeline from "../components/Timeline.vue"
import { ask } from "../confirm"
import { notify, runUndoable } from "../feedback"
import { setPageTitle } from "../title"
import {
  dateLocale,
  friendlyError,
  genderLabel,
  GENDER_OPTIONS,
  studentStatusLabel,
  subject,
  subjectColor,
  COMMON_SUBJECT_KEYS,
  tagStyle,
  t,
} from "../strings"

const props = defineProps({ id: { type: String, required: true } })
const router = useRouter()

const student = ref(null)
const timeline = ref([])
const classes = ref([])

const loading = ref(true)
const error = ref("")

// inline score editing
const editingId = ref(null)
const editValue = ref(null)
const editError = ref("")

// default to the latest exam; expand to see full history
const SCORE_EXAMS_VISIBLE = 1
const showAllScores = ref(false)

// tag editor
const tagFormOpen = ref(false)
const tagSaving = ref(false)
const tagError = ref("")
const tagForm = ref({ name: "", color: "#2f5b44" })
const allTags = ref([])

// profile edit
const profileEditing = ref(false)
const profileSaving = ref(false)
const profileError = ref("")
const profileForm = ref({})

const STATUS_OPTIONS = [
  { value: "active", label: t("status.active") },
  { value: "inactive", label: t("status.inactive") },
  { value: "graduated", label: t("status.graduated") },
]

async function load() {
  loading.value = true
  error.value = ""
  showAllScores.value = false
  try {
    const tasks = [
      api.get(`/students/${props.id}`),
      api.get(`/students/${props.id}/timeline`),
    ]
    if (!classes.value.length) {
      tasks.push(api.get("/classes").catch(() => []))
    }
    const res = await Promise.all(tasks)
    student.value = res[0]
    timeline.value = res[1]
    setPageTitle(res[0].name)
    if (res.length > 2) classes.value = res[2]
  } catch (e) {
    error.value = friendlyError(e)
  } finally {
    loading.value = false
  }
}
onMounted(load)
watch(() => props.id, load)

// ------------------------------------------------------------------ 时间线

// 时间线上考试事件的成绩描述：任一科目录入了成绩才显示，成绩取当前值
//（更正后 scores 里就是最新分），按固定科目顺序排列
const examScoreDesc = computed(() => {
  const desc = new Map()
  for (const row of student.value?.scores ?? []) {
    if (row.status !== "entered" || row.score == null) continue
    const key = row.exam_id || `${row.exam_date}|${row.exam_name}`
    let parts = desc.get(key)
    if (!parts) {
      parts = []
      desc.set(key, parts)
    }
    const n = Number(row.score)
    parts.push({ subject: row.subject, text: `${subject(row.subject)} ${n % 1 === 0 ? n : n.toFixed(1)}` })
  }
  const ordered = new Map()
  for (const [key, parts] of desc) {
    parts.sort(
      (a, b) =>
        (COMMON_SUBJECT_KEYS.indexOf(a.subject) === -1
          ? 99
          : COMMON_SUBJECT_KEYS.indexOf(a.subject)) -
        (COMMON_SUBJECT_KEYS.indexOf(b.subject) === -1
          ? 99
          : COMMON_SUBJECT_KEYS.indexOf(b.subject))
    )
    ordered.set(key, parts.map((p) => p.text).join(" · "))
  }
  return ordered
})

const timelineWithScores = computed(() =>
  timeline.value.map((e) =>
    e.event_type === "exam" && examScoreDesc.value.has(e.id)
      ? { ...e, score_summary: examScoreDesc.value.get(e.id) }
      : e
  )
)

// ------------------------------------------------------------------ 成绩

const hiddenScoreCount = computed(() =>
  Math.max(0, allExamScoreGroups.value.length - SCORE_EXAMS_VISIBLE)
)

function buildExamScoreGroups(rows) {
  const groups = []
  const byExam = new Map()
  for (const row of rows) {
    const key = row.exam_id || `${row.exam_date}|${row.exam_name}`
    let g = byExam.get(key)
    if (!g) {
      g = { exam_id: row.exam_id, exam_name: row.exam_name, exam_date: row.exam_date, results: [] }
      byExam.set(key, g)
      groups.push(g)
    }
    g.results.push(row)
  }
  for (const g of groups) {
    g.results.sort((a, b) => {
      const ia = COMMON_SUBJECT_KEYS.indexOf(a.subject)
      const ib = COMMON_SUBJECT_KEYS.indexOf(b.subject)
      return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib)
    })
  }
  groups.sort((a, b) => b.exam_date.localeCompare(a.exam_date))
  return groups
}

const allExamScoreGroups = computed(() => {
  if (!student.value?.scores.length) return []
  return buildExamScoreGroups(student.value.scores)
})

// 所选场次在折线图（时间正序）中的下标；-1 表示未选，即默认最近一场
const selectedTrendIndex = ref(-1)

const examScoreGroups = computed(() => {
  const all = allExamScoreGroups.value
  if (!all.length) return []
  if (showAllScores.value || all.length <= SCORE_EXAMS_VISIBLE) return all
  // 成绩组按时间倒序：图上下标 i 对应组下标 n-1-i
  const n = Math.min(all.length, scoreTrend.value?.labels.length ?? 0)
  const gi =
    selectedTrendIndex.value < 0 || selectedTrendIndex.value >= n
      ? 0
      : Math.min(n - 1 - selectedTrendIndex.value, all.length - SCORE_EXAMS_VISIBLE)
  return all.slice(gi, gi + SCORE_EXAMS_VISIBLE)
})

// per-subject delta vs the same subject on the previous exam sitting
const scoreDeltas = computed(() => {
  const deltas = new Map()
  const prev = {}
  const chronological = [...allExamScoreGroups.value].sort(
    (a, b) => a.exam_date.localeCompare(b.exam_date),
  )
  for (const g of chronological) {
    for (const row of g.results) {
      if (row.status === "entered" && row.score != null) {
        const last = prev[row.subject]
        deltas.set(
          row.result_id,
          last != null ? Math.round((row.score - last) * 10) / 10 : null,
        )
        prev[row.subject] = row.score
      } else {
        deltas.set(row.result_id, null)
      }
    }
  }
  return deltas
})

// multi-subject score trend: one line per subject across exams (chronological)
// 语数英 120 分、其余 100 分——统一换算成得分率（%）才可比
const scoreTrend = computed(() => {
  if (!student.value || !student.value.scores.length) return null
  const byExam = new Map()
  const fullBySubject = {}
  const colorBySubject = {}
  for (const row of student.value.scores) {
    fullBySubject[row.subject] = row.full_score
    if (row.subject_color && !colorBySubject[row.subject]) {
      colorBySubject[row.subject] = row.subject_color
    }
    const key = `${row.exam_date}|${row.exam_id}`
    if (!byExam.has(key)) {
      byExam.set(key, { label: row.exam_name, date: row.exam_date, perSubject: {} })
    }
    byExam.get(key).perSubject[row.subject] = row.score
  }
  const exams = [...byExam.values()].sort((a, b) => a.date.localeCompare(b.date))
  const subjects = [...new Set(student.value.scores.map((s) => s.subject))]
  const series = subjects.map((sub) => {
    const full = fullBySubject[sub] || 100
    return {
      key: sub,
      label: subject(sub),
      color: subjectColor(sub, colorBySubject[sub]),
      values: exams.map((e) => {
        const v = e.perSubject[sub]
        return v == null ? null : Math.round((v / full) * 1000) / 10
      }),
    }
  })
  return {
    labels: exams.map((e) => e.label),
    dates: exams.map((e) => e.date),
    series,
    yMax: 100,
    formatTip: (s, pct, i) => {
      const raw = exams[i]?.perSubject[s.key]
      const full = fullBySubject[s.key] || 100
      return raw == null ? `${pct}%` : `${pct}%（${raw}/${full} 分）`
    },
  }
})

function rowColor(row) {
  return subjectColor(row.subject, row.subject_color)
}

function fmtScore(row) {
  if (row.status !== "entered" || row.score == null) return "—"
  return Number(row.score).toFixed(1)
}

function fmtDelta(delta) {
  if (delta == null || delta === 0) return ""
  return `${delta > 0 ? "↑" : "↓"}${Math.abs(delta).toFixed(1)}`
}

function fmtCorrectionDelta(correction) {
  if (!correction || correction.old == null || correction.new == null) return ""
  const d = Math.round((correction.new - correction.old) * 10) / 10
  if (d === 0) return ""
  return `${d > 0 ? "+" : ""}${d.toFixed(1)}`
}

function scorePillTitle(row) {
  const parts = [
    `${subject(row.subject)} ${fmtScore(row)}/${Number(row.full_score).toFixed(1)}`,
  ]
  const cd = fmtCorrectionDelta(row.correction)
  if (cd) {
    parts.push(`已更正 ${cd}${row.correction.reason ? `（${row.correction.reason}）` : ""}`)
  }
  const delta = scoreDelta(row.result_id)
  if (delta != null) parts.push(`较上一场 ${fmtDelta(delta)}`)
  parts.push("点击更正")
  return parts.join(" · ")
}

function scoreDelta(resultId) {
  return scoreDeltas.value.get(resultId) ?? null
}

function deltaStyle(delta) {
  if (delta == null) return {}
  return { color: delta >= 0 ? "var(--ok)" : "var(--warn)" }
}

function startEdit(row) {
  editingId.value = row.result_id
  editValue.value = row.score
  editError.value = ""
}
function cancelEdit() {
  editingId.value = null
  editError.value = ""
}

async function saveEdit(row) {
  editError.value = ""
  const value = Number(editValue.value)
  if (editValue.value === "" || editValue.value == null || Number.isNaN(value)) {
    editError.value = "请填写一个数字"
    return
  }
  if (value < 0 || value > row.full_score) {
    editError.value = `分数要在 0 到 ${row.full_score} 之间`
    return
  }
  if (value === row.score) {
    cancelEdit()
    return
  }
  try {
    await api.patch(`/results/${row.result_id}`, {
      score: value,
      reason: t("detail.editReason"),
    })
    editingId.value = null
    await load()
    notify({ tone: "ok", title: `${subject(row.subject)} 成绩已更正为 ${value}`, timeout: 3000 })
  } catch (e) {
    editError.value = friendlyError(e)
  }
}

// ------------------------------------------------------------- 添加成绩弹窗

const scoreDialogOpen = ref(false)
const scoreDialogError = ref("")
const scoreSaving = ref(false)
const examOptions = ref([])
const examListOpen = ref(false)
const scoreForm = ref({ examId: "", values: {}, attended: {} })

const chosenExam = computed(
  () => examOptions.value.find((e) => e.id === scoreForm.value.examId) ?? null
)

async function openScoreDialog() {
  scoreDialogOpen.value = true
  scoreDialogError.value = ""
  examListOpen.value = false
  scoreForm.value = { examId: "", values: {}, attended: {} }
  if (!examOptions.value.length) {
    try {
      examOptions.value = await api.get("/exams")
    } catch (e) {
      scoreDialogError.value = friendlyError(e)
    }
  }
}

function closeScoreDialog() {
  scoreDialogOpen.value = false
  examListOpen.value = false
}

function pickExam(e) {
  scoreForm.value.examId = e.id
  examListOpen.value = false
  onScoreExamChange()
}

function onScoreExamChange() {
  // 换考试就重置：默认全部「参加考试」，取消勾选才记缺考
  const attended = {}
  for (const s of chosenExam.value?.subjects ?? []) attended[s.subject] = true
  scoreForm.value.values = {}
  scoreForm.value.attended = attended
}

async function saveScores() {
  scoreDialogError.value = ""
  const exam = chosenExam.value
  if (!exam) {
    scoreDialogError.value = "请先选择考试"
    return
  }
  const scores = []
  for (const s of exam.subjects) {
    const raw = (scoreForm.value.values[s.subject] ?? "").toString().trim()
    if (scoreForm.value.attended[s.subject] === false) {
      // 取消了「参加考试」→ 记缺考
      scores.push({ subject: s.subject, absent: true })
      continue
    }
    if (!raw) continue // 参加了但这科没填分 → 不录入
    const value = Number(raw)
    if (Number.isNaN(value)) {
      scoreDialogError.value = `${subject(s.subject)} 的成绩要填数字`
      return
    }
    if (value < 0 || value > s.full_score) {
      scoreDialogError.value = `${subject(s.subject)} 的成绩需在 0 到 ${s.full_score} 之间`
      return
    }
    scores.push({ subject: s.subject, score: value })
  }
  if (!scores.length) {
    scoreDialogError.value = "至少填写一科成绩，或勾选缺考"
    return
  }
  scoreSaving.value = true
  try {
    await api.post(`/exams/${exam.id}/scores`, {
      student_id: props.id,
      scores,
    })
    scoreDialogOpen.value = false
    await load()
    notify({ tone: "ok", title: t("detail.scoreAdded"), timeout: 3000 })
  } catch (e) {
    scoreDialogError.value = friendlyError(e)
  } finally {
    scoreSaving.value = false
  }
}

// ------------------------------------------------------------------ 标签

const tagSuggestions = computed(() => {
  const own = new Set((student.value?.tags ?? []).map((x) => x.id))
  return allTags.value.filter((x) => !own.has(x.id))
})

function syncTags(tags) {
  if (student.value) student.value.tags = tags
}

async function refreshSuggestions() {
  try {
    allTags.value = await api.get("/tags")
  } catch {
    allTags.value = []
  }
}

async function addTag() {
  tagError.value = ""
  if (!tagForm.value.name.trim()) {
    tagError.value = t("detail.tagNameRequired")
    return
  }
  tagSaving.value = true
  try {
    const created = await api.post(`/students/${props.id}/tags`, {
      name: tagForm.value.name.trim(),
      color: tagForm.value.color,
    })
    syncTags([...(student.value?.tags ?? []), created])
    tagForm.value.name = ""
    tagFormOpen.value = false
    await refreshSuggestions()
  } catch (e) {
    tagError.value = friendlyError(e)
  } finally {
    tagSaving.value = false
  }
}

async function attachExisting(tag) {
  tagError.value = ""
  const snapshot = student.value?.tags ?? []
  syncTags([...snapshot, tag])
  try {
    await api.post(`/students/${props.id}/tags`, { name: tag.name, color: tag.color })
    await refreshSuggestions()
  } catch (e) {
    syncTags(snapshot) // 失败就恢复原样，不留下假象
    tagError.value = friendlyError(e)
  }
}

async function toggleTagForm() {
  tagFormOpen.value = !tagFormOpen.value
  if (tagFormOpen.value) await refreshSuggestions()
}

async function removeTag(tag) {
  const snapshot = student.value?.tags ?? []
  syncTags(snapshot.filter((x) => x.id !== tag.id))
  runUndoable({
    title: `已移除标签「${tag.name}」`,
    run: () => api.delete(`/students/${props.id}/tags/${tag.id}`),
    onUndo: () => syncTags(snapshot),
    onDone: () => refreshSuggestions(),
  })
}

// -------------------------------------------------------------- 资料编辑

// 监护人管理：添加（同手机号自动合并为同一人）与解除链接；名字点击进监护人详情
const guardianFormOpen = ref(false)
const guardianForm = ref({ name: "", phone: "", relationship: "", address: "" })
const guardianSaving = ref(false)
const guardianError = ref("")

function openGuardianForm() {
  guardianFormOpen.value = true
  guardianForm.value = { name: "", phone: "", relationship: "", address: "" }
  guardianError.value = ""
}

async function addGuardian() {
  if (!guardianForm.value.name.trim()) {
    guardianError.value = t("detail.nameRequired")
    return
  }
  guardianSaving.value = true
  guardianError.value = ""
  try {
    await api.post(`/students/${props.id}/guardians`, {
      name: guardianForm.value.name.trim(),
      phone: guardianForm.value.phone.trim() || null,
      relationship: guardianForm.value.relationship.trim() || null,
      address: guardianForm.value.address.trim() || null,
    })
    guardianFormOpen.value = false
    await load()
    notify({ tone: "ok", title: t("common.saved"), timeout: 2400 })
  } catch (e) {
    guardianError.value = friendlyError(e)
  } finally {
    guardianSaving.value = false
  }
}

async function removeGuardian(g) {
  const ok = await ask({
    title: `解除与 ${g.name} 的监护人关联？`,
    consequences: ["只解除与这名学生的关联，监护人账户本身不会被删除。"],
    confirmLabel: t("action.delete"),
  })
  if (!ok) return
  try {
    await api.delete(`/students/${props.id}/guardians/${g.id}`)
    await load()
  } catch (e) {
    notify({ tone: "error", title: friendlyError(e) })
  }
}

function startProfileEdit() {
  profileEditing.value = true
  profileError.value = ""
  profileForm.value = {
    name: student.value.name,
    admission_no: student.value.admission_no || "",
    gender: student.value.gender || "",
    birth_date: student.value.birth_date || "",
    address: student.value.address || "",
    status: student.value.status || "active",
    class_id: student.value.class?.id ?? null,
  }
}
function cancelProfileEdit() {
  profileEditing.value = false
  profileForm.value = {}
  profileError.value = ""
  guardianFormOpen.value = false
  guardianError.value = ""
}

async function saveProfileEdit() {
  profileError.value = ""
  if (!profileForm.value.name.trim()) {
    profileError.value = t("detail.nameRequired")
    return
  }
  if (!profileForm.value.admission_no.trim()) {
    profileError.value = t("detail.admissionNoRequired")
    return
  }
  profileSaving.value = true
  try {
    await api.patch(`/students/${props.id}`, {
      name: profileForm.value.name.trim(),
      admission_no: profileForm.value.admission_no.trim(),
      gender: profileForm.value.gender || null,
      birth_date: profileForm.value.birth_date || null,
      address: profileForm.value.address.trim() || null,
      status: profileForm.value.status,
      class_id: profileForm.value.class_id || null,
    })
    cancelProfileEdit()
    await load()
    notify({ tone: "ok", title: t("common.saved"), timeout: 2400 })
  } catch (e) {
    profileError.value = friendlyError(e)
  } finally {
    profileSaving.value = false
  }
}

// ---------------------------------------------------------------- 删除

async function removeStudent() {
  const ok = await ask({
    title: `删除学生「${student.value.name}」？`,
    consequences: [t("detail.deleteConfirm")],
    confirmLabel: t("action.delete"),
  })
  if (!ok) return

  const name = student.value.name
  runUndoable({
    title: `已删除学生「${name}」`,
    detail: "返回列表前都可以撤销",
    run: () => api.delete(`/students/${props.id}`),
    successDetail: "已返回学生列表",
    onDone: () => router.replace("/students"),
  })
}

// ------------------------------------------------------------ 时间线导航

function addEvent() {
  router.push(`/students/${props.id}/events/new`)
}

function addComment() {
  router.push(`/students/${props.id}/comments/new`)
}

function goSummaries() {
  router.push(`/students/${props.id}/summaries`)
}

function fmtDate(d) {
  return d
    ? new Date(d).toLocaleDateString(dateLocale(), { year: "numeric", month: "short", day: "numeric" })
    : "—"
}

const headerMeta = computed(() => {
  if (!student.value) return []
  const s = student.value
  const rows = [{ label: t("th.status"), value: studentStatusLabel(s.status) }]
  if (s.gender) rows.push({ label: t("new.gender"), value: genderLabel(s.gender) })
  if (s.birth_date) rows.push({ label: t("detail.born"), value: fmtDate(s.birth_date) })
  return rows
})
</script>

<template>
  <AsyncState
    :loading="loading"
    :error="error"
    :empty="!loading && !error && !student"
    empty-title="学生档案没能加载"
    :rows="5"
    @retry="load"
  >
      <PageHeader
        :title="student.name"
        :subtitle="`${student.admission_no} · ${student.class ? student.class.name : t('students.ungrouped')}`"
      >
        <template #meta>
          <div class="row-wrap page-head__meta-row">
            <span v-for="m in headerMeta" :key="m.label" class="pill pill--outline">
              {{ m.label }} <b class="tnum">{{ m.value }}</b>
            </span>
          </div>

          <!-- 标签独立一行；「添加标签」复用标签外观（虚线空底） -->
          <div class="row-wrap page-head__tag-row">
            <span
              v-for="tag in student.tags"
              :key="tag.id"
              class="tag"
              :style="tagStyle(tag.color)"
            >
              {{ tag.name }}
              <button class="tag__x" :aria-label="`移除标签 ${tag.name}`" @click="removeTag(tag)">
                <Icon name="close" :size="10" />
              </button>
            </span>
            <button
              type="button"
              class="tag tag--add"
              :class="{ 'is-open': tagFormOpen }"
              @click="toggleTagForm"
            >
              <Icon name="tag" :size="11" /> {{ t("detail.addTag") }}
            </button>
          </div>

          <div v-if="tagFormOpen" class="card card--nested page-head__tag-form">
            <div class="card__body card__body--tight">
              <div v-if="tagSuggestions.length" class="row-wrap" style="margin-bottom: 10px">
                <span class="field__hint">{{ t("detail.tagInUse") }}</span>
                <button
                  v-for="s in tagSuggestions"
                  :key="s.id"
                  class="chip"
                  :style="{ borderColor: s.color, color: s.color }"
                  @click="attachExisting(s)"
                >
                  <Icon name="plus" :size="11" /> {{ s.name }}
                </button>
              </div>
              <div class="row">
                <input
                  v-model="tagForm.name"
                  class="input input--sm grow"
                  type="text"
                  :placeholder="t('detail.tagName')"
                  maxlength="40"
                  :aria-invalid="!!tagError"
                  @keydown.enter.prevent="addTag"
                />
                <input
                  v-model="tagForm.color"
                  class="input input--color"
                  type="color"
                  aria-label="标签颜色"
                />
                <button type="button" class="btn btn--sm" @click="tagFormOpen = false">
                  {{ t("action.cancel") }}
                </button>
                <button class="btn btn--sm btn--primary" :disabled="tagSaving" @click="addTag">
                  {{ t("action.save") }}
                </button>
              </div>
              <p v-if="tagError" class="field__error" style="margin-top: 8px">
                <Icon name="alert-circle" :size="12" /> {{ tagError }}
              </p>
            </div>
          </div>
        </template>
        <template #actions>
          <button class="btn" @click="addComment">
            <Icon name="note" :size="15" /> {{ t("students.addComment") }}
          </button>
          <button class="btn" @click="addEvent">
            <Icon name="plus" :size="15" /> {{ t("detail.recordEvent") }}
          </button>
          <button class="btn" @click="goSummaries">
            <Icon name="clipboard" :size="15" /> {{ t("summary.title") }}
          </button>
        </template>
      </PageHeader>

      <div class="split">
        <div>

          <!-- 成绩 -->
          <div class="card">
            <div class="card__head">
              <div>
                <h2 class="card__title"><Icon name="chart" :size="16" /> {{ t("detail.scores") }}</h2>
                <p class="card__desc">{{ t("detail.scoresHint") }}</p>
              </div>
              <button class="btn btn--sm" @click="openScoreDialog">
                <Icon name="plus" :size="14" /> {{ t("detail.addScore") }}
              </button>
            </div>

            <div class="card__body">
              <template v-if="student.scores.length">
                <LineChart
                  :labels="scoreTrend.labels"
                  :dates="scoreTrend.dates"
                  :series="scoreTrend.series"
                  :y-max="scoreTrend.yMax"
                  :format-tip="scoreTrend.formatTip"
                  :highlight-index="selectedTrendIndex"
                  @select="selectedTrendIndex = $event"
                />

                <div class="score-exams">
                  <section v-for="g in examScoreGroups" :key="g.exam_id" class="score-exam">
                    <header class="score-exam__head">
                      <h3 class="score-exam__title">{{ g.exam_name }}</h3>
                      <time class="score-exam__date">{{ fmtDate(g.exam_date) }}</time>
                    </header>
                    <div class="score-pill-row">
                      <template v-for="row in g.results" :key="row.result_id">
                        <span v-if="editingId === row.result_id" class="row" style="gap: 6px">
                          <input
                            v-model="editValue"
                            class="input input--sm"
                            type="number"
                            step="0.1"
                            :min="0"
                            :max="row.full_score"
                            style="width: 78px"
                            autofocus
                            :aria-label="`${subject(row.subject)} 分数`"
                            @keydown.enter.prevent="saveEdit(row)"
                            @keydown.esc="cancelEdit"
                          />
                          <button class="btn btn--sm btn--primary" @click="saveEdit(row)">
                            {{ t("action.save") }}
                          </button>
                          <button class="btn btn--sm btn--quiet" @click="cancelEdit">
                            {{ t("action.cancel") }}
                          </button>
                        </span>
                        <button
                          v-else
                          type="button"
                          class="score-pill"
                          :title="scorePillTitle(row)"
                          @click="startEdit(row)"
                        >
                          <span class="chart__dot" :style="{ background: rowColor(row) }" />
                          <span>{{ subject(row.subject) }}</span>
                          <b class="tnum score-pill__value">{{ fmtScore(row) }}</b>
                          <span
                            v-if="row.correction && fmtCorrectionDelta(row.correction)"
                            class="tnum score-pill__correction"
                            :title="row.correction.reason || ''"
                          >{{ t("detail.scoreCorrected", { n: fmtCorrectionDelta(row.correction) }) }}</span>
                          <span
                            v-if="scoreDelta(row.result_id) != null"
                            class="tnum score-pill__delta"
                            :style="deltaStyle(scoreDelta(row.result_id))"
                          >{{ fmtDelta(scoreDelta(row.result_id)) }}</span>
                        </button>
                      </template>
                    </div>
                  </section>
                </div>

                <button
                  v-if="hiddenScoreCount > 0 || showAllScores"
                  class="btn btn--sm btn--ghost btn--block"
                  style="margin-top: 12px"
                  @click="showAllScores = !showAllScores"
                >
                  <Icon :name="showAllScores ? 'chevron-up' : 'chevron-down'" :size="14" />
                  {{ showAllScores ? t("detail.scoresCollapse") : t("detail.scoresExpand", { n: hiddenScoreCount }) }}
                </button>

                <p v-if="editError" class="field__error" style="margin-top: 10px">
                  <Icon name="alert-circle" :size="12" /> {{ editError }}
                </p>
              </template>

              <div v-else class="state state--in-card">
                <span class="state__icon"><Icon name="clipboard" :size="22" /></span>
                <p class="state__title">{{ t("detail.noScores") }}</p>
                <p class="state__desc">{{ t("detail.noScoresDesc") }}</p>
              </div>
            </div>
          </div>

          <!-- 时间线 -->
          <div class="card">
            <div class="card__head">
              <div>
                <h2 class="card__title"><Icon name="note" :size="16" /> {{ t("detail.timeline") }}</h2>
                <p class="card__desc">{{ t("detail.timelineSub") }}</p>
              </div>
            </div>
            <div class="card__body">
              <Timeline :events="timelineWithScores" :student-id="props.id" />
              <p v-if="!timeline.length" class="state__desc" style="padding: 12px 0; text-align: center">
                {{ t("detail.noEvents") }}
              </p>
            </div>
          </div>
        </div>

        <!-- 资料卡（侧栏） -->
        <div class="card">
          <div class="card__head">
            <h2 class="card__title"><Icon name="user" :size="16" /> 学生资料</h2>
            <button v-if="!profileEditing" class="btn btn--sm" @click="startProfileEdit">
              <Icon name="pencil" :size="13" /> {{ t("action.edit") }}
            </button>
          </div>

          <div v-if="!profileEditing" class="card__body profile-panel">
            <section class="profile-section">
              <h3 class="profile-section__title">{{ t("detail.guardian") }}</h3>
              <ul v-if="student.guardians.length" class="profile-list">
                <li v-for="g in student.guardians" :key="g.id" class="profile-list__item">
                  <router-link :to="`/guardians/${g.id}`">{{ g.name }}</router-link>
                  <span v-if="g.relationship" class="muted"> · {{ g.relationship }}</span>
                  <span v-if="g.phone" class="muted tnum"> · {{ g.phone }}</span>
                </li>
              </ul>
              <p v-else class="profile-empty">{{ t("common.none") }}</p>
            </section>

            <section v-if="student.address" class="profile-section">
              <h3 class="profile-section__title">{{ t("new.address") }}</h3>
              <p class="profile-text">{{ student.address }}</p>
            </section>
          </div>

          <!-- 就地编辑资料 -->
          <form v-else class="card__body" @submit.prevent="saveProfileEdit">
            <p class="section-title" style="margin-bottom: 14px">
              {{ t("detail.profileEditTitle") }} · {{ student.name }}
            </p>
            <div class="form-grid">
              <FormField :label="t('new.name')" required>
                <input v-model="profileForm.name" class="input" type="text" maxlength="100" />
              </FormField>
              <FormField :label="t('th.admissionNo')" required>
                <input
                  v-model="profileForm.admission_no"
                  class="input tnum"
                  type="text"
                  maxlength="40"
                />
              </FormField>
              <FormField :label="t('new.gender')" optional>
                <select v-model="profileForm.gender" class="select">
                  <option v-for="g in GENDER_OPTIONS" :key="g.value" :value="g.value">{{ g.label }}</option>
                </select>
              </FormField>
              <FormField :label="t('detail.status')">
                <select v-model="profileForm.status" class="select">
                  <option v-for="s in STATUS_OPTIONS" :key="s.value" :value="s.value">{{ s.label }}</option>
                </select>
              </FormField>
              <FormField :label="t('new.class')" hint="分班时会自动记录加入班级或转班">
                <select v-model="profileForm.class_id" class="select">
                  <option :value="null">{{ t("students.ungrouped") }}</option>
                  <option v-for="c in classes" :key="c.id" :value="c.id">{{ c.name }}</option>
                </select>
              </FormField>
            </div>
            <div class="form-grid">
              <FormField :label="t('new.birthDate')" optional>
                <input v-model="profileForm.birth_date" class="input" type="date" />
              </FormField>
              <FormField :label="t('new.address')" optional>
                <input v-model="profileForm.address" class="input" type="text" />
              </FormField>
            </div>

            <div class="profile-section profile-section--inset">
              <div class="profile-section__head">
                <h3 class="profile-section__title">{{ t("detail.guardian") }}</h3>
                <button type="button" class="btn btn--sm btn--ghost" @click="openGuardianForm">
                  <Icon name="plus" :size="11" /> {{ t("detail.addGuardian") }}
                </button>
              </div>

              <ul v-if="student.guardians.length" class="profile-list">
                <li v-for="g in student.guardians" :key="g.id" class="profile-list__item profile-list__item--row">
                  <span class="grow">
                    <router-link :to="`/guardians/${g.id}`">{{ g.name }}</router-link>
                    <span v-if="g.relationship" class="muted"> · {{ g.relationship }}</span>
                    <span v-if="g.phone" class="muted tnum"> · {{ g.phone }}</span>
                  </span>
                  <button
                    type="button"
                    class="btn btn--sm btn--quiet"
                    :aria-label="`解除关联 ${g.name}`"
                    @click="removeGuardian(g)"
                  >
                    <Icon name="close" :size="12" />
                  </button>
                </li>
              </ul>
              <p v-else class="profile-empty">{{ t("common.none") }}</p>

              <div v-if="guardianFormOpen" class="card card--nested" style="margin-top: var(--sp-3)">
                <div class="card__body card__body--tight">
                  <div class="form-grid">
                    <FormField :label="t('new.guardianName')" required>
                      <input v-model="guardianForm.name" class="input input--sm" type="text" maxlength="100" />
                    </FormField>
                    <FormField :label="t('new.guardianPhone')" optional hint="相同手机号视为同一监护人">
                      <input v-model="guardianForm.phone" class="input input--sm" type="tel" maxlength="40" />
                    </FormField>
                  </div>
                  <div class="form-grid">
                    <FormField label="关系" optional>
                      <input v-model="guardianForm.relationship" class="input input--sm" type="text" maxlength="50" placeholder="如：母亲 / 祖父" />
                    </FormField>
                    <FormField label="地址" optional>
                      <input v-model="guardianForm.address" class="input input--sm" type="text" maxlength="200" />
                    </FormField>
                  </div>
                  <p v-if="guardianError" class="field__error" style="margin: 8px 0">
                    <Icon name="alert-circle" :size="12" /> {{ guardianError }}
                  </p>
                  <div class="row" style="gap: 8px; margin-top: 8px">
                    <button type="button" class="btn btn--sm btn--primary" :disabled="guardianSaving" @click="addGuardian">
                      <span v-if="guardianSaving" class="spinner" />
                      {{ t("action.save") }}
                    </button>
                    <button type="button" class="btn btn--sm btn--ghost" @click="guardianFormOpen = false">
                      {{ t("action.cancel") }}
                    </button>
                  </div>
                </div>
              </div>
            </div>

            <p v-if="profileError" class="field__error" style="margin-bottom: 12px">
              <Icon name="alert-circle" :size="13" /> {{ profileError }}
            </p>

            <div class="form-actions">
              <button type="submit" class="btn btn--primary" :disabled="profileSaving">
                <span v-if="profileSaving" class="spinner" />
                {{ profileSaving ? t("action.saving") : t("action.save") }}
              </button>
              <button type="button" class="btn btn--ghost" @click="cancelProfileEdit">
                {{ t("action.cancel") }}
              </button>
            </div>

            <div class="form-actions form-actions--danger">
              <button
                type="button"
                class="btn btn--danger"
                :disabled="profileSaving"
                @click="removeStudent"
              >
                <Icon name="trash" :size="14" /> {{ t("action.delete") }}
              </button>
            </div>
          </form>
        </div>
      </div>
  </AsyncState>

  <!-- 添加成绩弹窗：选考试 → 按科目填分/勾缺考 -->
  <div
    v-if="scoreDialogOpen"
    class="overlay"
    role="dialog"
    aria-modal="true"
    :aria-label="t('detail.addScore')"
    @click.self="closeScoreDialog"
  >
    <div class="modal" style="width: min(480px, 92vw)">
      <div class="modal__head">
        <div class="grow">
          <h2 class="modal__title">{{ t("detail.addScore") }}</h2>
        </div>
        <button class="icon-btn" aria-label="关闭" @click="closeScoreDialog">
          <Icon name="close" :size="16" />
        </button>
      </div>
      <div class="modal__body">
        <!-- 考试选择用自绘列表：原生 select 弹出层在嵌入式 WebView 里会被
             定位到屏幕底部，无法用样式修正 -->
        <div class="field">
          <span id="exam-picker-label" class="field__label">
            考试 <span class="field__req" aria-hidden="true">*</span>
          </span>
          <div class="exam-picker">
            <button
              type="button"
              class="exam-picker__trigger"
              :class="{ 'is-placeholder': !chosenExam }"
              aria-haspopup="listbox"
              :aria-expanded="examListOpen"
              aria-labelledby="exam-picker-label"
              @click="examListOpen = !examListOpen"
            >
              <span class="grow">{{ chosenExam ? chosenExam.name : "选择考试" }}</span>
              <Icon name="chevron-down" :size="14" style="flex-shrink: 0" />
            </button>
            <div v-if="examListOpen" class="exam-picker__menu" role="listbox">
              <button
                v-for="e in examOptions"
                :key="e.id"
                type="button"
                role="option"
                :aria-selected="e.id === scoreForm.examId"
                class="exam-picker__option"
                :class="{ 'is-active': e.id === scoreForm.examId }"
                @click="pickExam(e)"
              >
                <span class="grow">
                  {{ e.name }} <span class="muted">（{{ e.exam_date }}）</span>
                </span>
                <Icon v-if="e.id === scoreForm.examId" name="check" :size="14" />
              </button>
              <p v-if="!examOptions.length" class="muted" style="margin: 0; padding: 10px 12px">
                还没有可选择的考试
              </p>
            </div>
          </div>
        </div>

        <template v-if="chosenExam">
          <div class="stack" style="gap: 8px; margin-top: 4px">
            <div
              v-for="s in chosenExam.subjects"
              :key="s.id"
              class="row"
              style="gap: 8px; align-items: center"
            >
              <span style="min-width: 4em">{{ subject(s.subject) }}</span>
              <input
                v-model="scoreForm.values[s.subject]"
                class="input input--sm tnum"
                type="number"
                step="0.1"
                min="0"
                :max="s.full_score"
                :disabled="!scoreForm.attended[s.subject]"
                :placeholder="scoreForm.attended[s.subject] ? '' : '缺考'"
                :aria-label="`${subject(s.subject)} 分数`"
                style="width: 90px"
              />
              <span class="muted">/ {{ s.full_score }}</span>
              <label class="check" style="margin: 0">
                <input v-model="scoreForm.attended[s.subject]" type="checkbox" />
                <span>参加考试</span>
              </label>
            </div>
          </div>
          <p class="field__hint" style="margin-top: 8px">
            默认全部参加考试：填了分的科目才会录入；取消勾选记为缺考；已有成绩的科目会被覆盖。
          </p>
        </template>

        <p v-if="scoreDialogError" class="field__error" style="margin-top: 10px">
          <Icon name="alert-circle" :size="12" /> {{ scoreDialogError }}
        </p>
      </div>
      <div class="modal__foot">
        <button type="button" class="btn btn--ghost" @click="closeScoreDialog">
          {{ t("action.cancel") }}
        </button>
        <button
          type="button"
          class="btn btn--primary"
          :disabled="scoreSaving || !chosenExam"
          @click="saveScores"
        >
          <span v-if="scoreSaving" class="spinner" />
          {{ scoreSaving ? t("action.saving") : t("action.save") }}
        </button>
      </div>
    </div>
  </div>
</template>
