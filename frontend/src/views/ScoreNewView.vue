<script setup>
// 成绩录入（独立页面）：选考试 → 按科目填分。
// 已录入过成绩的考试与未录入的分组展示；选中已录入的考试会自动回填现有分数。
import { computed, onMounted, ref } from "vue"
import { useRouter } from "vue-router"
import Icon from "../components/Icon.vue"
import PageHeader from "../components/PageHeader.vue"
import api from "../api"
import { notify } from "../feedback"
import { friendlyError, subject, t } from "../strings"

const props = defineProps({
  studentId: { type: String, required: true },
})

const router = useRouter()
const student = ref(null)
const examOptions = ref([])
const loading = ref(true)
const saving = ref(false)
const error = ref("")
const selectedExamId = ref("")
const values = ref({})
const attended = ref({})

const chosenExam = computed(
  () => examOptions.value.find((e) => e.id === selectedExamId.value) ?? null
)

// 每场考试该学生已录的科目数：用于把考试分成「未录入 / 已录入」两组
const enteredCount = computed(() => {
  const map = new Map()
  for (const row of student.value?.scores ?? []) {
    if (!row.exam_id) continue
    map.set(row.exam_id, (map.get(row.exam_id) || 0) + 1)
  }
  return map
})

const unenteredExams = computed(() =>
  examOptions.value.filter((e) => !enteredCount.value.get(e.id))
)
const enteredExams = computed(() =>
  examOptions.value.filter((e) => enteredCount.value.get(e.id))
)

async function load() {
  loading.value = true
  error.value = ""
  try {
    const [studentDetail, exams] = await Promise.all([
      api.get(`/students/${props.studentId}`),
      api.get("/exams"),
    ])
    student.value = studentDetail
    examOptions.value = exams
  } catch (e) {
    error.value = friendlyError(e)
  } finally {
    loading.value = false
  }
}
onMounted(load)

function pickExam(e) {
  selectedExamId.value = e.id
  // 默认全部「参加考试」，取消勾选才记缺考
  const attendedMap = {}
  for (const s of e.subjects ?? []) attendedMap[s.subject] = true
  values.value = {}
  attended.value = attendedMap
  // 该考试已有成绩 → 自动回填分数与缺考状态，方便就地修改
  for (const row of student.value?.scores ?? []) {
    if (row.exam_id !== e.id || !(row.subject in attendedMap)) continue
    if (row.status === "absent") {
      attendedMap[row.subject] = false
    } else if (row.score != null) {
      values.value[row.subject] = row.score
    }
  }
}

function goBack() {
  router.push(`/students/${props.studentId}`)
}

async function save() {
  error.value = ""
  const exam = chosenExam.value
  if (!exam) {
    error.value = "请先选择考试"
    return
  }
  const scores = []
  for (const s of exam.subjects) {
    const raw = (values.value[s.subject] ?? "").toString().trim()
    if (attended.value[s.subject] === false) {
      // 取消了「参加考试」→ 记缺考
      scores.push({ subject: s.subject, absent: true })
      continue
    }
    if (!raw) continue // 参加了但这科没填分 → 不录入
    const value = Number(raw)
    if (Number.isNaN(value)) {
      error.value = `${subject(s.subject)} 的成绩要填数字`
      return
    }
    if (value < 0 || value > s.full_score) {
      error.value = `${subject(s.subject)} 的成绩需在 0 到 ${s.full_score} 之间`
      return
    }
    scores.push({ subject: s.subject, score: value })
  }
  if (!scores.length) {
    error.value = "至少填写一科成绩，或勾选缺考"
    return
  }
  saving.value = true
  try {
    await api.post(`/exams/${exam.id}/scores`, {
      student_id: props.studentId,
      scores,
    })
    notify({ tone: "ok", title: t("detail.scoreAdded"), timeout: 3000 })
    router.push(`/students/${props.studentId}`)
  } catch (e) {
    error.value = friendlyError(e)
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <PageHeader title="添加成绩" :subtitle="student?.name" />

  <div class="card" style="max-width: 640px">
    <div class="card__body">
      <div class="field">
        <span class="field__label">
          考试 <span class="field__req" aria-hidden="true">*</span>
        </span>
        <div class="score-exam-list" role="listbox" aria-label="选择考试">
          <template v-if="unenteredExams.length">
            <p class="score-exam-group-label">{{ t("scoreNew.groupUnentered") }}</p>
            <button
              v-for="e in unenteredExams"
              :key="e.id"
              type="button"
              role="option"
              :aria-selected="e.id === selectedExamId"
              class="score-exam-option"
              :class="{ 'is-active': e.id === selectedExamId }"
              @click="pickExam(e)"
            >
              <span class="grow">
                {{ e.name }} <span class="muted">（{{ e.exam_date }}）</span>
              </span>
              <span class="pill pill--muted">{{ t("scoreNew.badgeUnentered") }}</span>
              <Icon v-if="e.id === selectedExamId" name="check" :size="14" />
            </button>
          </template>
          <template v-if="enteredExams.length">
            <p class="score-exam-group-label">{{ t("scoreNew.groupEntered") }}</p>
            <button
              v-for="e in enteredExams"
              :key="e.id"
              type="button"
              role="option"
              :aria-selected="e.id === selectedExamId"
              class="score-exam-option"
              :class="{ 'is-active': e.id === selectedExamId }"
              @click="pickExam(e)"
            >
              <span class="grow">
                {{ e.name }} <span class="muted">（{{ e.exam_date }}）</span>
              </span>
              <span class="pill pill--ok">
                {{ t("scoreNew.badgeEntered", { n: enteredCount.get(e.id) }) }}
              </span>
              <Icon v-if="e.id === selectedExamId" name="check" :size="14" />
            </button>
          </template>
          <p v-if="!examOptions.length" class="muted" style="margin: 0; padding: 10px 12px">
            还没有可选择的考试
          </p>
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
              v-model="values[s.subject]"
              class="input input--sm tnum"
              type="number"
              step="0.1"
              min="0"
              :max="s.full_score"
              :disabled="!attended[s.subject]"
              :placeholder="attended[s.subject] ? '' : '缺考'"
              :aria-label="`${subject(s.subject)} 分数`"
              style="width: 90px"
            />
            <span class="muted">/ {{ s.full_score }}</span>
            <label class="check" style="margin: 0">
              <input v-model="attended[s.subject]" type="checkbox" />
              <span>参加考试</span>
            </label>
          </div>
        </div>
        <p class="field__hint" style="margin-top: 8px">
          默认全部参加考试：填了分的科目才会录入；取消勾选记为缺考；已有成绩的科目会被覆盖。
        </p>
      </template>

      <p v-if="error" class="field__error" style="margin-top: 10px">
        <Icon name="alert-circle" :size="12" /> {{ error }}
      </p>

      <div class="form-actions" style="margin-top: 16px">
        <button type="button" class="btn btn--ghost" @click="goBack">
          {{ t("action.cancel") }}
        </button>
        <button
          type="button"
          class="btn btn--primary"
          :disabled="saving || !chosenExam"
          @click="save"
        >
          <span v-if="saving" class="spinner" />
          {{ saving ? t("action.saving") : t("action.save") }}
        </button>
      </div>
    </div>
  </div>
</template>
