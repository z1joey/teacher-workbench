<script setup>
// 班级内容主体：座位表 + 趋势 + 名单 + 各科平均；未分班作为顶部可选的特殊班。
// 由 /classes（下拉选班）和 /classes/:id（深链接）两个宿主复用；
// 多班时页头出现下拉框切换，单班只显示班级名称。
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue"
import { useRouter } from "vue-router"
import api from "../api"
import Icon from "./Icon.vue"
import PageHeader from "./PageHeader.vue"
import AsyncState from "./AsyncState.vue"
import FormField from "./FormField.vue"
import LineChart from "./LineChart.vue"
import SeatingBoard from "./SeatingBoard.vue"
import SelectMenu from "./SelectMenu.vue"
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
    const c = detail.value.class
    setPageTitle(
      c.is_unassigned ? c.name : classBreadcrumbLabel(c.name, c.academic_year),
    )
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
})
watch(() => props.classId, load)

const isUnassigned = computed(() => !!detail.value?.class?.is_unassigned)
const isArchived = computed(() => !!detail.value?.class?.archived)

// 切换器选项：空的「未分班」默认不出现（当前正在看它时保留，避免标题丢名）
const switcherOptions = computed(() =>
  allClasses.value
    .filter(
      (c) => !c.is_unassigned || c.student_count > 0 || c.id === props.classId,
    )
    .map((c) => ({ value: c.id, label: classLabel(c) })),
)

