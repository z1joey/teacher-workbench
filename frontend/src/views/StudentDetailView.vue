<script setup>
import { ref, computed, onMounted, watch } from "vue"
import api from "../api"
import Icon from "../components/Icon.vue"
import LineChart from "../components/LineChart.vue"
import { dateLocale, genderLabel, qtype, statusLabel, subject, subjectColor, t } from "../strings"
import Timeline from "../components/Timeline.vue"

const props = defineProps({ id: { type: String, required: true } })

const student = ref(null)
const timeline = ref([])
const weaknesses = ref([])
const failed = ref([])
const loading = ref(true)
const error = ref("")

// inline score editing
const editingId = ref(null)
const editValue = ref(null)
const editError = ref("")

// home visit form — the visiting teacher is the logged-in user
const showVisitForm = ref(false)
const visitSaving = ref(false)
const visitError = ref("")
const visitForm = ref(emptyVisitForm())

function emptyVisitForm() {
  return { purpose: "", summary: "", follow_up_needed: false, follow_up_note: "" }
}

async function load() {
  loading.value = true
  error.value = ""
  try {
    const [s, tl, w, f] = await Promise.all([
      api.get(`/students/${props.id}`),
      api.get(`/students/${props.id}/timeline`),
      api.get(`/students/${props.id}/weaknesses`),
      api.get(`/students/${props.id}/failed-questions`),
    ])
    student.value = s
    timeline.value = tl
    weaknesses.value = w
    failed.value = f
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}
onMounted(load)
watch(() => props.id, load)

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

async function submitVisit() {
  if (!visitForm.value.summary.trim()) {
    visitError.value = t("visit.summaryRequired")
    return
  }
  visitSaving.value = true
  visitError.value = ""
  try {
    await api.post(`/students/${props.id}/home-visits`, visitForm.value)
    visitForm.value = emptyVisitForm()
    showVisitForm.value = false
    await load()
  } catch (e) {
    visitError.value = e.message
  } finally {
    visitSaving.value = false
  }
}

const failedGrouped = computed(() => {
  const groups = []
  const index = new Map()
  for (const f of failed.value) {
    const key = `${f.exam_name}|${f.subject}`
    if (!index.has(key)) {
      const group = {
        label: `${f.exam_name} · ${subject(f.subject)}`,
        items: [],
      }
      index.set(key, group)
      groups.push(group)
    }
    index.get(key).items.push(f)
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
function scoreLabel(row) {
  return row.status === "entered" && row.score != null
    ? `${row.score} / ${row.full_score}`
    : statusLabel(row.status)
}
function scoreClass(row) {
  if (row.status !== "entered" || row.score == null) return "badge muted"
  return row.score / row.full_score < 0.6 ? "badge warn" : "badge ok"
}
</script>

<template>
  <p v-if="error" class="error-text">{{ error }}</p>
  <p v-else-if="loading" class="empty">{{ t("common.loading") }}</p>

  <template v-else-if="student">
    <router-link to="/students" class="back-link"><Icon name="chevron-left" :size="14" /> {{ t("detail.back") }}</router-link>

    <div class="card" style="margin-top: 12px">
      <div class="profile-head">
        <div class="avatar">{{ student.name.charAt(0) }}</div>
        <div>
          <h1 style="margin-bottom: 0">{{ student.name }}</h1>
          <div class="profile-meta">
            <span class="badge">{{ student.class ? student.class.name : "—" }}</span>
            <span>{{ student.admission_no }}</span>
            <span>{{ genderLabel(student.gender) }}</span>
            <span>{{ t("detail.born") }} {{ fmtDate(student.birth_date) }}</span>
            <span class="badge ok">{{ statusLabel(student.status) }}</span>
          </div>
          <div class="profile-meta">
            <span>{{ t("detail.guardian") }}: {{ student.guardian_name || "—" }} · {{ student.guardian_phone || "—" }}</span>
            <span>{{ student.address || "" }}</span>
          </div>
        </div>
      </div>
    </div>

    <div class="two-col">
      <div>
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
                <th>{{ t("th.subject") }}</th>
                <th>{{ t("th.score") }}</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in student.scores" :key="row.result_id">
                <td>{{ row.exam_name }}
                  <span class="page-sub" style="margin:0">({{ fmtDate(row.exam_date) }})</span>
                </td>
                <td><span class="badge">{{ subject(row.subject) }}</span></td>
                <td>
                  <span :class="scoreClass(row)">{{ scoreLabel(row) }}</span>
                </td>
                <td style="text-align: right">
                  <template v-if="editingId === row.result_id">
                    <input v-model="editValue" type="number" step="0.1" style="width: 90px; margin-right: 6px" />
                    <button class="small primary" @click="saveEdit(row)">{{ t("action.save") }}</button>
                    <button class="small" @click="cancelEdit">{{ t("action.cancel") }}</button>
                  </template>
                  <button v-else class="small" @click="startEdit(row)">{{ t("action.edit") }}</button>
                </td>
              </tr>
            </tbody>
          </table>
          <p v-if="editError" class="error-text">{{ editError }}</p>
        </div>

        <!-- weaknesses -->
        <div class="card">
          <h2>{{ t("detail.weaknesses") }}</h2>
          <p v-if="!weaknesses.length" class="empty">{{ t("empty.weaknesses") }}</p>
          <div v-for="w in weaknesses" :key="w.id" class="weakness">
            <div class="weakness-info">
              <div class="weakness-topic">{{ w.knowledge_point }}</div>
              <div class="weakness-sub">
                {{ subject(w.subject) }} ·
                {{ t("detail.weaknessFailed", { failed: w.evidence_count, total: w.attempts }) }} ·
                {{ fmtDate(w.first_seen) }} → {{ fmtDate(w.last_seen) }}
              </div>
            </div>
            <div class="severity-bar"><div :style="{ width: Math.round(w.severity * 100) + '%' }"></div></div>
            <span :class="w.status === 'open' ? 'badge warn' : 'badge ok'">{{ statusLabel(w.status) }}</span>
          </div>
        </div>

        <!-- failed question drill-down -->
        <div class="card">
          <h2>{{ t("detail.drilldown") }}</h2>
          <p v-if="!failed.length" class="empty">{{ t("empty.drilldown") }}</p>
          <div v-for="g in failedGrouped" :key="g.label" style="margin-bottom: 14px">
            <div style="font-weight: 600; margin-bottom: 4px">{{ g.label }}</div>
            <table>
              <thead>
                <tr>
                  <th>{{ t("th.qno") }}</th>
                  <th>{{ t("th.topic") }}</th>
                  <th>{{ t("th.qtype") }}</th>
                  <th>{{ t("th.earned") }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(f, i) in g.items" :key="i">
                  <td>{{ f.question_no }}</td>
                  <td>{{ f.topic || t("common.none") }}</td>
                  <td class="page-sub" style="margin:0">{{ qtype(f.question_type) }}</td>
                  <td><span class="badge warn">{{ f.earned }} / {{ f.max_score }}</span></td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- home visits -->
        <div class="card">
          <div style="display: flex; justify-content: space-between; align-items: center">
            <h2 style="margin: 0">{{ t("detail.visits") }}</h2>
            <button class="small primary" @click="showVisitForm = !showVisitForm">
              {{ showVisitForm ? t("visit.close") : t("visit.record") }}
            </button>
          </div>

          <form v-if="showVisitForm" style="margin-top: 14px" @submit.prevent="submitVisit">
      <div class="field">
              <label>{{ t("visit.purpose") }}</label>
              <input v-model="visitForm.purpose" type="text" />
            </div>
            <div class="field">
              <label>{{ t("visit.summary") }} *</label>
              <textarea v-model="visitForm.summary" rows="3"></textarea>
            </div>
            <div class="field checkbox-row">
              <input id="fu" v-model="visitForm.follow_up_needed" type="checkbox" />
              <label for="fu">{{ t("visit.followUp") }}</label>
            </div>
            <div v-if="visitForm.follow_up_needed" class="field">
              <label>{{ t("visit.followUpNote") }}</label>
              <input v-model="visitForm.follow_up_note" type="text" />
            </div>
            <p v-if="visitError" class="error-text">{{ visitError }}</p>
            <button type="submit" class="primary" :disabled="visitSaving">
              {{ visitSaving ? t("visit.saving") : t("visit.save") }}
            </button>
          </form>

          <p v-if="!student.home_visits.length" class="empty" style="margin-top: 14px">
            {{ t("empty.visits") }}
          </p>
          <div
            v-for="v in student.home_visits"
            :key="v.id"
            style="padding: 10px 0; border-bottom: 1px solid var(--border)"
          >
            <div style="font-weight: 600">{{ v.purpose || t("detail.visits") }}</div>
            <div class="weakness-sub" style="margin: 2px 0 6px">{{ fmtDateTime(v.visited_at) }}</div>
            <div>{{ v.summary }}</div>
            <div v-if="v.follow_up_needed" style="margin-top: 6px">
              <span class="badge warn">{{ t("visit.followUp") }}: {{ v.follow_up_note || "…" }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- timeline -->
      <div class="card">
        <h2>{{ t("detail.timeline") }}</h2>
        <Timeline :events="timeline" />
      </div>
    </div>
  </template>
</template>
