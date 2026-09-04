<script setup>
// 新建考试：科目用可见的勾选块而不是一列复选框，日期当场校验，
// 提交按钮在条件不满足时说明差什么（防错）。
import { computed, ref } from "vue"
import { useRouter } from "vue-router"
import Icon from "../components/Icon.vue"
import PageHeader from "../components/PageHeader.vue"
import FormField from "../components/FormField.vue"
import api from "../api"
import { friendlyError, subject, t } from "../strings"

const router = useRouter()
const SUBJECT_OPTIONS = ["math", "english", "chinese", "physics", "chemistry"]

const form = ref({
  name: "",
  exam_date: "",
  full_score: 100,
  selected: { math: true, english: true, chinese: false, physics: false, chemistry: false },
})
const busy = ref(false)
const error = ref("")
const errors = ref({})

const selectedSubjects = computed(() => SUBJECT_OPTIONS.filter((s) => form.value.selected[s]))

function dateError() {
  const year = Number((form.value.exam_date || "").slice(0, 4))
  if (!form.value.exam_date || year < 2000 || year > 2100) return t("examnew.dateInvalid")
  return ""
}

function validate() {
  const e = {}
  if (!form.value.name.trim()) e.name = t("examnew.nameRequired")
  if (!selectedSubjects.value.length) e.subjects = t("examnew.subjectsRequired")
  const de = dateError()
  if (de) e.exam_date = de
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
      subjects: selectedSubjects.value.map((s) => ({
        subject: s,
        full_score: Number(form.value.full_score),
      })),
    })
    router.push(`/exams/${res.id}`)
  } catch (e) {
    error.value = friendlyError(e)
  } finally {
    busy.value = false
  }
}

function toggleSubject(s) {
  form.value.selected[s] = !form.value.selected[s]
  if (selectedSubjects.value.length) errors.value.subjects = ""
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
          :label="t('examnew.fullScore')"
          hint="所有科目共用同一个满分"
        >
          <input
            v-model="form.full_score"
            class="input"
            type="number"
            min="1"
            max="1000"
            step="1"
          />
        </FormField>
      </div>

      <div class="field">
        <span class="field__label">
          {{ t("examnew.subjects") }} <span class="field__req">*</span>
          <span class="field__opt">已选 {{ selectedSubjects.length }} 科</span>
        </span>
        <div class="row-wrap" style="margin-top: 4px">
          <button
            v-for="s in SUBJECT_OPTIONS"
            :key="s"
            type="button"
            class="chip"
            :class="{ 'chip--selected': form.selected[s] }"
            :aria-pressed="form.selected[s]"
            @click="toggleSubject(s)"
          >
            <Icon v-if="form.selected[s]" name="check" :size="13" />
            {{ subject(s) }}
          </button>
        </div>
        <span v-if="errors.subjects" class="field__error">
          <Icon name="alert-circle" :size="12" /> {{ errors.subjects }}
        </span>
        <span v-else class="field__hint">{{ t("exam.subjectLockNote") }}</span>
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
