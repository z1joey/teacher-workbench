<script setup>
import { ref, computed, onMounted, watch } from "vue"
import { useRouter } from "vue-router"
import api from "../api"
import Icon from "../components/Icon.vue"
import LineChart from "../components/LineChart.vue"
import { dateLocale, genderLabel, statusLabel, subject, subjectColor, t } from "../strings"
import Timeline from "../components/Timeline.vue"

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
const SCORE_ROWS_VISIBLE = 6
const SUBJECT_ORDER = ["chinese", "math", "english", "physics", "chemistry"]
const showAllScores = ref(false)
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

function subjectInitial(sub) {
  return subject(sub).charAt(0)
}

// profile edit
const profileEditing = ref(false)
const profileSaving = ref(false)
const profileError = ref("")
const profileForm = ref({})

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
    if (res.length > 2) classes.value = res[2]
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}
onMounted(load)
watch(() => props.id, load)

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
  if (!(profileForm.value.name || "").trim()) {
    profileError.value = "姓名不能为空"
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
  } catch (e) {
    profileError.value = e.message
  } finally {
    profileSaving.value = false
  }
}

async function removeStudent() {
  const msg = `确定删除学生「${student.value.name}」？\n\n如果该学生已有历史成绩/跟进记录，将自动停用账号（数据保留）。否则会被彻底删除。`
  if (!window.confirm(msg)) return
  try {
    const res = await api.delete(`/students/${props.id}`)
    const tip = res.action === "deactivated"
      ? `学生「${student.value.name}」已停用账号。`
      : `学生「${student.value.name}」已删除。`
    alert(tip)
    router.replace("/students")
  } catch (e) {
    alert(`删除失败：${e.message}`)
  }
}

function startEdit(row) {
  editingId.value = row.result_id
  editValue.value = row.score
  editError.value = ""
}
function cancelEdit() {
  editingId.value = null
}

async function saveEdit(row) {
  editError.value = ""
  try {
    await api.patch(`/results/${row.result_id}`, {
      score: Number(editValue.value),
      reason: t("detail.editReason"),
    })
    editingId.value = null
    await load()
  } catch (e) {
    editError.value = e.message
  }
}

function onEventClick(e) {
  // Only manual events (non-system, with actor_teacher_id) are editable
  if (e.is_system) return
  router.push(`/students/${props.id}/events/${e.id}`)
}
function addEvent() {
  router.push(`/students/${props.id}/events/new`)
}

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

function fmtDate(d) {
  return d
    ? new Date(d).toLocaleDateString(dateLocale(), { year: "numeric", month: "short", day: "numeric" })
    : "—"
}
function fmtDateTime(ts) {
  return new Date(ts).toLocaleString(dateLocale(), {
    year: "numeric", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
  })
}
function scoreClass(row) {
  // color by percentage of full score, not absolute value — a 90/150 exam
  // warns just like a 54/100 one
  if (row.status !== "entered" || row.score == null) return "badge muted"
  const ratio = row.score / row.full_score
  return ratio < 0.6 ? "badge warn" : "badge ok"
}
</script>

