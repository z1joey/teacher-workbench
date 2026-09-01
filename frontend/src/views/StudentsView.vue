<script setup>
import { ref, computed, onMounted } from "vue"
import { useRouter } from "vue-router"
import Icon from "../components/Icon.vue"
import api from "../api"
import { genderLabel, statusLabel, t } from "../strings"

const router = useRouter()
const students = ref([])
const query = ref("")
const loading = ref(true)
const error = ref("")

onMounted(async () => {
  try {
    students.value = await api.get("/students")
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
})

const filtered = computed(() => {
  const q = query.value.trim().toLowerCase()
  if (!q) return students.value
  return students.value.filter(
    (s) =>
      s.name.toLowerCase().includes(q) ||
      s.admission_no.toLowerCase().includes(q) ||
      (s.class && s.class.name.toLowerCase().includes(q))
  )
})

function className(c) {
  return c ? c.name : "—"
}
</script>

<template>
  <div style="display: flex; justify-content: space-between; align-items: center; gap: 12px">
    <div>
      <h1>{{ t("students.title") }}</h1>
      <p class="page-sub">{{ t("students.subtitle", { count: students.length }) }}</p>
    </div>
    <router-link to="/students/new">
      <button class="primary"><Icon name="plus" :size="15" /> {{ t("students.add") }}</button>
    </router-link>
  </div>

  <div class="card">
    <input
      v-model="query"
      type="text"
      :placeholder="t('students.search')"
      style="max-width: 380px"
    />

    <p v-if="error" class="error-text">{{ error }}</p>
    <p v-else-if="loading" class="empty">{{ t("common.loading") }}</p>
    <p v-else-if="!filtered.length" class="empty">{{ t("common.noMatch") }}</p>

    <table v-else>
      <thead>
        <tr>
          <th>{{ t("th.admissionNo") }}</th>
          <th>{{ t("th.name") }}</th>
          <th>{{ t("th.gender") }}</th>
          <th>{{ t("th.class") }}</th>
          <th>{{ t("th.status") }}</th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="s in filtered"
          :key="s.id"
          class="clickable"
          @click="router.push(`/students/${s.id}`)"
        >
          <td>{{ s.admission_no }}</td>
          <td><strong>{{ s.name }}</strong></td>
          <td>{{ genderLabel(s.gender) }}</td>
          <td><span class="badge">{{ className(s.class) }}</span></td>
          <td><span class="badge ok">{{ statusLabel(s.status) }}</span></td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
