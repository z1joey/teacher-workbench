<script setup>
import { ref, onMounted } from "vue"
import { useRouter } from "vue-router"
import Icon from "../components/Icon.vue"
import api from "../api"
import { genderLabel, t } from "../strings"

const router = useRouter()

const classes = ref([])
const teachers = ref([])
const loading = ref(true)
const error = ref("")

const showCreate = ref(false)
const creating = ref(false)
const createError = ref("")
const createForm = ref(emptyForm())

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
        <router-link :to="`/classes/${c.id}`" style="text-decoration: none; color: inherit; display: block">
          <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 8px">
            <div>
              <h2 style="margin-bottom: 2px">{{ className(c) }}</h2>
              <span class="weakness-sub">
                {{ c.academic_year }} · {{ t("classes.homeroom") }}: {{ c.homeroom_teacher || "—" }} ·
                {{ t("profile.studentsCount", { n: c.student_count }) }}
              </span>
            </div>
            <button class="small icon-btn" title="查看 / 编辑 / 删除">…</button>
          </div>
          <div v-if="c.students.length" class="student-chips">
            <span
              v-for="s in c.students"
              :key="s.id"
              class="student-chip"
              :title="s.admission_no"
              @click.stop="(e) => { e.preventDefault(); e.stopPropagation(); router.push('/students/' + s.id) }"
            >
              {{ s.name }} <span class="weakness-sub">{{ genderLabel(s.gender) }}</span>
            </span>
          </div>
          <p v-else class="empty">{{ t("classes.noStudents") }}</p>
        </router-link>
      </div>
    </div>
  </template>
</template>
