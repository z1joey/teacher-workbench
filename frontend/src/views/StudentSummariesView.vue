<script setup>
// 学生总结：AI 生成 + 历史总结管理。
// 总结是教师私有事件——学生时间线看不到，首页「最新动态」和本页都可进入；
// 从动态点进来时 ?focus=<id> 会定位并展开对应那条。
import { computed, nextTick, onMounted, ref, watch } from "vue"
import { useRoute } from "vue-router"
import Icon from "../components/Icon.vue"
import PageHeader from "../components/PageHeader.vue"
import FormField from "../components/FormField.vue"
import api from "../api"
import { ask } from "../confirm"
import { notify, runUndoable } from "../feedback"
import { friendlyError, t } from "../strings"
import { setPageCrumbs } from "../title"

const props = defineProps({
  studentId: { type: String, required: true },
})

const route = useRoute()

const studentName = ref("")
const loading = ref(true)
const loadError = ref("")

// ---- 生成表单（时间段默认“全部”） ----
const rangePreset = ref("all") // all | 90d | half | custom
const customFrom = ref("")
const customTo = ref("")
const length = ref("standard") // brief | standard | detailed
const style = ref("formal") // formal | warm | motivational

const generating = ref(false)
const generateError = ref("")
const preview = ref(null) // null = 没有可保存的预览

// ---- 历史总结 ----
const history = ref([])
const historyLoading = ref(false)
const editingId = ref(null)
const editText = ref("")
const editSaving = ref(false)

const RANGE_OPTIONS = [
  { value: "all", label: t("summary.rangeAll") },
  { value: "90d", label: t("summary.range90d") },
  { value: "half", label: t("summary.rangeHalfYear") },
  { value: "custom", label: t("summary.rangeCustom") },
]
const LENGTH_OPTIONS = [
  { value: "brief", label: t("summary.lengthBrief") },
  { value: "standard", label: t("summary.lengthStandard") },
  { value: "detailed", label: t("summary.lengthDetailed") },
]
const STYLE_OPTIONS = [
  { value: "formal", label: t("summary.styleFormal") },
  { value: "warm", label: t("summary.styleWarm") },
  { value: "motivational", label: t("summary.styleMotivational") },
]

const LENGTH_LABELS = {
  brief: t("summary.lengthBrief"),
  standard: t("summary.lengthStandard"),
  detailed: t("summary.lengthDetailed"),
}
const STYLE_LABELS = {
  formal: t("summary.styleFormal"),
  warm: t("summary.styleWarm"),
  motivational: t("summary.styleMotivational"),
}

function shiftDays(days) {
  const d = new Date()
  d.setDate(d.getDate() - days)
  return d.toISOString().slice(0, 10)
}

const dateRange = computed(() => {
  if (rangePreset.value === "90d") return { date_from: shiftDays(90), date_to: null }
  if (rangePreset.value === "half") return { date_from: shiftDays(182), date_to: null }
  if (rangePreset.value === "custom") {
    return { date_from: customFrom.value || null, date_to: customTo.value || null }
  }
  return { date_from: null, date_to: null }
})

function rangeLabel(item) {
  const p = item.params || {}
  if (!p.date_from && !p.date_to) return t("summary.rangeAll")
  const from = p.date_from || "…"
  const to = p.date_to || "今天"
  return `${from} ~ ${to}`
}

async function loadHistory() {
  historyLoading.value = true
  try {
    history.value = await api.get(`/students/${props.studentId}/summaries`)
  } catch (e) {
    loadError.value = friendlyError(e)
  } finally {
    historyLoading.value = false
  }
}

async function load() {
  loading.value = true
  try {
    const student = await api.get(`/students/${props.studentId}`)
    studentName.value = student.name || ""
  } catch (e) {
    loadError.value = friendlyError(e)
    loading.value = false
    return
  }
  // 面包屑：学生 / <学生名>(回学生档案) / 学生总结
  setPageCrumbs([
    { label: studentName.value, to: `/students/${props.studentId}` },
  ])
  await loadHistory()
  loading.value = false
  await focusFromQuery()
}

onMounted(load)
watch(() => props.studentId, load)

watch(
  () => route.query.focus,
  () => focusFromQuery()
)

async function focusFromQuery() {
  const focus = route.query.focus
  if (!focus) return
  const item = history.value.find((s) => s.id === focus)
  if (!item) return
  startEdit(item)
  await nextTick()
  document.getElementById(`summary-${item.id}`)?.scrollIntoView({ block: "center" })
}

