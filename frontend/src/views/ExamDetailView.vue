<script setup>
import { ref, computed, onMounted, watch } from "vue"
import { useRouter } from "vue-router"
import api from "../api"
import Icon from "../components/Icon.vue"
import LineChart from "../components/LineChart.vue"
import { subject, subjectColor, t } from "../strings"

const props = defineProps({ id: { type: String, required: true } })
const router = useRouter()

const exam = ref(null)
const averages = ref(null)
const trendData = ref(null)
const loading = ref(true)
const error = ref("")

// edit state
const editing = ref(false)
const editSaving = ref(false)
const editError = ref("")
const editForm = ref({})

onMounted(async () => {
  try {
    const [av, tr, ex] = await Promise.all([
      api.get(`/exams/${props.id}/averages`),
      api.get("/exams/trend"),
      api.get(`/exams/${props.id}`),
    ])
    averages.value = av
    trendData.value = tr
    exam.value = ex
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
})
watch(() => props.id, onMounted)

function startEdit() {
  editing.value = true
  editError.value = ""
  editForm.value = {
    name: exam.value.name,
    exam_date: exam.value.exam_date,
  }
}
function cancelEdit() {
  editing.value = false
  editForm.value = {}
  editError.value = ""
}

async function saveEdit() {
  editError.value = ""
  if (!(editForm.value.name || "").trim()) {
    editError.value = "考试名称不能为空"
    return
  }
  editSaving.value = true
  try {
    const updated = await api.patch(`/exams/${props.id}`, {
      name: editForm.value.name.trim(),
      exam_date: editForm.value.exam_date,
    })
    exam.value = updated
    await onMounted()  // refresh averages (name/date may affect attribution)
    editing.value = false
  } catch (e) {
    editError.value = e.message
  } finally {
    editSaving.value = false
  }
}

async function removeExam() {
  const msg = `确定删除考试「${exam.value.name}」？\n这会连带删除本次考试的所有成绩、题目和作答。此操作不可恢复。`
  if (!window.confirm(msg)) return
  try {
    await api.delete(`/exams/${props.id}`)
    router.replace("/exams")
  } catch (e) {
    alert(`删除失败：${e.message}`)
  }
}

const trendChart = computed(() => {
  if (!trendData.value || !trendData.value.exams.length) return null
  const labels = trendData.value.exams.map((e) => e.name)
  const series = trendData.value.series.map((s) => ({
    key: s.subject,
    label: subject(s.subject),
    color: subjectColor(s.subject),
    values: s.values,
  }))
  const yMax = Math.max(100, ...trendData.value.series.map((s) => s.full_score || 0))
  const highlightIndex = trendData.value.exams.findIndex(
    (e) => averages.value && e.id === averages.value.exam.id
  )
  return { labels, series, yMax, highlightIndex }
})

const subjects = computed(() => (averages.value ? averages.value.school.map((s) => s.subject) : []))

const classRows = computed(() => {
  if (!averages.value) return []
  const byClass = {}
  for (const c of averages.value.classes) {
    byClass[c.class_name] = byClass[c.class_name] || {}
    byClass[c.class_name][c.subject] = c
  }
  return Object.entries(byClass).map(([name, cells]) => ({
    label: name,
    cells,
  }))
})

function fmtDate(d) {
  return new Date(d).toLocaleDateString("zh-CN", { year: "numeric", month: "short", day: "numeric" })
}

function pct(score, full) {
  return full ? Math.round((score / full) * 100) : 0
}
</script>

<template>
  <p v-if="error" class="error-text">{{ error }}</p>
  <p v-else-if="loading" class="empty">{{ t("common.loading") }}</p>

  <template v-else-if="averages && exam">
    <router-link to="/exams" class="back-link"><Icon name="chevron-left" :size="14" /> {{ t("detail.back") }}</router-link>

    <div class="card" style="margin-top: 12px">
      <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 10px">
        <div>
          <h1 style="margin-bottom: 4px">{{ exam.name }} · {{ t("exam.averages") }}</h1>
          <p class="page-sub" style="margin: 0">
            {{ fmtDate(exam.exam_date) }} · {{ t("exam.attributionNote") }}
          </p>
          <div style="margin-top: 10px; display: flex; gap: 8px; flex-wrap: wrap">
            <span v-for="s in exam.subjects" :key="s.id" class="badge">
              {{ subject(s.subject) }} · {{ t("exams.fullScore") }} {{ s.full_score }}
            </span>
          </div>
        </div>
        <div v-if="!editing" style="display: flex; gap: 8px">
          <button class="small" @click="startEdit">{{ t("action.edit") }}</button>
          <button class="small logout-btn" @click="removeExam">{{ t("action.delete") }}</button>
        </div>
      </div>

      <!-- inline edit form -->
      <div v-if="editing" style="margin-top: 16px; padding-top: 16px; border-top: 1px solid var(--border)">
        <h3 style="margin: 0 0 8px">{{ t("action.edit") }} · {{ exam.name }}</h3>
        <div class="form-row">
          <label>考试名称
            <input v-model="editForm.name" type="text" />
          </label>
          <label>日期
            <input v-model="editForm.exam_date" type="date" />
          </label>
        </div>
        <p v-if="editError" class="error-text" style="margin: 6px 0">{{ editError }}</p>
        <div style="display: flex; gap: 8px; margin-top: 8px">
          <button class="primary small" :disabled="editSaving" @click="saveEdit">
            {{ editSaving ? "保存中..." : t("action.save") }}
          </button>
          <button class="small" @click="cancelEdit">{{ t("action.cancel") }}</button>
        </div>
        <p class="page-sub" style="margin-top: 10px; color: var(--muted)">
          提示：科目结构在有成绩录入时不可修改。如需改科目，请先删除本次考试。
        </p>
      </div>
    </div>

    <div class="card">
      <h2>{{ t("exam.trendTitle") }}</h2>
      <p class="page-sub" style="margin-top: 0">{{ t("exam.trendSub") }}</p>
      <LineChart
        v-if="trendChart"
        :labels="trendChart.labels"
        :series="trendChart.series"
        :y-max="trendChart.yMax"
        :highlight-index="trendChart.highlightIndex"
      />
    </div>

    <div class="stat-grid">
      <div v-for="s in averages.school" :key="s.subject" class="stat">
        <div class="stat-label">{{ subject(s.subject) }}</div>
        <div class="stat-value">{{ s.avg }}</div>
        <div class="stat-sub">
          {{ t("exam.outOf") }} {{ s.full_score }} ({{ pct(s.avg, s.full_score) }}%) ·
          {{ t("exam.students", { count: s.count }) }} ·
          {{ t("exam.min") }} {{ s.min }} · {{ t("exam.max") }} {{ s.max }}
        </div>
      </div>
    </div>

    <div class="card">
      <h2>{{ t("exam.perClass") }}</h2>
      <table>
        <thead>
          <tr>
            <th>{{ t("th.class") }}</th>
            <th v-for="subj in subjects" :key="subj">{{ subject(subj) }} {{ t("exam.avg") }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in classRows" :key="row.label">
            <td><span class="badge">{{ row.label }}</span></td>
            <td v-for="subj in subjects" :key="subj">
              <template v-if="row.cells[subj]">
                <strong>{{ row.cells[subj].avg }}</strong>
                <span class="page-sub" style="margin: 0">
                  ({{ t("exam.students", { count: row.cells[subj].count }) }})
                </span>
              </template>
              <template v-else>{{ t("common.none") }}</template>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </template>
</template>
