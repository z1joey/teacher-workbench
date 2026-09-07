<script setup>
// 记录 / 编辑事件：新建固定为家访；编辑时类型不可改，只编辑内容。
import { computed, onMounted, ref } from "vue"
import { useRouter } from "vue-router"
import api from "../api"
import Icon from "../components/Icon.vue"
import PageHeader from "../components/PageHeader.vue"
import AsyncState from "../components/AsyncState.vue"
import FormField from "../components/FormField.vue"
import { ask } from "../confirm"
import { notify, runUndoable } from "../feedback"
import { describeEvent, friendlyError, eventTypeLabel, t } from "../strings"

const props = defineProps({
  studentId: { type: String, required: true },
  eventId: { type: [String, null], default: null },
})
const router = useRouter()

const isCreate = computed(() => !props.eventId)
const isSystemEdit = computed(() => !isCreate.value && event.value?.is_system === true)

const student = ref(null)
const event = ref(null)
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
    summary: "",
    purpose: "",
    done: false,
    occurred_at: "",
  }
}

onMounted(async () => {
  loading.value = true
  error.value = ""
  try {
    const tasks = [api.get(`/students/${props.studentId}`)]
    if (!isCreate.value) {
      tasks.push(api.get(`/students/${props.studentId}/events/${props.eventId}`))
    }
    const res = await Promise.all(tasks)
    student.value = res[0]
    if (isCreate.value) {
      // 家访默认所有登记监护人都到场
      selectedGuardians.value = new Set((student.value.guardians ?? []).map((g) => g.id))
    }
    if (!isCreate.value) {
      const ev = res[1]
      if (ev.event_type === "comment") {
        router.replace(`/comments/${props.eventId}`)
        return
      }
      event.value = ev
      const p = ev.payload || {}
      form.value = {
        event_type: ev.event_type,
        summary:
          p.notes ||
          p.summary ||
          (ev.is_system ? describeEvent(ev.event_type, p) : ""),
        purpose: p.purpose || "",
        done: !!p.done,
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

// 编辑时类型固定，不可改；新建固定为家访
const effectiveEventType = computed(() =>
  isCreate.value ? form.value.event_type : (event.value?.event_type ?? form.value.event_type),
)

// 自定义类型时真正提交给后端的名字（仅新建）
const resolvedType = computed(() => form.value.event_type)

// 家访和家长沟通要说清「为什么」
function typeNeedsPurpose(type) {
  return type === "home_visited" || type === "parent_call"
}

const isHomeVisit = computed(
  () => effectiveEventType.value === "home_visited",
)

function validate() {
  const e = {}
  if (!isSystemEdit.value && !isHomeVisit.value && !form.value.summary.trim()) {
    e.summary = t("event.summaryRequired")
  }
  errors.value = e
  return !Object.keys(e).length
}

async function save() {
  error.value = ""
  if (!validate()) return
  saving.value = true
  try {
    const payload = {
      event_type: isCreate.value ? resolvedType.value : event.value.event_type,
      summary: form.value.summary.trim(),
      purpose: form.value.purpose.trim() || null,
    }
    if (isHomeVisit.value) payload.done = form.value.done
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
  const type = effectiveEventType.value
  return type ? eventTypeLabel(type, event.value?.payload) : ""
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
      :title="isCreate ? '记录家访' : eventTypeLabelSafe()"
      :subtitle="student ? student.name : ''"
    />

    <AsyncState :loading="loading" :error="error" :rows="4" @retry="router.go(0)">
      <div class="card" style="max-width: 620px">
        <form class="card__body" @submit.prevent="save" novalidate>
          <FormField
            v-if="typeNeedsPurpose(effectiveEventType)"
            :label="isHomeVisit ? t('event.homeVisitPurpose') : t('event.purpose')"
            :optional="true"
            :hint="t('event.purposeHint')"
            :error="errors.purpose || ''"
          >
            <input
              v-model="form.purpose"
              class="input"
              type="text"
              :placeholder="isHomeVisit ? t('event.defaultPurpose') : undefined"
              :aria-invalid="!!errors.purpose"
            />
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

          <FormField
            :label="isSystemEdit ? t('event.description') : t('event.summary')"
            :required="!isSystemEdit && !isHomeVisit"
            :optional="isSystemEdit || isHomeVisit"
            :error="errors.summary || ''"
          >
            <textarea
              v-model="form.summary"
              class="textarea"
              rows="4"
              :aria-invalid="!!errors.summary"
            />
          </FormField>

          <div v-if="isHomeVisit" class="field">
            <label class="check">
              <input v-model="form.done" type="checkbox" />
              <span>{{ t("event.homeVisitDone") }}</span>
            </label>
            <span class="field__hint">{{ t("event.homeVisitDoneHint") }}</span>
          </div>

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
              v-if="!isCreate && !isSystemEdit"
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