// ---- 生成 ----

function validateRange() {
  if (rangePreset.value !== "custom") return ""
  if (customFrom.value && customTo.value && customFrom.value > customTo.value) {
    return t("summary.rangeInvalid")
  }
  return ""
}

async function generate() {
  generateError.value = ""
  const invalid = validateRange()
  if (invalid) {
    generateError.value = invalid
    return
  }
  generating.value = true
  try {
    const res = await api.post(`/students/${props.studentId}/summary/generate`, {
      ...dateRange.value,
      length: length.value,
      style: style.value,
    })
    preview.value = res.content || ""
    if (!preview.value) generateError.value = friendlyError(new Error("AI 未返回内容，请稍后再试"))
  } catch (e) {
    const msg = friendlyError(e)
    // 422：所选时间段内没有学生记录 —— 表单里友好提示
    generateError.value = msg.includes("没有学生记录") ? t("summary.emptyRange") : msg
  } finally {
    generating.value = false
  }
}

async function saveSummary() {
  if (!preview.value?.trim()) return
  generating.value = true
  try {
    await api.post("/summaries", {
      student_id: props.studentId,
      content: preview.value.trim(),
      length: length.value,
      style: style.value,
      ...dateRange.value,
    })
    preview.value = null
    await loadHistory()
    notify({ tone: "ok", title: t("summary.saved"), timeout: 2400 })
  } catch (e) {
    generateError.value = friendlyError(e)
  } finally {
    generating.value = false
  }
}

function discardPreview() {
  preview.value = null
  generateError.value = ""
}

// ---- 历史总结 ----

function startEdit(item) {
  editingId.value = item.id
  editText.value = item.content
}

function cancelEdit() {
  editingId.value = null
  editText.value = ""
}

async function saveEdit(item) {
  const content = editText.value.trim()
  if (!content || content === item.content) {
    cancelEdit()
    return
  }
  editSaving.value = true
  try {
    await api.patch(`/summaries/${item.id}`, { content })
    item.content = content
    item.edited = true
    editingId.value = null
    notify({ tone: "ok", title: t("common.saved"), timeout: 2400 })
  } catch (e) {
    notify({ tone: "error", title: friendlyError(e), timeout: 4000 })
  } finally {
    editSaving.value = false
  }
}

function removeSummary(item) {
  // 先把条目从列表里拿掉；撤销则重新加载，宽限期结束后才真正删除
  const name = studentName.value || ""
  history.value = history.value.filter((s) => s.id !== item.id)
  runUndoable({
    title: `已删除「${name}」的总结`,
    run: () => api.delete(`/summaries/${item.id}`),
    onUndo: loadHistory,
    successTitle: t("summary.deleted"),
  })
}

function fmtDateTime(iso) {
  if (!iso) return ""
  const d = new Date(iso)
  return d.toLocaleString("zh-CN", {
    year: "numeric",
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  })
}
</script>

