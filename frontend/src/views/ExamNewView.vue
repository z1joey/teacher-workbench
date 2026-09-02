<script setup>
import { ref, computed } from "vue"
import { useRouter } from "vue-router"
import api from "../api"
import { subject, t } from "../strings"

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

const selectedSubjects = computed(() =>
  SUBJECT_OPTIONS.filter((s) => form.value.selected[s])
)

async function submit() {
  error.value = ""
  if (!selectedSubjects.value.length) {
    error.value = t("examnew.subjectsRequired")
    return
  }
  const year = Number((form.value.exam_date || "").slice(0, 4))
  if (!form.value.exam_date || year < 2000 || year > 2100) {
    error.value = t("examnew.dateInvalid")
    return
  }
  busy.value = true
  try {
    const res = await api.post("/exams", {
      name: form.value.name,
      exam_date: form.value.exam_date,
      subjects: selectedSubjects.value.map((s) => ({
        subject: s,
        full_score: Number(form.value.full_score),
      })),
    })
    router.push(`/exams/${res.id}`)
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <router-link to="/exams" style="font-size: 13px">← {{ t("nav.exams") }}</router-link>

  <h1 style="margin-top: 12px">{{ t("examnew.title") }}</h1>
  <p class="page-sub">{{ t("examnew.subtitle") }}</p>

  <div class="card" style="max-width: 560px">
    <form @submit.prevent="submit">
      <div class="field">
        <label>{{ t("examnew.name") }} *</label>
        <input v-model="form.name" type="text" required />
      </div>
      <div class="field" style="max-width: 260px">
        <label>{{ t("examnew.date") }} *</label>
        <input v-model="form.exam_date" type="date" required />
      </div>

      <h2>{{ t("examnew.subjects") }}</h2>
      <div class="subject-grid">
        <label v-for="s in SUBJECT_OPTIONS" :key="s" class="checkbox-row subject-option">
          <input v-model="form.selected[s]" type="checkbox" />
          <span>{{ subject(s) }}</span>
        </label>
      </div>
      <div class="field" style="max-width: 200px">
        <label>{{ t("examnew.fullScore") }}</label>
        <input v-model="form.full_score" type="number" min="1" max="1000" step="1" />
      </div>

      <p v-if="error" class="error-text">{{ error }}</p>
      <button type="submit" class="primary" style="margin-top: 6px" :disabled="busy">
        {{ busy ? t("examnew.saving") : t("examnew.submit") }}
      </button>
    </form>
  </div>
</template>
