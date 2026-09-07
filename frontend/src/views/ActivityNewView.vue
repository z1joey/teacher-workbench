<script setup>
// 新建普通事件：比赛、活动等。学生可选参与名单 —— 事件会同时关联老师和学生，
// 出现在双方的时间线里。
import { computed, onMounted, ref } from "vue"
import { useRouter } from "vue-router"
import Icon from "../components/Icon.vue"
import PageHeader from "../components/PageHeader.vue"
import FormField from "../components/FormField.vue"
import api from "../api"
import { friendlyError, t, todayStr } from "../strings"

const router = useRouter()

// 传入 eventId 即编辑模式：预填表单，提交走 PATCH
const props = defineProps({
  eventId: { type: String, default: null },
})
const isEdit = computed(() => !!props.eventId)

// 本地时区的今天；toISOString 会用 UTC，凌晨 0-8 点会错成昨天
const today = todayStr()
const form = ref({
  title: "",
  date: today,
  notes: "",
})
const students = ref([])
const selected = ref(new Set())
const query = ref("")
const studentListOpen = ref(false) // 点「指定学生」才展开学生列表
const loading = ref(true)
const busy = ref(false)
const error = ref("")
const errors = ref({})

onMounted(async () => {
  try {
    const rows = await api.get("/students")
    students.value = rows.filter((s) => s.status === "active")
    if (props.eventId) {
      const ev = await api.get(`/events/${props.eventId}`)
      form.value = {
        title: ev.title,
        date: ev.occurred_at.slice(0, 10),
        notes: ev.notes || "",
      }
      selected.value = new Set(ev.students.map((s) => s.id))
      studentListOpen.value = true
    }
  } catch (e) {
    error.value = friendlyError(e)
  } finally {
    loading.value = false
  }
})

const filtered = computed(() => {
  const q = query.value.trim().toLowerCase()
  if (!q) return students.value
  return students.value.filter(
    (s) => s.name.toLowerCase().includes(q) || s.admission_no.toLowerCase().includes(q),
  )
})

// 按班级分组：点班级 = 整班参加（全选/再次点击取消全班）
const classGroups = computed(() => {
  const map = new Map()
  for (const s of students.value) {
    const key = s.class?.id ?? "__none__"
    if (!map.has(key)) {
      map.set(key, { key, name: s.class?.name ?? t("students.ungrouped"), list: [] })
    }
    map.get(key).list.push(s)
  }
  return [...map.values()]
})

function classSelectedCount(c) {
  return c.list.reduce((n, s) => n + (selected.value.has(s.id) ? 1 : 0), 0)
}

function toggleClass(c) {
  const ids = c.list.map((s) => s.id)
  const allIn = ids.every((id) => selected.value.has(id))
  const next = new Set(selected.value)
  ids.forEach((id) => (allIn ? next.delete(id) : next.add(id)))
  selected.value = next
}

function toggle(id) {
  const next = new Set(selected.value)
  next.has(id) ? next.delete(id) : next.add(id)
  selected.value = next
}

function validate() {
  const e = {}
  if (!form.value.title.trim()) e.title = t("eventNew.titleRequired")
  errors.value = e
  return !Object.keys(e).length
}

async function submit() {
  error.value = ""
  if (!validate()) return
  busy.value = true
  try {
    const body = {
      title: form.value.title.trim(),
      occurred_at: form.value.date ? `${form.value.date}T09:00:00` : null,
      notes: form.value.notes.trim() || null,
      student_ids: [...selected.value],
    }
    if (isEdit.value) {
      await api.patch(`/events/${props.eventId}`, body)
      router.push(`/events/${props.eventId}`)
    } else {
      await api.post("/events", body)
      router.push("/events")
    }
  } catch (e) {
    error.value = friendlyError(e)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <PageHeader
    :title="isEdit ? '编辑事件' : t('eventNew.title')"
    :subtitle="t('eventNew.subtitle')"
  />

  <div class="card">
    <div class="card__body">
      <form @submit.prevent="submit">
        <FormField
          :label="t('eventNew.nameLabel')"
          required
          :error="errors.title || ''"
          :hint="t('eventNew.nameHint')"
        >
          <input
            v-model="form.title"
            class="input"
            type="text"
            maxlength="100"
            :placeholder="t('eventNew.namePlaceholder')"
            :aria-invalid="!!errors.title"
          />
        </FormField>

        <div class="form-grid">
          <FormField :label="t('eventNew.dateLabel')" optional>
            <input v-model="form.date" class="input" type="date" />
          </FormField>
        </div>

        <FormField :label="t('eventNew.notesLabel')" optional>
          <textarea v-model="form.notes" class="input" rows="3" maxlength="2000" />
        </FormField>

        <FormField :label="t('eventNew.studentsLabel')" optional :hint="t('eventNew.studentsHint')">
          <div>
            <div v-if="classGroups.length > 1" class="row-wrap" style="margin-bottom: 10px">
              <button
                v-for="c in classGroups"
                :key="c.key"
                type="button"
                class="chip"
                :style="
                  classSelectedCount(c) === c.list.length && c.list.length
                    ? { background: '#2e6ba8', borderColor: '#2e6ba8', color: '#fff' }
                    : {}
                "
                :title="t('eventNew.classChipTitle')"
                @click="toggleClass(c)"
              >
                {{ c.name }} {{ classSelectedCount(c) }}/{{ c.list.length }}
              </button>
              <button
                type="button"
                class="chip"
                :style="
                  studentListOpen
                    ? { background: '#2e6ba8', borderColor: '#2e6ba8', color: '#fff' }
                    : {}
                "
                @click="studentListOpen = !studentListOpen"
              >
                {{ studentListOpen ? t("eventNew.hideStudentList") : t("eventNew.specifyStudents") }}
              </button>
            </div>
            <template v-if="studentListOpen">
              <input
                v-model="query"
                class="input"
                type="search"
                :placeholder="t('eventNew.searchPlaceholder')"
                style="margin-bottom: 10px"
              />
              <div v-if="!loading" class="card card--link" style="max-height: 260px; overflow-y: auto">
                <div class="card__body card__body--tight">
                  <label
                    v-for="s in filtered"
                    :key="s.id"
                    class="feed__item"
                    style="cursor: pointer; align-items: center"
                  >
                    <input
                      type="checkbox"
                      :checked="selected.has(s.id)"
                      @change="toggle(s.id)"
                    />
                    <span style="margin-left: 8px">
                      {{ s.name }}
                      <span class="muted tnum" style="margin-left: 6px">{{ s.admission_no }}</span>
                      <span v-if="s.class" class="muted" style="margin-left: 6px">{{ s.class.name }}</span>
                    </span>
                  </label>
                  <p v-if="!filtered.length" class="feed__desc" style="padding: 8px">
                    {{ t("eventNew.noStudentMatch") }}
                  </p>
                </div>
              </div>
            </template>
            <p class="field__hint">
              {{ t("eventNew.selectedCount", { n: selected.size }) }}
            </p>
          </div>
        </FormField>

        <p v-if="error" class="field__error" style="margin-bottom: 12px">
          <Icon name="alert-circle" :size="13" /> {{ error }}
        </p>

        <div class="form-actions">
          <button type="submit" class="btn btn--primary" :disabled="busy">
            <span v-if="busy" class="spinner" />
            {{ busy ? t("eventNew.saving") : isEdit ? t("action.save") : t("eventNew.submit") }}
          </button>
          <router-link :to="isEdit ? `/events/${props.eventId}` : '/events'" class="btn btn--ghost">
            {{ t("action.cancel") }}
          </router-link>
        </div>
      </form>
    </div>
  </div>
</template>