<template>
  <p v-if="error" class="error-text">{{ error }}</p>
  <p v-else-if="loading" class="empty">{{ t("common.loading") }}</p>

  <template v-else-if="student">
    <router-link to="/students" class="back-link"><Icon name="chevron-left" :size="14" /> {{ t("detail.back") }}</router-link>

    <div class="card" style="margin-top: 12px">
      <div v-if="!profileEditing" style="display: flex; justify-content: space-between; align-items: flex-start; gap: 10px">
        <div class="profile-head">
          <div class="avatar">{{ student.name.charAt(0) }}</div>
          <div>
            <h1 style="margin-bottom: 0">{{ student.name }}</h1>
            <div class="profile-meta">
              <span class="badge">{{ student.class ? student.class.name : "—" }}</span>
              <span>{{ student.admission_no }}</span>
              <span>{{ genderLabel(student.gender) }}</span>
              <span>{{ t("detail.born") }} {{ fmtDate(student.birth_date) }}</span>
              <span class="badge" :class="student.status === 'active' ? 'ok' : 'muted'">{{ statusLabel(student.status) }}</span>
            </div>
            <div class="profile-meta">
              <span>{{ t("detail.guardian") }}: {{ student.guardian_name || "—" }} · {{ student.guardian_phone || "—" }}</span>
              <span>{{ student.address || "" }}</span>
            </div>
          </div>
        </div>
        <div style="display: flex; gap: 8px">
          <button class="small" @click="startProfileEdit">{{ t("action.edit") }}</button>
          <button class="small logout-btn" @click="removeStudent">{{ t("action.delete") }}</button>
        </div>
      </div>

      <!-- inline profile edit -->
      <div v-else>
        <h2 style="margin: 0 0 10px">{{ t("action.edit") }} · {{ student.name }}</h2>
        <div class="form-row">
          <label>姓名
            <input v-model="profileForm.name" type="text" />
          </label>
          <label>性别
            <select v-model="profileForm.gender">
              <option value="">（未填写）</option>
              <option value="male">男</option>
              <option value="female">女</option>
              <option value="other">其他</option>
            </select>
          </label>
          <label>状态
            <select v-model="profileForm.status">
              <option value="active">活跃</option>
              <option value="inactive">停用</option>
            </select>
          </label>
          <label>班级
            <select v-model="profileForm.class_id">
              <option v-for="c in classes" :key="c.id" :value="c.id">{{ c.name }}</option>
            </select>
          </label>
        </div>
        <div class="form-row">
          <label>监护人姓名
            <input v-model="profileForm.guardian_name" type="text" placeholder="家长姓名" />
          </label>
          <label>监护人电话
            <input v-model="profileForm.guardian_phone" type="tel" placeholder="联系方式" />
          </label>
          <label>出生日期
            <input v-model="profileForm.birth_date" type="date" />
          </label>
          <label>住址
            <input v-model="profileForm.address" type="text" placeholder="住址" />
          </label>
        </div>
        <p v-if="profileError" class="error-text" style="margin: 6px 0">{{ profileError }}</p>
        <div style="display: flex; gap: 8px; margin-top: 6px">
          <button class="primary small" :disabled="profileSaving" @click="saveProfileEdit">
            {{ profileSaving ? "保存中..." : t("action.save") }}
          </button>
          <button class="small" @click="cancelProfileEdit">{{ t("action.cancel") }}</button>
        </div>
      </div>
    </div>

    <!-- scores -->
    <div class="card">
      <h2>{{ t("detail.scores") }}</h2>
      <p v-if="!student.scores.length" class="empty">{{ t("empty.scores") }}</p>
      <template v-else>
        <p class="page-sub" style="margin-top: 0">{{ t("detail.trendSub") }}</p>
        <LineChart
          :labels="scoreTrend.labels"
          :series="scoreTrend.series"
          :y-max="scoreTrend.yMax"
        />
      </template>
      <table v-if="student.scores.length" style="margin-top: 12px">
        <thead>
          <tr>
            <th>{{ t("th.exam") }}</th>
            <th>{{ t("th.score") }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="g in examScoreGroups" :key="g.exam_id">
            <td>{{ g.exam_name }}
              <span class="page-sub" style="margin:0">({{ fmtDate(g.exam_date) }})</span>
            </td>
            <td>
              <span v-for="row in g.results" :key="row.result_id" class="score-seg">
                <template v-if="editingId === row.result_id">
                  <input v-model="editValue" type="number" step="0.1" style="width: 70px" />
                  <button class="small primary" @click="saveEdit(row)">{{ t("action.save") }}</button>
                  <button class="small" @click="cancelEdit">{{ t("action.cancel") }}</button>
                </template>
                <button
                  v-else
                  class="score-pill"
                  :title="`${subject(row.subject)} ${row.score}/${row.full_score} · 点击修改`"
                  @click="startEdit(row)"
                >
                  <b class="score-pill-subject">{{ subjectInitial(row.subject) }}</b>
                  <span :class="scoreClass(row)">{{ row.score }}</span>
                </button>
              </span>
            </td>
          </tr>
        </tbody>
      </table>
      <button
        v-if="hiddenScoreCount > 0 || showAllScores"
        class="small scores-toggle"
        @click="showAllScores = !showAllScores"
      >
        <Icon :name="showAllScores ? 'chevron-up' : 'chevron-down'" :size="14" />
        {{ showAllScores ? t("detail.scoresCollapse") : t("detail.scoresExpand", { n: hiddenScoreCount }) }}
      </button>
      <p v-if="editError" class="error-text">{{ editError }}</p>
    </div>

    <!-- timeline + add button -->
    <div class="card">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px">
        <h2 style="margin: 0">{{ t("detail.timeline") }}</h2>
        <button class="small primary" @click="addEvent">+</button>
      </div>
      <Timeline :events="timeline" :clickable="true" @select="onEventClick" />
    </div>
  </template>
</template>
