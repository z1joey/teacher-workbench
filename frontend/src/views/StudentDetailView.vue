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
  studentStatusTone,
  subject,
  subjectColor,
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

// the score table collapses to the most recent entries once exams pile up
const SCORE_ROWS_VISIBLE = 9 // one full exam (all subjects)
const SUBJECT_ORDER = ["chinese", "math", "english", "politics", "history", "geography", "biology", "physics", "chemistry"]
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

// ------------------------------------------------------------------ 成绩

const hiddenScoreCount = computed(() =>
  Math.max(0, (student.value?.scores.length ?? 0) - SCORE_ROWS_VISIBLE)
)
const visibleScores = computed(() => {
  if (!student.value || showAllScores.value || hiddenScoreCount.value === 0) {
    return student.value?.scores ?? []
  }
  return student.value.scores.slice(-SCORE_ROWS_VISIBLE) // newest exams
})

// one row per exam: subjects in 语/数/英 order, scores aligned to that order
const examScoreGroups = computed(() => {
  const groups = []
  const byExam = new Map()
  for (const row of visibleScores.value) {
    let g = byExam.get(row.exam_id)
    if (!g) {
      g = { exam_id: row.exam_id, exam_name: row.exam_name, exam_date: row.exam_date, results: [] }
      byExam.set(row.exam_id, g)
      groups.push(g)
    }
    g.results.push(row)
  }
  for (const g of groups) {
    g.results.sort((a, b) => {
      const ia = SUBJECT_ORDER.indexOf(a.subject)
      const ib = SUBJECT_ORDER.indexOf(b.subject)
      return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib)
    })
  }
  return groups
})

// multi-subject score trend: one line per subject across exams (chronological)
const scoreTrend = computed(() => {
  if (!student.value || !student.value.scores.length) return null
  const byExam = new Map()
  for (const row of student.value.scores) {
    const key = `${row.exam_date}|${row.exam_id}`
    if (!byExam.has(key)) {
      byExam.set(key, { label: row.exam_name, date: row.exam_date, perSubject: {} })
    }
    byExam.get(key).perSubject[row.subject] = row.score
  }
  const exams = [...byExam.values()].sort((a, b) => a.date.localeCompare(b.date))
  const subjects = [...new Set(student.value.scores.map((s) => s.subject))]
  const series = subjects.map((sub) => ({
    key: sub,
    label: subject(sub),
    color: subjectColor(sub),
    values: exams.map((e) => e.perSubject[sub] ?? null),
  }))
  const yMax = Math.max(100, ...student.value.scores.map((s) => s.full_score || 0))
  return { labels: exams.map((e) => e.label), series, yMax }
})