function classLabel(c) {
  if (c.is_unassigned) return c.name
  return duplicateNames.value.has(c.name) ? `${c.name}（${c.academic_year}）` : c.name
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

// ------------------------------------------------------------------ 批量分配
// 选择模式下名单 chip 变为勾选，确认后一次请求调入目标班级；
// 已在目标班级的学生由后端跳过并在 toast 里说明。
const selectMode = ref(false)
const selectedIds = ref(new Set())
const targetClassId = ref("")
const batchSubmitting = ref(false)
const batchError = ref("")

// ------------------------------------------------------------------ 班级归档
// 毕业操作集中在个人中心；这里只负责已归档班级的展示与取消归档。
const unarchiving = ref(false)

async function unarchiveClass() {
  unarchiving.value = true
  try {
    await api.patch(`/classes/${props.classId}`, { archived: false })
    notify({ tone: "ok", title: t("classdetail.unarchiveDone"), timeout: 2600 })
    await Promise.all([load(), loadClassList()])
    emit("changed")
  } catch (e) {
    notify({ tone: "error", title: friendlyError(e), timeout: 3200 })
  } finally {
    unarchiving.value = false
  }
}

const targetClasses = computed(() =>
  allClasses.value.filter((c) => c.id !== props.classId && !c.archived),
)

function exitSelectMode() {
  selectMode.value = false
  selectedIds.value = new Set()
  batchError.value = ""
}

function toggleSelectMode() {
  if (selectMode.value) {
    exitSelectMode()
    return
  }
  selectMode.value = true
  targetClassId.value = targetClasses.value[0]?.id ?? ""
}

function toggleStudent(id) {
  const next = new Set(selectedIds.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  selectedIds.value = next
}

const allSelected = computed(
  () =>
    detail.value.students.length > 0 &&
    detail.value.students.every((s) => selectedIds.value.has(s.id)),
)

function toggleAll() {
  selectedIds.value = allSelected.value
    ? new Set()
    : new Set(detail.value.students.map((s) => s.id))
}

async function confirmBatchAssign() {
  const target = targetClasses.value.find((c) => c.id === targetClassId.value)
  if (!selectedIds.value.size || !target) return
  const ok = await ask({
    title: t("classdetail.batchConfirmTitle", { n: selectedIds.value.size, class: target.name }),
    message: t("classdetail.batchConfirmHint"),
    confirmLabel: t("classdetail.batchConfirm"),
  })
  if (!ok) return
  batchSubmitting.value = true
  batchError.value = ""
  try {
    const res = await api.post(`/classes/${target.id}/enrollments`, {
      student_ids: [...selectedIds.value],
    })
    notify({
      tone: "ok",
      title: res.skipped.length
        ? t("classdetail.batchDoneSkipped", { moved: res.moved.length, skipped: res.skipped.length })
        : t("classdetail.batchDone", { n: res.moved.length }),
      timeout: 3200,
    })
    exitSelectMode()
    await Promise.all([load(), loadUnassigned()])
    emit("changed")
  } catch (e) {
    batchError.value = friendlyError(e)
  } finally {
    batchSubmitting.value = false
  }
}

function onBatchKeydown(e) {
  if (e.key === "Escape" && selectMode.value && !showAddStudent.value) exitSelectMode()
}
onMounted(() => window.addEventListener("keydown", onBatchKeydown))
onBeforeUnmount(() => window.removeEventListener("keydown", onBatchKeydown))

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
        <template v-if="switcherOptions.length > 1" #title>
          <SelectMenu
            :model-value="classId"
            :options="switcherOptions"
            aria-label="选择班级"
            trigger-class="class-switcher__select"
            @update:model-value="(id) => emit('switch', id)"
          >
            <template #trigger="{ label }">
              <span>{{ label }}</span>
              <Icon name="chevron-down" :size="18" class="switcher-chevron" />
            </template>
          </SelectMenu>
        </template>
        <template #actions>
          <span v-if="isArchived" class="pill pill--muted">{{ t("classes.archived") }}</span>
          <button class="btn btn--ghost" @click="emit('create')">
            <Icon name="plus" :size="15" /> {{ t("classes.create") }}
          </button>
          <button v-if="!isUnassigned && !isArchived && !editing" class="btn" @click="startEdit">
            <Icon name="pencil" :size="15" /> {{ t("action.edit") }}
          </button>
          <button v-if="isArchived" class="btn" :disabled="unarchiving" @click="unarchiveClass">
            <span v-if="unarchiving" class="spinner" />
            {{ t("classdetail.unarchive") }}
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

      <!-- 座位表：未分班不显示 -->
      <SeatingBoard v-if="!isUnassigned" :class-id="classId" :students="detail.students" />

      <div class="split">
        <div>
          <div v-if="!isUnassigned" class="card">
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

          <div class="card">
            <div class="card__head">
              <div class="grow">
                <h2 class="card__title"><Icon name="users" :size="16" /> {{ t("classdetail.roster") }}</h2>
                <p v-if="isUnassigned" class="card__desc">{{ t("classes.unassignedHint") }}</p>
              </div>
              <template v-if="detail.students.length && !isArchived && selectMode">
                <button type="button" class="btn btn--sm" @click="toggleAll">
                  {{ allSelected ? t("classdetail.batchNone") : t("classdetail.batchAll") }}
                </button>
              </template>
              <button
                v-if="detail.students.length && !isArchived"
                type="button"
                class="btn btn--sm"
                :class="{ 'btn--primary': selectMode }"
                @click="toggleSelectMode"
              >
                {{ selectMode ? t("classdetail.batchExit") : t("classdetail.batchSelect") }}
              </button>
              <span v-if="!selectMode" class="pill pill--muted pill--count">{{ detail.students.length }}</span>
            </div>
            <div class="card__body">
              <div v-if="detail.students.length" class="chips">
                <template v-for="s in detail.students" :key="s.id">
                  <button
                    v-if="selectMode"
                    type="button"
                    class="chip chip--toggle"
                    :class="{ 'is-on': selectedIds.has(s.id) }"
                    :aria-pressed="selectedIds.has(s.id)"
                    @click="toggleStudent(s.id)"
                  >
                    <span class="chip__mark" aria-hidden="true">✓</span>
                    {{ s.name }}
                    <span class="muted" style="font-size: 12px">
                      {{ isUnassigned ? s.admission_no : genderLabel(s.gender) }}
                    </span>
                  </button>
                  <router-link
                    v-else
                    :to="{
                      path: `/students/${s.id}`,
                      query: { from: 'class', classId: props.classId, className: detail.class.name },
                    }"
                    class="chip"
                    :title="s.admission_no"
                  >
                    {{ s.name }}
                    <span class="muted" style="font-size: 12px">
                      {{ isUnassigned ? s.admission_no : genderLabel(s.gender) }}
                    </span>
                  </router-link>
                </template>
              </div>
              <div v-else class="state state--in-card">
                <p class="state__desc">{{ t("classes.noStudents") }}</p>
              </div>
            </div>
          </div>
        </div>

        <div v-if="!isUnassigned" class="card">
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

      <!-- 批量分配底部操作条 -->
      <template v-if="selectMode && selectedIds.size">
        <div class="batch-bar">
          <div class="batch-bar__in">
            <span class="batch-bar__count">{{ t("classdetail.batchSelected", { n: selectedIds.size }) }}</span>
            <div class="batch-bar__right">
              <label class="batch-bar__field">
                <span class="batch-bar__label">{{ t("classdetail.batchTarget") }}</span>
                <select
                  v-model="targetClassId"
                  class="input input--sm batch-bar__select"
                  :disabled="batchSubmitting"
                >
                  <option v-for="c in targetClasses" :key="c.id" :value="c.id">{{ classLabel(c) }}</option>
                </select>
              </label>
              <button
                type="button"
                class="btn btn--primary"
                :disabled="batchSubmitting || !targetClassId"
                @click="confirmBatchAssign"
              >
                <span v-if="batchSubmitting" class="spinner" />
                {{ t("classdetail.batchConfirm") }}
              </button>
              <button
                type="button"
                class="icon-btn batch-bar__close"
                :aria-label="t('classdetail.batchExit')"
                :disabled="batchSubmitting"
                @click="exitSelectMode"
              >
                <Icon name="close" :size="15" />
              </button>
            </div>
          </div>
          <p v-if="batchError" class="batch-bar__error">
            <Icon name="alert-circle" :size="12" /> {{ batchError }}
          </p>
        </div>
        <div class="batch-bar-spacer" aria-hidden="true"></div>
      </template>
  </AsyncState>
</template>

<style scoped>
.switcher-chevron {
  flex-shrink: 0;
  color: var(--muted);
}
</style>
