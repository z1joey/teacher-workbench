<script setup>
// 新建考试：常用科目一点即加，每科可改名称 / 满分 / 颜色；也可自行添加。
import { computed, onMounted, ref } from "vue"
import { useRouter } from "vue-router"
import Icon from "../components/Icon.vue"
import PageHeader from "../components/PageHeader.vue"
import FormField from "../components/FormField.vue"
import api from "../api"
import { COMMON_SUBJECTS, friendlyError, subject, t, todayStr } from "../strings"

const router = useRouter()

let nextRowId = 1

function presetRow(p) {
  return {
    id: nextRowId++,
    key: p.key,
    name: p.label,
    full_score: p.fullScore,
    color: p.color,
    fromPreset: true,
  }
}

const form = ref({
  name: "",
  // 默认今天：不选日期直接创建时，考试落在当天（结束日期留空即单日考试）
  exam_date: todayStr(),
  end_date: "",
  subjects: [
    presetRow(COMMON_SUBJECTS.find((s) => s.key === "math")),
    presetRow(COMMON_SUBJECTS.find((s) => s.key === "english")),
  ],
  class_ids: [],
})
const busy = ref(false)
const error = ref("")
const errors = ref({})

// 参加班级：以班级为单位圈定参加考试的学生；不选 = 全校在读学生
const classes = ref([])
const selectedClassCount = computed(() => form.value.class_ids.length)

function toggleClass(id) {
  const idx = form.value.class_ids.indexOf(id)
  if (idx >= 0) form.value.class_ids.splice(idx, 1)
  else form.value.class_ids.push(id)
}

onMounted(async () => {
  try {
    classes.value = await api.get("/classes")
  } catch {
    classes.value = [] // 拉不到班级也不阻塞创建，仍可全校范围
  }
})

function catalogOf(key) {
  return COMMON_SUBJECTS.find((s) => s.key === key)
}

function isPresetSelected(key) {
  return form.value.subjects.some((row) => row.fromPreset && row.key === key)
}

function subjectKey(row) {
  if (row.fromPreset) {
    const p = catalogOf(row.key)
    if (p && row.name.trim() === p.label) return row.key
  }
  return row.name.trim()
}

const selectedCount = computed(() => form.value.subjects.length)

const allPresetsSelected = computed(() =>
  COMMON_SUBJECTS.every((p) => isPresetSelected(p.key))
)

function dateError() {
  const year = Number((form.value.exam_date || "").slice(0, 4))
  if (!form.value.exam_date || year < 2000 || year > 2100) return t("examnew.dateInvalid")
  return ""
}

function endDateError() {
  if (form.value.end_date && form.value.exam_date && form.value.end_date < form.value.exam_date) {
    return t("examnew.endDateInvalid")
  }
  return ""
}

function validate() {
  const e = {}
  if (!form.value.name.trim()) e.name = t("examnew.nameRequired")
  if (!form.value.subjects.length) e.subjects = t("examnew.subjectsRequired")
  const keys = form.value.subjects.map(subjectKey)
  if (keys.some((k) => !k)) e.subjects = t("examnew.subjectNameRequired")
  else if (new Set(keys).size !== keys.length) e.subjects = t("examnew.subjectDup")
  else if (form.value.subjects.some((row) => !Number(row.full_score) || Number(row.full_score) <= 0)) {
    e.subjects = t("examnew.fullScoreInvalid")
  }
  const de = dateError()
  if (de) e.exam_date = de
  const ee = endDateError()
  if (ee) e.end_date = ee
  errors.value = e
  return !Object.keys(e).length
}

async function submit() {
  error.value = ""
  if (!validate()) return
  busy.value = true
  try {
    const res = await api.post("/exams", {
      name: form.value.name.trim(),
      exam_date: form.value.exam_date,
      end_date: form.value.end_date || null,
      subjects: form.value.subjects.map((row) => ({
        subject: subjectKey(row),
        full_score: Number(row.full_score),
        color: row.color,
      })),
      class_ids: form.value.class_ids,
    })
    router.push(`/exams/${res.id}`)
  } catch (e) {
    error.value = friendlyError(e)
  } finally {
    busy.value = false
  }
}

function togglePreset(p) {
  const idx = form.value.subjects.findIndex((row) => row.fromPreset && row.key === p.key)
  if (idx >= 0) form.value.subjects.splice(idx, 1)
  else form.value.subjects.push(presetRow(p))
  if (form.value.subjects.length) errors.value.subjects = ""
}

function toggleAllPresets() {
  if (allPresetsSelected.value) {
    form.value.subjects = form.value.subjects.filter((row) => !row.fromPreset)
  } else {
    for (const p of COMMON_SUBJECTS) {
      if (!isPresetSelected(p.key)) form.value.subjects.push(presetRow(p))
    }
  }
  if (form.value.subjects.length) errors.value.subjects = ""
}

function addCustom() {
  form.value.subjects.push({
    id: nextRowId++,
    key: "",
    name: "",
    full_score: 100,
    color: "#64748b",
    fromPreset: false,
  })
  errors.value.subjects = ""
}

function removeRow(id) {
  form.value.subjects = form.value.subjects.filter((row) => row.id !== id)
}
</script>

