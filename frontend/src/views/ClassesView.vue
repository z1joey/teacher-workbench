<script setup>
import { ref, onMounted } from "vue"
import Icon from "../components/Icon.vue"
import api from "../api"
import { genderLabel, t } from "../strings"

const classes = ref([])
const teachers = ref([])
const loading = ref(true)
const error = ref("")

const showCreate = ref(false)
const creating = ref(false)
const createError = ref("")
const createForm = ref(emptyForm())

const editingId = ref(null)
const editForm = ref(emptyForm())
const editError = ref("")

function emptyForm() {
  return { name: "", grade_level: 7, academic_year: defaultYear(), homeroom_teacher_id: null }
}

function defaultYear() {
  const now = new Date()
  const start = now.getMonth() + 1 >= 8 ? now.getFullYear() : now.getFullYear() - 1
  return `${start}/${start + 1}`
}

onMounted(async () => {
  try {
    const [cs, ts] = await Promise.all([api.get("/classes"), api.get("/teachers")])
    classes.value = cs
    teachers.value = ts
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
})

async function load() {
  classes.value = await api.get("/classes")
}

function toBody(f) {
  return {
    name: (f.name || "").trim(),
    grade_level: Number(f.grade_level),
    academic_year: (f.academic_year || "").trim(),
    homeroom_teacher_id: f.homeroom_teacher_id || null,
  }
}

async function createClass() {
  createError.value = ""
  if (!(createForm.value.name || "").trim()) {
    createError.value = t("classes.nameRequired")
    return
  }
  creating.value = true
  try {
    await api.post("/classes", toBody(createForm.value))
    createForm.value = emptyForm()
    showCreate.value = false
    await load()
  } catch (e) {
    createError.value = e.message
  } finally {
    creating.value = false
  }
}

function startEdit(c) {
  editingId.value = c.id
  editError.value = ""
  editForm.value = {
    name: c.name || "",
    grade_level: c.grade_level,
    academic_year: c.academic_year,
    homeroom_teacher_id: c.homeroom_teacher_id,
  }
}

async function saveEdit(c) {
  editError.value = ""
  if (!(editForm.value.name || "").trim()) {
    editError.value = t("classes.nameRequired")
    return
  }
  try {
    await api.patch(`/classes/${c.id}`, toBody(editForm.value))
    editingId.value = null
    await load()
  } catch (e) {
    editError.value = e.message
  }
}

async function removeClass(c) {
  if (!window.confirm(t("classes.deleteConfirm"))) return
  try {
    await api.delete(`/classes/${c.id}`)
    await load()
  } catch (e) {
    error.value = e.message
    setTimeout(() => (error.value = ""), 4000)
  }
}

function className(c) {
  return c.name
}
</script>

<template>
  <div style="display: flex; justify-content: space-between; align-items: center; gap: 12px">
    <div>
      <h1>{{ t("classes.title") }}</h1>
      <p class="page-sub">{{ t("classes.subtitle") }}</p>
    </div>
    <button class="primary" @click="showCreate = !showCreate">
      <Icon v-if="!showCreate" name="plus" :size="15" />
      {{ showCreate ? t("action.cancel") : t("classes.create") }}
    </button>
  </div>

  <p v-if="error" class="error-text">{{ error }}</p>
  <p v-else-if="loading" class="empty">{{ t("common.loading") }}</p>

  <template v-else>
    <!-- create form -->
    <div v-if="showCreate" class="card" style="max-width: 560px">
      <h2>{{ t("classes.create") }}</h2>
      <div style="display: flex; gap: 12px">
        <div class="field" style="flex: 1">
          <label>{{ t("classes.name") }} *</label>
          <input v-model="createForm.name" type="text" :placeholder="t('classes.name')" />
        </div>
        <div class="field" style="flex: 1">
          <label>{{ t("classes.grade") }}</label>
          <input v-model="createForm.grade_level" type="number" min="1" max="12" />
        </div>
      </div>
      <div style="display: flex; gap: 12px">
        <div class="field" style="flex: 1">
          <label>{{ t("classes.year") }}</label>
          <input v-model="createForm.academic_year" type="text" />
        </div>
        <div class="field" style="flex: 1">
          <label>{{ t("classes.homeroom") }}</label>
          <select v-model="createForm.homeroom_teacher_id">
            <option :value="null">{{ t("common.none") }}</option>
            <option v-for="teacher in teachers" :key="teacher.id" :value="teacher.id">
              {{ teacher.name }}
            </option>
          </select>
        </div>
      </div>
      <p v-if="createError" class="error-text">{{ createError }}</p>
      <button class="primary" :disabled="creating" @click="createClass">
        {{ creating ? t("classes.creating") : t("classes.create") }}
      </button>
    </div>

    <!-- class cards -->
    <div class="class-grid">
      <div v-for="c in classes" :key="c.id" class="card class-card">
        <template v-if="editingId !== c.id">
          <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 8px">
            <div>
              <h2 style="margin-bottom: 2px">{{ className(c) }}</h2>
              <span class="weakness-sub">
                {{ c.academic_year }} · {{ t("classes.homeroom") }}: {{ c.homeroom_teacher || "—" }} ·
                {{ t("profile.studentsCount", { n: c.student_count }) }}
              </span>
            </div>
            <div class="class-actions">
              <router-link :to="`/classes/${c.id}`">
                <button class="small primary">{{ t("classes.viewDetail") }}</button>
              </router-link>
              <button class="small" @click="startEdit(c)">{{ t("action.edit") }}</button>
              <button class="small logout-btn" @click="removeClass(c)">{{ t("classes.delete") }}</button>
            </div>
          </div>
          <div v-if="c.students.length" class="student-chips">
            <router-link
              v-for="s in c.students"
              :key="s.id"
              :to="`/students/${s.id}`"
              class="student-chip"
              :title="s.admission_no"
            >
              {{ s.name }} <span class="weakness-sub">{{ genderLabel(s.gender) }}</span>
            </router-link>
          </div>
          <p v-else class="empty">{{ t("classes.noStudents") }}</p>
        </template>

        <!-- inline edit -->
        <template v-else>
          <h2 style="margin-bottom: 10px">{{ t("action.edit") }}</h2>
          <div style="display: flex; gap: 12px">
            <div class="field" style="flex: 1">
              <label>{{ t("classes.name") }} *</label>
              <input v-model="editForm.name" type="text" />
            </div>
            <div class="field" style="flex: 1">
              <label>{{ t("classes.grade") }}</label>
              <input v-model="editForm.grade_level" type="number" min="1" max="12" />
            </div>
          </div>
          <div style="display: flex; gap: 12px">
            <div class="field" style="flex: 1">
              <label>{{ t("classes.year") }}</label>
              <input v-model="editForm.academic_year" type="text" />
            </div>
            <div class="field" style="flex: 1">
              <label>{{ t("classes.homeroom") }}</label>
              <select v-model="editForm.homeroom_teacher_id">
                <option :value="null">{{ t("common.none") }}</option>
                <option v-for="teacher in teachers" :key="teacher.id" :value="teacher.id">
                  {{ teacher.name }}
                </option>
              </select>
            </div>
          </div>
          <p v-if="editError" class="error-text">{{ editError }}</p>
          <button class="primary small" @click="saveEdit(c)">{{ t("action.save") }}</button>
          <button class="small" style="margin-left: 8px" @click="editingId = null">
            {{ t("action.cancel") }}
          </button>
        </template>
      </div>
    </div>
  </template>
</template>
