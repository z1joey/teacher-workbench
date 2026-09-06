<script setup>
// 记录 / 编辑事件：类型用中文下拉而不是代码输入框，
// 需要「事由」和「跟进」的类型会自动展开对应字段（防错 + 低记忆负担）。
import { computed, onMounted, ref } from "vue"
import { useRouter } from "vue-router"
import api from "../api"
import Icon from "../components/Icon.vue"
import PageHeader from "../components/PageHeader.vue"
import AsyncState from "../components/AsyncState.vue"
import FormField from "../components/FormField.vue"
import { ask } from "../confirm"
import { notify, runUndoable } from "../feedback"
import { friendlyError, recordableEventOptions, eventTypeLabel, t } from "../strings"

const props = defineProps({
  studentId: { type: String, required: true },
  eventId: { type: [String, null], default: null },
})
const router = useRouter()

const isCreate = computed(() => !props.eventId)

const CUSTOM_VALUE = "__custom__"

const student = ref(null)
const event = ref(null)
const customEventTypes = ref([])
const loading = ref(true)
const saving = ref(false)
const error = ref("")
const notFound = ref(false)

const form = ref(emptyForm())
const errors = ref({})
// 记录家访时到场的监护人（Person），默认全部勾选
const selectedGuardians = ref(new Set())

function toggleGuardian(id) {
  const next = new Set(selectedGuardians.value)
  next.has(id) ? next.delete(id) : next.add(id)
  selectedGuardians.value = next
}

function emptyForm() {
  return {
    event_type: "home_visited",
    custom_type: "",
    summary: "",
    purpose: "",
    follow_up_needed: false,
    follow_up_note: "",
    occurred_at: "",
  }
}

onMounted(async () => {
  loading.value = true
  error.value = ""
  try {
    const tasks = [
      api.get(`/students/${props.studentId}`),
      api.get("/teachers/me/event-types").catch(() => []),
    ]
    if (!isCreate.value) {
      tasks.push(api.get(`/students/${props.studentId}/events/${props.eventId}`))
    }
    const res = await Promise.all(tasks)
    student.value = res[0]
    customEventTypes.value = res[1] || []
    if (isCreate.value) {
      // 家访默认所有登记监护人都到场
      selectedGuardians.value = new Set((student.value.guardians ?? []).map((g) => g.id))
    }
    if (!isCreate.value) {
      const ev = res[2]
      event.value = ev
      const p = ev.payload || {}
      const known = [...PRESET_VALUES, ...customEventTypes.value]
      const isCustom = !known.includes(ev.event_type)
      form.value = {
        event_type: isCustom ? CUSTOM_VALUE : ev.event_type,
        custom_type: isCustom ? ev.event_type : "",
        summary: p.summary || "",
        purpose: p.purpose || "",
        follow_up_needed: !!p.follow_up_needed,
        follow_up_note: p.follow_up_note || "",
        occurred_at: ev.occurred_at ? ev.occurred_at.slice(0, 16) : "",
      }
    }
  } catch (e) {
    if (/not found/i.test(e.message || "")) notFound.value = true
    else error.value = friendlyError(e)
  } finally {
    loading.value = false
  }
})

const presets = recordableEventOptions()
const PRESET_VALUES = presets.map((o) => o.value)

// 新建只开放家访；下拉仅编辑旧记录时出现，用于回显暂时关闭的类型
// （家长沟通/谈心/辅导/教师备注），不再提供「自定义类型」新入口。
const typeOptions = computed(() => {
  if (isCreate.value) return presets
  const extras = customEventTypes.value
    .filter((x) => !PRESET_VALUES.includes(x))
    .map((x) => ({ value: x, label: eventTypeLabel(x) }))
  return [...presets, ...extras, { value: CUSTOM_VALUE, label: "自定义类型" }]
})

// 自定义类型时真正提交给后端的名字
const resolvedType = computed(() =>
  form.value.event_type === CUSTOM_VALUE ? form.value.custom_type.trim() : form.value.event_type
)

// 家访和家长沟通要说清「为什么」；家访常常需要后续跟进
function typeNeedsPurpose(type) {
  return type === "home_visited" || type === "parent_call"
}
function typeNeedsFollowUp(type) {
  return type === "home_visited"
}

function validate() {
  const e = {}
  if (!form.value.summary.trim()) e.summary = t("event.summaryRequired")
  if (!resolvedType.value) e.event_type = "请填写事件类型"
  errors.value = e
  return !Object.keys(e).length
}

async function save() {
  error.value = ""
  if (!validate()) return
  saving.value = true
  try {
    const payload = {
      event_type: resolvedType.value,
      summary: form.value.summary.trim(),
      purpose: form.value.purpose.trim() || null,
      follow_up_needed: form.value.follow_up_needed,
      follow_up_note: form.value.follow_up_note.trim() || null,
    }
    if (form.value.occurred_at) {
      payload.occurred_at = new Date(form.value.occurred_at).toISOString()
    }
    if (isCreate.value) {
      const body = { ...payload, guardian_ids: [...selectedGuardians.value] }
      await api.post(`/students/${props.studentId}/events`, body)
    } else {
      await api.patch(`/students/${props.studentId}/events/${props.eventId}`, payload)
    }
    notify({ tone: "ok", title: isCreate.value ? "已记录" : t("common.saved"), timeout: 2400 })
    router.replace(`/students/${props.studentId}`)
  } catch (e) {
    error.value = friendlyError(e)
  } finally {
    saving.value = false
  }
}

