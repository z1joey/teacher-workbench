<script setup>
import { ref, computed, onMounted, watch } from "vue"
import { useRouter } from "vue-router"
import api from "../api"
import Icon from "../components/Icon.vue"
import LineChart from "../components/LineChart.vue"
import { genderLabel, subject, subjectColor, t } from "../strings"

const props = defineProps({ id: { type: String, required: true } })
const router = useRouter()

const detail = ref(null)
const teachers = ref([])
const loading = ref(true)
const error = ref("")

const editing = ref(false)
const editSaving = ref(false)
const editError = ref("")
const editForm = ref({})

function emptyEditForm(c) {
  return {
    name: c.name || "",
    grade_level: c.grade_level,
    academic_year: c.academic_year,
    homeroom_teacher_id: c.homeroom_teacher_id,
  }
}

onMounted(async () => {
  try {
    const tasks = [api.get(`/classes/${props.id}`)]
    if (!teachers.value.length) tasks.push(api.get("/teachers").catch(() => []))
    const [d, ts] = await Promise.all(tasks)
    detail.value = d
    if (ts) teachers.value = ts
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
  editForm.value = emptyEditForm(detail.value.class)
}
function cancelEdit() {
  editing.value = false
  editForm.value = {}
  editError.value = ""
}

async function saveEdit() {
  editError.value = ""
  if (!(editForm.value.name || "").trim()) {
    editError.value = t("classes.nameRequired")
    return
  }
  editSaving.value = true
  try {
    await api.patch(`/classes/${props.id}`, {
      name: editForm.value.name.trim(),
      grade_level: Number(editForm.value.grade_level),
      academic_year: editForm.value.academic_year.trim(),
      homeroom_teacher_id: editForm.value.homeroom_teacher_id || null,
    })
    editing.value = false
    await onMounted()
  } catch (e) {
    editError.value = e.message
  } finally {
    editSaving.value = false
  }
}

async function removeClass() {
  const msg = `确定删除班级「${detail.value.class.name}」？\n\n` +
    `如果班级内仍有学生（含历史记录），后端会拒绝删除。是否继续？`
  if (!window.confirm(msg)) return
  try {
    await api.delete(`/classes/${props.id}`)
    router.replace("/classes")
  } catch (e) {
    if (e.message?.includes("仍有学生")) {
      alert(e.message)
    } else {
      alert(`删除失败：${e.message}`)
    }
  }
}

const trendChart = computed(() => {
  if (!detail.value || !detail.value.trend.exams.length) return null
  const exams = detail.value.trend.exams
  const series = detail.value.trend.series.map((s) => ({
    key: s.subject,
    label: subject(s.subject),
    color: subjectColor(s.subject),
    values: s.values,
  }))
  const yMax = Math.max(100, ...detail.value.trend.series.map((s) => s.full_score || 0))
  return { labels: exams.map((e) => e.name), series, yMax }
})

const hasScores = computed(() => detail.value && detail.value.averages.length > 0)

function fmtPct(score, full) {
  return full ? Math.round((score / full) * 100) : 0
}
</script>

<template>
  <p v-if="error" class="error-text">{{ error }}</p>
  <p v-else-if="loading" class="empty">{{ t("common.loading") }}</p>

  <template v-else-if="detail">
    <router-link to="/classes" class="back-link"><Icon name="chevron-left" :size="14" /> {{ t("classdetail.back") }}</router-link>

    <div class="card" style="margin-top: 12px">
      <div v-if="!editing" style="display: flex; justify-content: space-between; align-items: flex-start; gap: 10px">
        <div class="profile-head">
          <div class="avatar">{{ detail.class.name.charAt(0) }}</div>
          <div>
            <h1 style="margin-bottom: 0">{{ detail.class.name }}</h1>
            <div class="profile-meta">
              <span class="badge">{{ detail.class.academic_year }}</span>
              <span>{{ t("classes.grade") }} {{ detail.class.grade_level }}</span>
              <span>{{ t("classes.homeroom") }}: {{ detail.class.homeroom_teacher || "—" }}</span>
              <span>{{ t("profile.studentsCount", { n: detail.students.length }) }}</span>
            </div>
          </div>
        </div>
        <div style="display: flex; gap: 8px">
          <button class="small" @click="startEdit">{{ t("action.edit") }}</button>
          <button class="small logout-btn" @click="removeClass">{{ t("action.delete") }}</button>
        </div>
      </div>

      <!-- inline edit form -->
      <div v-else>
        <h2 style="margin: 0 0 10px">{{ t("action.edit") }} · {{ detail.class.name }}</h2>
        <div style="display: flex; gap: 12px; flex-wrap: wrap">
          <div class="field" style="flex: 1; min-width: 160px">
            <label>{{ t("classes.name") }} *
              <input v-model="editForm.name" type="text" />
            </label>
          </div>
          <div class="field" style="flex: 1; min-width: 120px">
            <label>{{ t("classes.grade") }}
              <input v-model="editForm.grade_level" type="number" min="1" max="12" />
            </label>
          </div>
          <div class="field" style="flex: 1; min-width: 160px">
            <label>{{ t("classes.year") }}
              <input v-model="editForm.academic_year" type="text" />
            </label>
          </div>
          <div class="field" style="flex: 1; min-width: 160px">
            <label>{{ t("classes.homeroom") }}
              <select v-model="editForm.homeroom_teacher_id">
                <option :value="null">{{ t("common.none") }}</option>
                <option v-for="t2 in teachers" :key="t2.id" :value="t2.id">{{ t2.name }}</option>
              </select>
            </label>
          </div>
        </div>
        <p v-if="editError" class="error-text" style="margin: 6px 0">{{ editError }}</p>
        <div style="display: flex; gap: 8px; margin-top: 6px">
          <button class="primary small" :disabled="editSaving" @click="saveEdit">
            {{ editSaving ? "保存中..." : t("action.save") }}
          </button>
          <button class="small" @click="cancelEdit">{{ t("action.cancel") }}</button>
        </div>
      </div>
    </div>

    <div class="two-col">
      <div>
        <div class="card">
          <h2>{{ t("classdetail.trendTitle") }}</h2>
          <p class="page-sub" style="margin-top: 0">{{ t("classdetail.trendSub") }}</p>
          <p v-if="!trendChart || !trendChart.series.length" class="empty">{{ t("classdetail.noScores") }}</p>
          <LineChart
            v-else
            :labels="trendChart.labels"
            :series="trendChart.series"
            :y-max="trendChart.yMax"
          />
        </div>

        <div class="card">
          <h2>{{ t("classdetail.roster") }}</h2>
          <div v-if="detail.students.length" class="student-chips">
            <router-link
              v-for="s in detail.students"
              :key="s.id"
              :to="`/students/${s.id}`"
              class="student-chip"
              :title="s.admission_no"
            >
              {{ s.name }} <span class="weakness-sub">{{ genderLabel(s.gender) }}</span>
            </router-link>
          </div>
          <p v-else class="empty">{{ t("classes.noStudents") }}</p>
        </div>
      </div>

      <div class="card">
        <h2>{{ t("classdetail.averages") }}</h2>
        <p v-if="!hasScores" class="empty">{{ t("classdetail.noScores") }}</p>
        <div v-for="a in detail.averages" :key="a.subject" class="stat" style="box-shadow: none; border: none; padding: 6px 0">
          <div class="stat-label">{{ subject(a.subject) }}</div>
          <div class="stat-value">{{ a.avg ?? "—" }}</div>
          <div class="stat-sub">
            {{ t("exam.outOf") }} {{ a.full_score }} ({{ fmtPct(a.avg, a.full_score) }}%) ·
            {{ t("exam.exams", { count: a.count }) }}
          </div>
        </div>
      </div>
    </div>
  </template>
</template>