<template>
  <PageHeader :title="t('summary.title')" :subtitle="studentName || t('summary.subtitle')" />
  <p class="card__desc" style="max-width: 720px; margin-top: -6px">
    {{ t("summary.subtitle") }}
  </p>

  <div v-if="loadError" class="card" style="max-width: 720px">
    <div class="card__body">
      <p class="field__error"><Icon name="alert-circle" :size="13" /> {{ loadError }}</p>
    </div>
  </div>

  <template v-else>
    <!-- 生成新总结 -->
    <div class="card" style="max-width: 720px">
      <div class="card__body">
        <div class="field">
          <div class="field__label">{{ t("summary.rangeLabel") }}</div>
          <div class="segmented" role="radiogroup" :aria-label="t('summary.rangeLabel')">
            <button
              v-for="opt in RANGE_OPTIONS"
              :key="opt.value"
              type="button"
              class="segmented__item"
              :class="{ 'is-active': rangePreset === opt.value }"
              @click="rangePreset = opt.value"
            >
              {{ opt.label }}
            </button>
          </div>
          <div v-if="rangePreset === 'custom'" class="form-grid" style="margin-top: 10px">
            <FormField :label="t('summary.rangeFrom')" optional>
              <input v-model="customFrom" class="input" type="date" />
            </FormField>
            <FormField :label="t('summary.rangeTo')" optional>
              <input v-model="customTo" class="input" type="date" />
            </FormField>
          </div>
        </div>

        <div class="field">
          <div class="field__label">{{ t("summary.lengthLabel") }}</div>
          <div class="segmented" role="radiogroup" :aria-label="t('summary.lengthLabel')">
            <button
              v-for="opt in LENGTH_OPTIONS"
              :key="opt.value"
              type="button"
              class="segmented__item"
              :class="{ 'is-active': length === opt.value }"
              @click="length = opt.value"
            >
              {{ opt.label }}
            </button>
          </div>
        </div>

        <div class="field">
          <div class="field__label">{{ t("summary.styleLabel") }}</div>
          <div class="segmented" role="radiogroup" :aria-label="t('summary.styleLabel')">
            <button
              v-for="opt in STYLE_OPTIONS"
              :key="opt.value"
              type="button"
              class="segmented__item"
              :class="{ 'is-active': style === opt.value }"
              @click="style = opt.value"
            >
              {{ opt.label }}
            </button>
          </div>
        </div>

        <p v-if="generateError" class="field__error" style="margin-top: 10px">
          <Icon name="alert-circle" :size="13" /> {{ generateError }}
        </p>

        <div class="form-actions">
          <button type="button" class="btn btn--primary" :disabled="generating" @click="generate">
            <span v-if="generating" class="spinner" />
            {{ generating ? t("summary.generating") : t("summary.generate") }}
          </button>
        </div>

        <div v-if="preview !== null" class="field" style="margin-top: 16px">
          <div class="field__label">{{ t("summary.previewLabel") }}</div>
          <textarea v-model="preview" class="input" rows="7" />
          <div class="form-actions">
            <button
              type="button"
              class="btn btn--primary"
              :disabled="generating || !preview.trim()"
              @click="saveSummary"
            >
              {{ t("summary.save") }}
            </button>
            <button type="button" class="btn btn--ghost" :disabled="generating" @click="generate">
              {{ t("summary.regenerate") }}
            </button>
            <button type="button" class="btn btn--ghost" :disabled="generating" @click="discardPreview">
              {{ t("action.cancel") }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 历史总结 -->
    <div class="card" style="max-width: 720px">
      <div class="card__body">
        <h2 class="section-title">
          {{ t("summary.historyTitle") }}
          <span v-if="history.length" class="muted" style="font-weight: 400">
            {{ t("summary.count", { n: history.length }) }}
          </span>
        </h2>

        <p v-if="historyLoading" class="muted">{{ t("action.saving") }}</p>
        <p v-else-if="!history.length" class="muted">{{ t("summary.historyEmpty") }}</p>

        <ul v-else class="summary-list">
          <li
            v-for="item in history"
            :id="`summary-${item.id}`"
            :key="item.id"
            class="summary-item"
          >
            <div class="between">
              <time class="timeline__time">{{ fmtDateTime(item.occurred_at) }}</time>
              <span v-if="editingId !== item.id" class="summary-item__actions">
                <button type="button" class="btn btn--sm" @click="startEdit(item)">
                  <Icon name="pencil" :size="13" /> {{ t("common.edit") }}
                </button>
                <button type="button" class="btn btn--sm" @click="removeSummary(item)">
                  <Icon name="trash" :size="13" /> {{ t("action.delete") }}
                </button>
              </span>
            </div>
            <p class="summary-item__meta">
              {{ LENGTH_LABELS[item.params?.length] || "" }}
              <template v-if="item.params?.style"> · {{ STYLE_LABELS[item.params.style] || item.params.style }}</template>
              · {{ rangeLabel(item) }}
              <template v-if="item.edited"> · {{ t("summary.edited") }}</template>
            </p>

            <p v-if="editingId !== item.id" class="summary-item__content">{{ item.content }}</p>
            <template v-else>
              <textarea v-model="editText" class="input" rows="6" />
              <div class="form-actions">
                <button
                  type="button"
                  class="btn btn--primary btn--sm"
                  :disabled="editSaving"
                  @click="saveEdit(item)"
                >
                  <span v-if="editSaving" class="spinner" /> {{ t("action.save") }}
                </button>
                <button type="button" class="btn btn--ghost btn--sm" @click="cancelEdit">
                  {{ t("action.cancel") }}
                </button>
              </div>
            </template>
          </li>
        </ul>
      </div>
    </div>
  </template>
</template>