async function remove() {
  const ok = await ask({
    title: `删除这条${eventTypeLabelSafe()}记录？`,
    consequences: [t("event.deleteConfirm")],
    confirmLabel: t("action.delete"),
  })
  if (!ok) return

  const name = student.value?.name || ""
  runUndoable({
    title: `已删除「${name}」的这条记录`,
    run: () => api.delete(`/students/${props.studentId}/events/${props.eventId}`),
    onDone: () => router.replace(`/students/${props.studentId}`),
  })
}

function eventTypeLabelSafe() {
  if (!form.value.event_type) return "事件"
  const found = typeOptions.value.find((o) => o.value === form.value.event_type)
  if (!found) return form.value.event_type
  return found.value === CUSTOM_VALUE ? form.value.custom_type || "自定义事件" : found.label
}

function goBack() {
  router.replace(`/students/${props.studentId}`)
}
</script>

<template>
  <!-- 记录已被别人删掉：给一条明确的出路，而不是空白页 -->
  <div v-if="notFound" class="nf-wrap">
    <div class="nf-board">
      <Icon name="alert" :size="30" />
      <p class="nf-title">{{ t("nf.eventGone") }}</p>
      <p class="nf-sub">{{ t("nf.eventGoneSub") }}</p>
    </div>
    <div class="nf-actions">
      <router-link :to="`/students/${props.studentId}`">
        <button class="btn btn--primary">{{ t("nf.backTimeline") }}</button>
      </router-link>
    </div>
  </div>

  <template v-else>
    <PageHeader
      :title="isCreate ? '记录家访' : `编辑${eventTypeLabelSafe()}`"
      :subtitle="student ? student.name : ''"
    />

    <AsyncState :loading="loading" :error="error" :rows="4" @retry="router.go(0)">
      <div class="card" style="max-width: 620px">
        <form class="card__body" @submit.prevent="save" novalidate>
          <!-- 新建固定为家访，不再选类型；类型下拉只在编辑历史记录时出现 -->
          <FormField
            v-if="!isCreate"
            :label="t('event.type')"
            :error="errors.event_type || ''"
          >
            <select
              v-model="form.event_type"
              class="select"
              :aria-invalid="!!errors.event_type"
            >
              <option v-for="o in typeOptions" :key="o.value" :value="o.value">{{ o.label }}</option>
            </select>
          </FormField>

          <FormField
            v-if="!isCreate && form.event_type === '__custom__'"
            label="自定义类型名称"
            required
          >
            <input v-model="form.custom_type" class="input" type="text" maxlength="20" />
          </FormField>

          <FormField
            v-if="typeNeedsPurpose(form.event_type)"
            :label="t('event.purpose')"
            optional
            :hint="t('event.purposeHint')"
          >
            <input v-model="form.purpose" class="input" type="text" />
          </FormField>

          <!-- 记录家访时勾选到场的监护人：他们和学生会一起成为事件参与者 -->
          <FormField
            v-if="isCreate && student?.guardians?.length"
            label="到场的监护人"
            optional
            hint="默认全部到场，没来的可以取消勾选；监护人会和这次家访关联起来"
          >
            <div class="row-wrap">
              <label v-for="g in student.guardians" :key="g.id" class="check">
                <input
                  type="checkbox"
                  :checked="selectedGuardians.has(g.id)"
                  @change="toggleGuardian(g.id)"
                />
                <span>
                  {{ g.name }}{{ g.relationship ? `（${g.relationship}）` : ""
                  }}<template v-if="g.phone"> · {{ g.phone }}</template>
                </span>
              </label>
            </div>
          </FormField>

          <FormField :label="t('event.summary')" required :error="errors.summary || ''">
            <textarea
              v-model="form.summary"
              class="textarea"
              rows="4"
              :aria-invalid="!!errors.summary"
            />
          </FormField>

          <template v-if="typeNeedsFollowUp(form.event_type)">
            <div class="field">
              <label class="check">
                <input v-model="form.follow_up_needed" type="checkbox" />
                <span>{{ t("event.followUp") }}</span>
              </label>
              <span class="field__hint">{{ t("event.followUpHint") }}</span>
            </div>
            <FormField
              v-if="form.follow_up_needed"
              :label="t('event.followUpNote')"
              optional
            >
              <input v-model="form.follow_up_note" class="input" type="text" />
            </FormField>
          </template>

          <FormField :label="t('event.occurredAt')" optional :hint="t('event.occurredAtHint')">
            <input v-model="form.occurred_at" class="input" type="datetime-local" />
          </FormField>

          <p v-if="error" class="field__error" style="margin-bottom: 12px">
            <Icon name="alert-circle" :size="13" /> {{ error }}
          </p>

          <div class="form-actions">
            <button type="submit" class="btn btn--primary" :disabled="saving">
              <span v-if="saving" class="spinner" />
              {{ saving ? t("event.saving") : t("event.save") }}
            </button>
            <button type="button" class="btn btn--ghost" @click="goBack">{{ t("action.cancel") }}</button>

            <span class="form-actions__spacer" />
            <button
              v-if="!isCreate"
              type="button"
              class="btn btn--danger"
              :disabled="saving"
              @click="remove"
            >
              <Icon name="trash" :size="14" /> {{ t("action.delete") }}
            </button>
          </div>
        </form>
      </div>
    </AsyncState>
  </template>
</template>