function subjectInitial(sub) {
  return subject(sub).charAt(0)
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

function scoreClass(row) {
  // color by percentage of full score, not absolute value — a 90/150 exam
  // warns just like a 54/100 one
  if (row.status !== "entered" || row.score == null) return "pill pill--muted"
  const ratio = row.score / row.full_score
  return ratio < 0.6 ? "pill pill--warn" : "pill pill--ok"
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

function startProfileEdit() {
  profileEditing.value = true
  profileError.value = ""
  profileForm.value = {
    name: student.value.name,
    gender: student.value.gender || "",
    guardian_name: student.value.guardian_name || "",
    guardian_phone: student.value.guardian_phone || "",
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
}

async function saveProfileEdit() {
  profileError.value = ""
  if (!profileForm.value.name.trim()) {
    profileError.value = t("detail.nameRequired")
    return
  }
  profileSaving.value = true
  try {
    await api.patch(`/students/${props.id}`, {
      name: profileForm.value.name.trim(),
      gender: profileForm.value.gender || null,
      guardian_name: profileForm.value.guardian_name.trim() || null,
      guardian_phone: profileForm.value.guardian_phone.trim(),
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

function fmtDate(d) {
  return d
    ? new Date(d).toLocaleDateString(dateLocale(), { year: "numeric", month: "short", day: "numeric" })
    : "—"
}
</script>

<template>
  <AsyncState :loading="loading" :error="error" :rows="5" @retry="load">
    <template v-if="student">
      <PageHeader
        :title="student.name"
        :subtitle="`${student.admission_no} · ${student.class ? student.class.name : t('students.ungrouped')}`"
        :meta="[
          { label: t('th.status'), value: studentStatusLabel(student.status) },
          { label: t('new.gender'), value: genderLabel(student.gender) },
          { label: t('detail.born'), value: fmtDate(student.birth_date) },
        ]"
      >
        <template #actions>
          <button class="btn" @click="addEvent">
            <Icon name="plus" :size="15" /> {{ t("detail.recordEvent") }}
          </button>
          <button class="btn btn--danger" @click="removeStudent">
            <Icon name="trash" :size="15" /> {{ t("action.delete") }}
          </button>
        </template>
      </PageHeader>

      <div class="split">
        <div>
          <!-- 资料卡 -->
          <div class="card">
            <div class="card__head">
              <h2 class="card__title"><Icon name="user" :size="16" /> 学生资料</h2>
              <button v-if="!profileEditing" class="btn btn--sm" @click="startProfileEdit">
                <Icon name="pencil" :size="13" /> {{ t("action.edit") }}
              </button>
            </div>

            <div v-if="!profileEditing" class="card__body">
              <div class="row" style="gap: 14px; align-items: flex-start">
                <span class="avatar avatar--lg">{{ student.name.charAt(0) }}</span>
                <div class="grow">
                  <div class="row-wrap">
                    <span class="pill" :class="`pill--${studentStatusTone(student.status)}`">
                      {{ studentStatusLabel(student.status) }}
                    </span>
                    <span v-if="student.class" class="pill pill--outline">{{ student.class.name }}</span>
                  </div>
                  <p class="stat__sub" style="margin-top: 8px">
                    {{ t("detail.guardian") }}：{{ student.guardian_name || t("common.none") }}
                    · {{ student.guardian_phone || t("common.none") }}
                  </p>
                  <p v-if="student.address" class="stat__sub">{{ student.address }}</p>
                </div>
              </div>

              <!-- 标签 -->
              <div class="row-wrap" style="margin-top: 16px">
                <span
                  v-for="tag in student.tags"
                  :key="tag.id"
                  class="tag"
                  :style="{ background: tag.color }"
                >
                  {{ tag.name }}
                  <button class="tag__x" :aria-label="`移除标签 ${tag.name}`" @click="removeTag(tag)">
                    <Icon name="close" :size="10" />
                  </button>
                </span>
                <button class="btn btn--sm btn--ghost" @click="toggleTagForm">
                  <Icon name="tag" :size="13" /> {{ t("detail.addTag") }}
                </button>
              </div>

              <div v-if="tagFormOpen" class="card card--nested" style="margin-top: 12px">
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
                    <button class="btn btn--sm btn--primary" :disabled="tagSaving" @click="addTag">
                      {{ t("action.save") }}
                    </button>
                  </div>
                  <p v-if="tagError" class="field__error" style="margin-top: 8px">
                    <Icon name="alert-circle" :size="12" /> {{ tagError }}
                  </p>
                </div>
              </div>
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
                <FormField :label="t('new.class')" hint="换班会自动记录一条转班事件">
                  <select v-model="profileForm.class_id" class="select">
                    <option :value="null">{{ t("students.ungrouped") }}</option>
                    <option v-for="c in classes" :key="c.id" :value="c.id">{{ c.name }}</option>
                  </select>
                </FormField>
              </div>
              <div class="form-grid">
                <FormField :label="t('new.guardianName')" optional>
                  <input v-model="profileForm.guardian_name" class="input" type="text" />
                </FormField>
                <FormField :label="t('new.guardianPhone')" optional>
                  <input v-model="profileForm.guardian_phone" class="input" type="tel" maxlength="40" />
                </FormField>
                <FormField :label="t('new.birthDate')" optional>
                  <input v-model="profileForm.birth_date" class="input" type="date" />
                </FormField>
                <FormField :label="t('new.address')" optional>
                  <input v-model="profileForm.address" class="input" type="text" />
                </FormField>
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
            </form>
          </div>

          <!-- 成绩 -->
          <div class="card">
            <div class="card__head">
              <div>
                <h2 class="card__title"><Icon name="chart" :size="16" /> {{ t("detail.scores") }}</h2>
                <p class="card__desc">{{ t("detail.scoresHint") }}</p>
              </div>
            </div>

            <div class="card__body">
              <template v-if="student.scores.length">
                <LineChart
                  :labels="scoreTrend.labels"
                  :series="scoreTrend.series"
                  :y-max="scoreTrend.yMax"
                />

                <div class="table-wrap" style="margin-top: 16px">
                  <table class="table table--stack">
                    <thead>
                      <tr>
                        <th>{{ t("th.exam") }}</th>
                        <th>{{ t("th.score") }}</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="g in examScoreGroups" :key="g.exam_id">
                        <td data-label="考试">
                          <div>{{ g.exam_name }}</div>
                          <div class="stat__sub">{{ fmtDate(g.exam_date) }}</div>
                        </td>
                        <td data-label="分数">
                          <span class="row-wrap">
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
                                class="score-pill"
                                :title="`${subject(row.subject)} ${row.score}/${row.full_score} · 点击更正`"
                                @click="startEdit(row)"
                              >
                                <b>{{ subjectInitial(row.subject) }}</b>
                                <span :class="scoreClass(row)">{{ row.score ?? t("common.none") }}</span>
                              </button>
                            </template>
                          </span>
                        </td>
                      </tr>
                    </tbody>
                  </table>
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
              <button class="btn btn--sm btn--primary" @click="addEvent">
                <Icon name="plus" :size="13" /> {{ t("detail.recordEvent") }}
              </button>
            </div>
            <div class="card__body">
              <Timeline :events="timeline" :student-id="props.id" />
              <p v-if="!timeline.length" class="state__desc" style="padding: 12px 0; text-align: center">
                {{ t("detail.noEvents") }}
              </p>
            </div>
          </div>
        </div>
      </div>
    </template>
  </AsyncState>
</template>
