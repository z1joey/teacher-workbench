<script setup>
import { ref, onMounted } from "vue"
import { useRouter } from "vue-router"
import Icon from "../components/Icon.vue"
import api from "../api"
import { t } from "../strings"

const router = useRouter()
const classes = ref([])
const form = ref({
  name: "",
  gender: "",
  birth_date: "",
  guardian_name: "",
  guardian_phone: "",
  address: "",
  class_id: null,
})
const busy = ref(false)
const error = ref("")

onMounted(async () => {
  try {
    classes.value = await api.get("/classes")
  } catch (e) {
    error.value = e.message
  }
})

async function submit() {
  error.value = ""
  if (!form.value.class_id) {
    error.value = t("new.classRequired")
    return
  }
  busy.value = true
  try {
    const body = {
      name: form.value.name,
      gender: form.value.gender || null,
      birth_date: form.value.birth_date || null,
      guardian_name: form.value.guardian_name || null,
      guardian_phone: form.value.guardian_phone,
      address: form.value.address || null,
      class_id: Number(form.value.class_id),
    }
    const res = await api.post("/students", body)
    router.push(`/students/${res.id}`)
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}

function className(c) {
  return c.name
}
</script>

<template>
  <router-link to="/students" class="back-link"><Icon name="chevron-left" :size="14" /> {{ t("nav.students") }}</router-link>

  <h1 style="margin-top: 12px">{{ t("new.title") }}</h1>
  <p class="page-sub">{{ t("new.subtitle") }}</p>

  <div class="card" style="max-width: 560px">
    <form @submit.prevent="submit">
      <h2>{{ t("new.sectionBasic") }}</h2>
      <div class="field">
        <label>{{ t("new.name") }} *</label>
        <input v-model="form.name" type="text" required />
      </div>
      <div style="display: flex; gap: 12px">
        <div class="field" style="flex: 1">
          <label>{{ t("new.gender") }}</label>
          <select v-model="form.gender">
            <option value="">{{ t("common.none") }}</option>
            <option value="F">{{ t("gender.f") }}</option>
            <option value="M">{{ t("gender.m") }}</option>
          </select>
        </div>
        <div class="field" style="flex: 1">
          <label>{{ t("new.birthDate") }}</label>
          <input v-model="form.birth_date" type="date" />
        </div>
      </div>

      <h2 style="margin-top: 8px">{{ t("new.sectionGuardian") }}</h2>
      <div style="display: flex; gap: 12px">
        <div class="field" style="flex: 1">
          <label>{{ t("new.guardianName") }}</label>
          <input v-model="form.guardian_name" type="text" />
        </div>
        <div class="field" style="flex: 1">
          <label>{{ t("new.guardianPhone") }} *</label>
          <input v-model="form.guardian_phone" type="tel" required />
        </div>
      </div>
      <div class="field">
        <label>{{ t("new.address") }}</label>
        <input v-model="form.address" type="text" />
      </div>

      <h2 style="margin-top: 8px">{{ t("new.sectionClass") }}</h2>
      <div class="field">
        <label>{{ t("new.class") }} *</label>
        <select v-model="form.class_id" required>
          <option :value="null" disabled>{{ t("new.classPlaceholder") }}</option>
          <option v-for="c in classes" :key="c.id" :value="c.id">
            {{ className(c) }} · {{ c.academic_year }} ({{ c.student_count }})
          </option>
        </select>
      </div>

      <p v-if="error" class="error-text">{{ error }}</p>
      <button type="submit" class="primary" style="margin-top: 6px" :disabled="busy">
        {{ busy ? t("new.saving") : t("new.submit") }}
      </button>
    </form>
  </div>
</template>
