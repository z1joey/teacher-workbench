<script setup>
// 考试详情：全校趋势 + 各科统计 + 各班对比。虚线标出当前这次考试，
// 让用户一眼看出自己看的是哪一场（状态可见）。
import { computed, onMounted, ref, watch } from "vue"
import { useRouter } from "vue-router"
import api from "../api"
import Icon from "../components/Icon.vue"
import PageHeader from "../components/PageHeader.vue"
import AsyncState from "../components/AsyncState.vue"
import FormField from "../components/FormField.vue"
import LineChart from "../components/LineChart.vue"
import { ask } from "../confirm"
import { notify, runUndoable } from "../feedback"
import { setPageTitle } from "../title"
import { friendlyError, formatDateRange, subject, subjectColor, t } from "../strings"

const props = defineProps({ id: { type: String, required: true } })
const router = useRouter()

const exam = ref(null)
const averages = ref(null)
const trendData = ref(null)
const loading = ref(true)
const error = ref("")

const editing = ref(false)
const editSaving = ref(false)
const editError = ref("")
const editForm = ref({})

async function load() {
  loading.value = true
  error.value = ""
  try {
    const [av, tr, ex] = await Promise.all([
      api.get(`/exams/${props.id}/averages`),
      api.get("/exams/trend"),
      api.get(`/exams/${props.id}`),
    ])
    averages.value = av
    trendData.value = tr
    exam.value = ex
    setPageTitle(ex.name)
  } catch (e) {
    error.value = friendlyError(e)
  } finally {
    loading.value = false
  }
}
onMounted(load)
watch(() => props.id, load)

function startEdit() {
  editing.value = true
  editError.value = ""
  editForm.value = {
    name: exam.value.name,
    exam_date: exam.value.exam_date,
    end_date: exam.value.end_date || "",
  }
}
function cancelEdit() {
  editing.value = false
  editForm.value = {}
  editError.value = ""
}

async function saveEdit() {
  editError.value = ""
  if (!editForm.value.name.trim()) {
    editError.value = t("examnew.nameRequired")
    return
  }
  if (editForm.value.end_date && editForm.value.end_date < editForm.value.exam_date) {
    editError.value = t("examnew.endDateInvalid")
    return
  }
  editSaving.value = true
  try {
    const updated = await api.patch(`/exams/${props.id}`, {
      name: editForm.value.name.trim(),
      exam_date: editForm.value.exam_date,
      end_date: editForm.value.end_date || null,
    })
    exam.value = updated
    editing.value = false
    notify({ tone: "ok", title: t("common.saved"), timeout: 2400 })
    await load()
  } catch (e) {
    editError.value = friendlyError(e)
  } finally {
    editSaving.value = false
  }
}

async function removeExam() {
  const name = exam.value.name
  const ok = await ask({
    title: `删除考试「${name}」？`,
    consequences: [
      t("exam.deleteConfirm"),
      "已经录入的分数会一起消失，且无法单独恢复。",
      "6 秒内可以在提示条上点「撤销」。",
    ],
    confirmLabel: t("action.delete"),
  })
  if (!ok) return

  runUndoable({
    title: `已删除考试「${name}」`,
    run: () => api.delete(`/exams/${props.id}`),
    onDone: () => router.replace("/exams"),
  })
}

const trendChart = computed(() => {
  if (!trendData.value || !trendData.value.exams.length) return null
  const highlightIndex = trendData.value.exams.findIndex(
    (e) => averages.value && e.id === averages.value.exam.id
  )
  return {
    labels: trendData.value.exams.map((e) => e.name),
    dates: trendData.value.exams.map((e) => e.exam_date),
    series: trendData.value.series.map((s) => ({
      key: s.subject,
      label: subject(s.subject),
      color: subjectColor(s.subject, exam.value?.subjects.find((x) => x.subject === s.subject)?.color),
      values: s.values,
    })),
    yMax: Math.max(100, ...trendData.value.series.map((s) => s.full_score || 0)),
    highlightIndex,
  }
})

const subjects = computed(() => (averages.value ? averages.value.school.map((s) => s.subject) : []))

const classRows = computed(() => {
  if (!averages.value) return []
  const byClass = {}
  for (const c of averages.value.classes) {
    byClass[c.class_name] = byClass[c.class_name] || {}
    byClass[c.class_name][c.subject] = c
  }
  return Object.entries(byClass).map(([name, cells]) => ({ label: name, cells }))
})

function pct(score, full) {
  return full ? Math.round((score / full) * 100) : 0
}
</script>

