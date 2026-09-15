<script setup>
// 考试详情：全校趋势 + 各科统计 + 各班对比。虚线标出当前这次考试，
// 让用户一眼看出自己看的是哪一场（状态可见）。
import { computed, onMounted, ref, watch } from "vue"
import { useRouter } from "vue-router"
import api, { downloadFile, triggerDownload, uploadFile } from "../api"
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
const classes = ref([])
const classesTouched = ref(false)

async function load() {
  loading.value = true
  error.value = ""
  try {
    const [av, tr, ex, cls] = await Promise.all([
      api.get(`/exams/${props.id}/averages`),
      api.get("/exams/trend"),
      api.get(`/exams/${props.id}`),
      api.get("/classes").catch(() => []), // 拉不到班级只影响编辑下拉，不阻塞页面
    ])
    averages.value = av
    trendData.value = tr
    exam.value = ex
    classes.value = cls
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
  classesTouched.value = false
  editForm.value = {
    name: exam.value.name,
    exam_date: exam.value.exam_date,
    end_date: exam.value.end_date || "",
    class_ids: [...(exam.value.class_ids || [])],
  }
}
function cancelEdit() {
  editing.value = false
  editForm.value = {}
  editError.value = ""
  classesTouched.value = false
}

function toggleEditClass(id) {
  classesTouched.value = true
  const ids = new Set(editForm.value.class_ids)
  if (ids.has(id)) ids.delete(id)
  else ids.add(id)
  editForm.value = { ...editForm.value, class_ids: [...ids] }
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
    const payload = {
      name: editForm.value.name.trim(),
      exam_date: editForm.value.exam_date,
      end_date: editForm.value.end_date || null,
    }
    // 只有动过参加班级才提交 class_ids，避免把未改动的参加者意外重置
    if (classesTouched.value) payload.class_ids = [...editForm.value.class_ids]
    const updated = await api.patch(`/exams/${props.id}`, payload)
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

// --- 成绩 Excel 导入 ---
const scoreFileInput = ref(null)
const scoreFile = ref(null)
const importingScores = ref(false)
const scoreResult = ref(null)

function onScoreFile(e) {
  scoreFile.value = e.target.files[0] || null
  if (scoreFile.value) importScores()
  e.target.value = "" // 同一文件可重复选择
}

async function downloadScoreTemplate() {
  try {
    const { blob, filename } = await downloadFile(`/exams/${props.id}/scores/import-template`)
    triggerDownload(blob, filename)
  } catch (e) {
    notify({ tone: "error", title: "下载失败", detail: friendlyError(e) })
  }
}

async function importScores() {
  if (!scoreFile.value) {
    notify({ tone: "warn", title: t("exam.scoreImportPick") })
    return
  }
  importingScores.value = true
  scoreResult.value = null
  try {
    const r = await uploadFile(`/exams/${props.id}/scores/import`, scoreFile.value)
    scoreResult.value = r
    scoreFile.value = null
    notify({
      tone: r.errors.length ? "warn" : "ok",
      title: t("exam.scoreImportDone"),
      detail: `${t("exam.scoreImportOk")} ${r.imported_students} · ${t("exam.scoreImportError")} ${r.errors.length}`,
      timeout: 4000,
    })
    await load() // 平均分、趋势图立即反映新成绩
  } catch (e) {
    notify({ tone: "error", title: t("exam.scoreImportFail"), detail: friendlyError(e) })
  } finally {
    importingScores.value = false
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

// 这场考试还没有录入任何成绩时，趋势图没有可画的内容，不显示
const hasExamScores = computed(() => (averages.value?.school ?? []).length > 0)

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
  <AsyncState
    :loading="loading"
    :error="error"
    :empty="!loading && !error && !(averages && exam)"
    :empty-title="t('exam.loadEmptyTitle')"
    :rows="4"
    @retry="load"
  >
      <PageHeader
        :title="exam.name"
        :subtitle="`${formatDateRange(exam.exam_date, exam.end_date)} · ${t('exam.attributionNote')}`"
      >
        <template #actions>
          <button v-if="!editing" class="btn" @click="downloadScoreTemplate">
            <Icon name="download" :size="15" /> {{ t("exam.scoreTemplate") }}
          </button>
          <button v-if="!editing" class="btn btn--primary" :disabled="importingScores" @click="scoreFileInput?.click()">
            <span v-if="importingScores" class="spinner" />
            <Icon name="upload" :size="15" /> {{ t("exam.scoreImport") }}
          </button>
          <input
            ref="scoreFileInput"
            type="file"
            accept=".xlsx"
            class="sr-only"
            @change="onScoreFile"
          />
          <button v-if="!editing" class="btn" @click="startEdit">
            <Icon name="pencil" :size="15" /> {{ t("action.edit") }}
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

      <!-- 成绩导入结果：哪些学生成功、哪些没有 -->
      <div v-if="scoreResult" class="card" style="margin-bottom: 20px">
        <div class="card__head">
          <div>
            <h2 class="card__title"><Icon name="upload" :size="16" /> {{ t("exam.scoreImportTitle") }}</h2>
            <p class="card__desc">{{ t("exam.scoreImportDone") }} {{ scoreResult.imported_students }} 人 · 登记成绩 {{ scoreResult.entered_scores }} 条<template v-if="scoreResult.absent_scores">（含缺考 {{ scoreResult.absent_scores }}）</template></p>
          </div>
          <button class="btn btn--sm" @click="scoreResult = null">{{ t("action.close") }}</button>
        </div>
        <div class="table-wrap">
          <table class="table">
            <thead>
              <tr><th>行号</th><th>学号</th><th>姓名</th><th>导入科目</th><th>结果</th></tr>
            </thead>
            <tbody>
              <tr v-for="r in scoreResult.rows" :key="r.row">
                <td class="tnum">{{ r.row }}</td>
                <td class="tnum">{{ r.admission_no || "—" }}</td>
                <td>{{ r.name || "—" }}</td>
                <td>
                  <template v-if="r.subjects.length">{{ r.subjects.map(subject).join("、") }}</template>
                  <template v-else-if="r.absent_subjects.length">缺考：{{ r.absent_subjects.map(subject).join("、") }}</template>
                  <template v-else>—</template>
                </td>
                <td>
                  <span v-if="r.status === 'ok'" class="pill pill--outline">{{ t("exam.scoreImportOk") }}</span>
                  <span v-else-if="r.status === 'partial'" class="pill pill--outline" :title="r.message">
                    {{ t("exam.scoreImportPartial") }} · {{ r.message }}
                  </span>
                  <span v-else class="pill pill--outline" style="color: var(--danger)">
                    {{ t("exam.scoreImportError") }} · {{ r.message }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
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

          <div class="field">
            <span class="field__label">
              {{ t("examnew.classes") }}
              <span v-if="editForm.class_ids?.length" class="field__opt">
                {{ t("examnew.classesSelected", { n: editForm.class_ids.length }) }}
              </span>
            </span>
            <div class="row-wrap" style="margin-top: 4px">
              <button
                v-for="c in classes"
                :key="c.id"
                type="button"
                class="chip"
                :class="{ 'chip--selected': editForm.class_ids.includes(c.id) }"
                :aria-pressed="editForm.class_ids.includes(c.id)"
                :disabled="editSaving"
                @click="toggleEditClass(c.id)"
              >
                <Icon v-if="editForm.class_ids.includes(c.id)" name="check" :size="13" />
                {{ c.name }}
                <span class="muted tnum" style="font-size: 12px">{{ c.student_count }}</span>
              </button>
            </div>
            <span class="field__hint">{{ t("examnew.classesHint") }}</span>
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
            <span class="form-actions__spacer" />
            <button
              type="button"
              class="btn btn--danger"
              :disabled="editSaving"
              @click="removeExam"
            >
              <Icon name="trash" :size="14" /> {{ t("action.delete") }}
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
            v-if="trendChart && hasExamScores"
            :labels="trendChart.labels"
            :dates="trendChart.dates"
            :series="trendChart.series"
            :y-max="trendChart.yMax"
            :highlight-index="trendChart.highlightIndex"
          />
          <!-- card__body 自带 20px 内边距，这里不再加水平 padding，保证与标题左对齐 -->
          <p v-else class="muted">
            还没有成绩录入，录入后这里会显示全校平均分趋势。
          </p>
        </div>
      </div>

      <!-- 各班对比 -->
      <div class="card">
        <div class="card__head">
          <h2 class="card__title"><Icon name="building" :size="16" /> {{ t("exam.perClass") }}</h2>
        </div>
        <div class="table-wrap">
          <p v-if="!classRows.length" class="muted" style="padding: var(--sp-2) var(--sp-5)">
            {{ t("exam.perClassEmpty") }}
          </p>
          <table v-else class="table table--stack">
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
  </AsyncState>
</template>
