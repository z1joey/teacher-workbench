<script setup>
import { ref, computed, onMounted } from "vue"
import { useRouter } from "vue-router"
import api from "../api"
import Icon from "../components/Icon.vue"
import { eventTypeLabel, t } from "../strings"

const props = defineProps({
  studentId: { type: String, required: true },
  eventId: { type: [String, null], default: null },
})
const router = useRouter()

const isCreate = computed(() => !props.eventId)

const student = ref(null)
const event = ref(null)
const customEventTypes = ref([])
const loading = ref(true)
const saving = ref(false)
const error = ref("")

const EVENT_TYPE_OPTIONS = [
  { value: "home_visited", label: "家访" },
  { value: "parent_call", label: "家长沟通" },
  { value: "talk", label: "谈心" },
  { value: "tutoring", label: "辅导" },
  { value: "note_added", label: "随笔" },
]

const form = ref(emptyForm())

function emptyForm() {
  return { event_type: "home_visited", summary: "", purpose: "", follow_up_needed: false, follow_up_note: "", occurred_at: "" }
}

onMounted(async () => {
  loading.value = true
  error.value = ""
  try {
    const tasks = [
      api.get(`/students/${props.studentId}`),
      api.get(`/teachers/me/event-types`).catch(() => []),
    ]
    if (!isCreate.value) {
      tasks.push(api.get(`/students/${props.studentId}/events/${props.eventId}`))
    }
    const res = await Promise.all(tasks)
    student.value = res[0]
    customEventTypes.value = res[1] || []
    if (!isCreate.value) {
      const ev = res[2]
      event.value = ev
      const p = ev.payload || {}
      form.value = {
        event_type: ev.event_type,
        summary: p.summary || "",
        purpose: p.purpose || "",
        follow_up_needed: !!p.follow_up_needed,
        follow_up_note: p.follow_up_note || "",
        occurred_at: ev.occurred_at ? ev.occurred_at.slice(0, 16) : "",
      }
    }
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
})

const typeOptions = computed(() => {
  const presets = EVENT_TYPE_OPTIONS
  const seen = new Set(presets.map((o) => o.value))
  const extras = customEventTypes.value
    .filter((t) => !seen.has(t))
    .map((t) => ({ value: t, label: t }))
  return [...presets, ...extras]
})

function typeNeedsPurpose(type) {
  return type === "home_visited" || type === "parent_call"
}
function typeNeedsFollowUp(type) {
  return type === "home_visited"
}

async function save() {
  error.value = ""
  if (!form.value.summary.trim()) {
    error.value = t("event.summaryRequired")
    return
  }
  saving.value = true
  try {
    const payload = {
      event_type: form.value.event_type,
      summary: form.value.summary.trim(),
      purpose: form.value.purpose.trim() || null,
      follow_up_needed: form.value.follow_up_needed,
      follow_up_note: form.value.follow_up_note.trim() || null,
    }
    if (form.value.occurred_at) {
      payload.occurred_at = new Date(form.value.occurred_at).toISOString()
    }
    if (isCreate.value) {
      await api.post(`/students/${props.studentId}/events`, payload)
    } else {
      await api.patch(`/students/${props.studentId}/events/${props.eventId}`, payload)
    }
    router.replace(`/students/${props.studentId}`)
  } catch (e) {
    error.value = e.message
  } finally {
    saving.value = false
  }
}

async function remove() {
  if (!window.confirm(t("action.deleteConfirm"))) return
  try {
    await api.delete(`/students/${props.studentId}/events/${props.eventId}`)
    router.replace(`/students/${props.studentId}`)
  } catch (e) {
    alert(`删除失败：${e.message}`)
  }
}

function goBack() {
  router.replace(`/students/${props.studentId}`)
}
</script>

<template>
  <p v-if="error" class="error-text">{{ error }}</p>
  <p v-else-if="loading" class="empty">{{ t("common.loading") }}</p>

  <template v-else-if="student">
    <router-link :to="`/students/${props.studentId}`" class="back-link">
      <Icon name="chevron-left" :size="14" /> 返回 {{ student.name }}
    </router-link>

    <div class="card" style="margin-top: 12px">
      <div style="display: flex; justify-content: space-between; align-items: center">
        <h1 style="margin: 0">
          {{ isCreate ? "记录事件" : eventTypeLabel(event.event_type) }}
          <span class="page-sub" style="margin-left: 6px; font-weight: normal">· {{ student.name }}</span>
        </h1>
        <button v-if="!isCreate" class="small logout-btn" @click="remove">{{ t("action.delete") }}</button>
      </div>

      <div style="margin-top: 16px">
        <div class="field">
          <label>{{ t("event.type") }} *</label>
          <input list="custom-event-types" v-model="form.event_type" class="datalist-input" />
          <datalist id="custom-event-types">
            <option v-for="o in typeOptions" :key="o.value" :value="o.value">{{ o.label }}</option>
          </datalist>
          <span class="page-sub">可以从下拉选择，也可以直接输入自定义名称（如"考前谈心"、"作业抽查"）。</span>
        </div>

        <div v-if="typeNeedsPurpose(form.event_type)" class="field">
          <label>{{ t("event.purpose") }}</label>
          <input v-model="form.purpose" type="text" />
        </div>

        <div class="field">
          <label>{{ t("event.summary") }} *</label>
          <textarea v-model="form.summary" rows="4"></textarea>
        </div>

        <div v-if="typeNeedsFollowUp(form.event_type)" class="field checkbox-row">
          <input id="fu" v-model="form.follow_up_needed" type="checkbox" />
          <label for="fu">{{ t("event.followUp") }}</label>
        </div>
        <div v-if="typeNeedsFollowUp(form.event_type) && form.follow_up_needed" class="field">
          <label>{{ t("event.followUpNote") }}</label>
          <input v-model="form.follow_up_note" type="text" />
        </div>

        <div class="field">
          <label>事件时间</label>
          <input v-model="form.occurred_at" type="datetime-local" />
          <span class="page-sub">留空则使用当前时间。</span>
        </div>

        <p v-if="error" class="error-text">{{ error }}</p>
        <div style="display: flex; gap: 8px; margin-top: 8px">
          <button class="primary" :disabled="saving" @click="save">
            {{ saving ? t("event.saving") : t("event.save") }}
          </button>
          <button class="small" @click="goBack">{{ t("action.cancel") }}</button>
        </div>
      </div>
    </div>
  </template>
</template>
