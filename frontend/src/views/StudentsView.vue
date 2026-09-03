<script setup>
import { ref, computed, onMounted } from "vue"
import { useRouter } from "vue-router"
import Icon from "../components/Icon.vue"
import api from "../api"
import { searchQuery, searchStudents } from "../search"
import { genderLabel, statusLabel, t } from "../strings"

const router = useRouter()
const students = ref([])
const query = searchQuery // global — the nav search box filters this list
const loading = ref(true)
const error = ref("")
const collapsed = ref({})

onMounted(async () => {
  try {
    students.value = await api.get("/students")
    searchStudents.value = students.value // keep the nav dropdown in sync
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

// First-appearance order (admission_no order); students without a class go last.
const groups = computed(() => {
  const byName = new Map()
  for (const s of filtered.value) {
    const name = s.class ? s.class.name : t("students.ungrouped")
    if (!byName.has(name)) byName.set(name, [])
    byName.get(name).push(s)
  }
  const ungrouped = t("students.ungrouped")
  return [...byName.entries()]
    .sort(([a], [b]) => (a === ungrouped) - (b === ungrouped))
    .map(([name, list]) => ({ name, list }))
})

const searching = computed(() => query.value.trim().length > 0)

// While searching, always expand so matches are never hidden inside a collapsed group.
function isCollapsed(group) {
  return !searching.value && !!collapsed.value[group.name]
}

function toggleGroup(group) {
  collapsed.value[group.name] = !collapsed.value[group.name]
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

  <p v-if="error" class="error-text">{{ error }}</p>
  <p v-else-if="loading" class="empty">{{ t("common.loading") }}</p>
  <p v-else-if="!filtered.length" class="empty">{{ t("common.noMatch") }}</p>

  <div v-for="g in groups" :key="g.name" class="card group-card">
    <button
      :id="`group-head-${g.name}`"
      class="group-head"
      type="button"
      :aria-expanded="!isCollapsed(g)"
      :aria-controls="`group-body-${g.name}`"
      @click="toggleGroup(g)"
    >
      <strong>{{ g.name }}</strong>
      <span class="badge muted">{{ g.list.length }}</span>
      <Icon class="chev" :class="{ open: !isCollapsed(g) }" name="chevron-down" :size="15" />
    </button>
    <div v-show="!isCollapsed(g)" :id="`group-body-${g.name}`" role="region" :aria-labelledby="`group-head-${g.name}`">
      <table>
        <thead>
          <tr>
            <th>{{ t("th.admissionNo") }}</th>
            <th>{{ t("th.name") }}</th>
            <th>{{ t("th.gender") }}</th>
            <th>{{ t("th.status") }}</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="s in g.list"
            :key="s.id"
            class="clickable"
            @click="router.push(`/students/${s.id}`)"
          >
            <td>{{ s.admission_no }}</td>
            <td><strong>{{ s.name }}</strong></td>
            <td>{{ genderLabel(s.gender) }}</td>
            <td><span class="badge" :class="s.status === 'active' ? 'ok' : 'muted'">{{ statusLabel(s.status) }}</span></td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