<template>
  <AsyncState :loading="loading" :error="error" :rows="4" @retry="load">
    <template v-if="averages && exam">
      <PageHeader
        :title="exam.name"
        :subtitle="`${formatDateRange(exam.exam_date, exam.end_date)} · ${t('exam.attributionNote')}`"
      >
        <template #actions>
          <button class="btn" @click="startEdit">
            <Icon name="pencil" :size="15" /> {{ t("action.edit") }}
          </button>
          <button class="btn btn--danger" @click="removeExam">
            <Icon name="trash" :size="15" /> {{ t("action.delete") }}
          </button>
        </template>
      </PageHeader>

      <div class="row-wrap" style="margin-bottom: 20px">
        <span
          v-for="s in exam.subjects"
          :key="s.id"
          class="pill pill--outline"
        >
          <span class="subject-dot" :style="{ background: subjectColor(s.subject, s.color) }" />
          {{ subject(s.subject) }} · {{ t("exams.fullScore") }} {{ s.full_score }}
        </span>
      </div>

      <!-- 就地编辑 -->
      <div v-if="editing" class="card" style="max-width: 620px">
        <div class="card__head">
          <h2 class="card__title">{{ t("action.edit") }} · {{ exam.name }}</h2>
        </div>
        <form class="card__body" @submit.prevent="saveEdit">
          <div class="form-grid">
            <FormField :label="t('examnew.name')" required>
              <input v-model="editForm.name" class="input" type="text" maxlength="80" />
            </FormField>
            <FormField :label="t('examnew.date')" required>
              <input v-model="editForm.exam_date" class="input" type="date" />
            </FormField>
            <FormField
              :label="t('examnew.endDate')"
              :hint="t('examnew.endDateHint')"
            >
              <input
                v-model="editForm.end_date"
                class="input"
                type="date"
                :min="editForm.exam_date || undefined"
              />
            </FormField>
          </div>
          <p class="field__hint" style="margin-bottom: 12px">{{ t("exam.subjectLockNote") }}</p>

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
        </form>
      </div>

      <!-- 各科统计 -->
      <div class="stat-grid">
        <div v-for="s in averages.school" :key="s.subject" class="stat">
          <div class="stat__label">{{ subject(s.subject) }} {{ t("exam.avg") }}</div>
          <div class="stat__value tnum">{{ s.avg }}</div>
          <div class="stat__sub">
            {{ t("exam.outOf") }} {{ s.full_score }}（{{ pct(s.avg, s.full_score) }}%） ·
            {{ t("exam.students", { count: s.count }) }}
          </div>
          <div class="stat__sub">
            {{ t("exam.min") }} {{ s.min }} · {{ t("exam.max") }} {{ s.max }}
          </div>
        </div>
      </div>

      <!-- 全校趋势 -->
      <div class="card">
        <div class="card__head">
          <div>
            <h2 class="card__title"><Icon name="trending" :size="16" /> {{ t("exam.trendTitle") }}</h2>
            <p class="card__desc">{{ t("exam.trendSub") }}</p>
          </div>
        </div>
        <div class="card__body">
          <LineChart
            v-if="trendChart"
            :labels="trendChart.labels"
            :dates="trendChart.dates"
            :series="trendChart.series"
            :y-max="trendChart.yMax"
            :highlight-index="trendChart.highlightIndex"
          />
        </div>
      </div>

      <!-- 各班对比 -->
      <div class="card">
        <div class="card__head">
          <h2 class="card__title"><Icon name="building" :size="16" /> {{ t("exam.perClass") }}</h2>
        </div>
        <div class="table-wrap">
          <table class="table table--stack">
            <thead>
              <tr>
                <th>{{ t("th.class") }}</th>
                <th v-for="subj in subjects" :key="subj" class="cell-num">
                  {{ subject(subj) }} {{ t("exam.avg") }}
                </th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in classRows" :key="row.label">
                <td data-label="班级"><span class="pill pill--outline">{{ row.label }}</span></td>
                <td
                  v-for="subj in subjects"
                  :key="subj"
                  class="cell-num"
                  :data-label="subject(subj)"
                >
                  <template v-if="row.cells[subj]">
                    <b class="tnum">{{ row.cells[subj].avg }}</b>
                    <span class="stat__sub">（{{ t("exam.students", { count: row.cells[subj].count }) }}）</span>
                  </template>
                  <span v-else class="muted">{{ t("common.none") }}</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </AsyncState>
</template>