<template>
  <PageHeader :title="t('examnew.title')" :subtitle="t('examnew.subtitle')" />

  <div class="card" style="max-width: 620px">
    <form class="card__body" @submit.prevent="submit" novalidate>
      <FormField :label="t('examnew.name')" required :error="errors.name || ''">
        <input
          v-model="form.name"
          class="input"
          type="text"
          maxlength="80"
          :aria-invalid="!!errors.name"
        />
      </FormField>

      <div class="form-grid">
        <FormField :label="t('examnew.date')" required :error="errors.exam_date || ''">
          <input
            v-model="form.exam_date"
            class="input"
            type="date"
            :aria-invalid="!!errors.exam_date"
          />
        </FormField>
        <FormField
          :label="t('examnew.endDate')"
          :hint="t('examnew.endDateHint')"
          :error="errors.end_date || ''"
        >
          <input
            v-model="form.end_date"
            class="input"
            type="date"
            :min="form.exam_date || undefined"
            :aria-invalid="!!errors.end_date"
          />
        </FormField>
      </div>

      <div class="field">
        <span class="field__label">
          {{ t("examnew.subjects") }} <span class="field__req">*</span>
          <span class="field__opt">已选 {{ selectedCount }} 科</span>
        </span>
        <div class="row-wrap" style="margin-top: 4px">
          <button
            type="button"
            class="chip"
            :class="{ 'chip--selected': allPresetsSelected }"
            :aria-pressed="allPresetsSelected"
            @click="toggleAllPresets"
          >
            <Icon v-if="allPresetsSelected" name="check" :size="13" />
            {{ t("examnew.selectAllSubjects") }}
          </button>
          <button
            v-for="p in COMMON_SUBJECTS"
            :key="p.key"
            type="button"
            class="chip"
            :class="{ 'chip--selected': isPresetSelected(p.key) }"
            :style="isPresetSelected(p.key)
              ? { borderColor: p.color, color: p.color, background: p.color + '1a' }
              : {}"
            :aria-pressed="isPresetSelected(p.key)"
            @click="togglePreset(p)"
          >
            <Icon v-if="isPresetSelected(p.key)" name="check" :size="13" />
            {{ p.label }}
          </button>
          <button type="button" class="chip" @click="addCustom">
            <Icon name="plus" :size="13" /> {{ t("examnew.addSubject") }}
          </button>
        </div>
        <div class="stack" style="gap: 8px; margin-top: 12px">
          <div
            v-for="row in form.subjects"
            :key="row.id"
            class="subject-row"
          >
            <input
              v-model="row.color"
              class="input input--color"
              type="color"
              :aria-label="t('examnew.subjectColor')"
            />
            <input
              v-model="row.name"
              class="input subject-row__name"
              type="text"
              maxlength="50"
              :placeholder="row.fromPreset ? subject(row.key) : t('examnew.customSubject')"
              :aria-label="t('examnew.subjectName')"
            />
            <label class="subject-row__score">
              <span class="muted">{{ t("examnew.fullScore") }}</span>
              <input
                v-model.number="row.full_score"
                class="input"
                type="number"
                min="1"
                max="1000"
                step="1"
                :aria-label="t('examnew.fullScore')"
              />
            </label>
            <button
              type="button"
              class="btn btn--ghost btn--sm"
              :aria-label="t('action.delete')"
              @click="removeRow(row.id)"
            >
              <Icon name="x" :size="14" />
            </button>
          </div>
        </div>
        <span v-if="errors.subjects" class="field__error">
          <Icon name="alert-circle" :size="12" /> {{ errors.subjects }}
        </span>
        <span v-else class="field__hint">{{ t("examnew.subjectsHint") }}</span>
      </div>

      <div class="field">
        <span class="field__label">
          {{ t("examnew.classes") }}
          <span v-if="selectedClassCount" class="field__opt">
            {{ t("examnew.classesSelected", { n: selectedClassCount }) }}
          </span>
        </span>
        <div class="row-wrap" style="margin-top: 4px">
          <button
            v-for="c in classes"
            :key="c.id"
            type="button"
            class="chip"
            :class="{ 'chip--selected': form.class_ids.includes(c.id) }"
            :aria-pressed="form.class_ids.includes(c.id)"
            @click="toggleClass(c.id)"
          >
            <Icon v-if="form.class_ids.includes(c.id)" name="check" :size="13" />
            {{ c.name }}
            <span class="muted tnum" style="font-size: 12px">{{ c.student_count }}</span>
          </button>
        </div>
        <span class="field__hint">{{ t("examnew.classesHint") }}</span>
      </div>

      <p v-if="error" class="field__error" style="margin-bottom: 12px">
        <Icon name="alert-circle" :size="13" /> {{ error }}
      </p>

      <div class="form-actions">
        <button type="submit" class="btn btn--primary" :disabled="busy">
          <span v-if="busy" class="spinner" />
          {{ busy ? t("examnew.saving") : t("examnew.submit") }}
        </button>
        <router-link to="/exams" class="btn btn--ghost">{{ t("action.cancel") }}</router-link>
      </div>
    </form>
  </div>
</template>
