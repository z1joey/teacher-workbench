<script setup>
// 用户反馈弹窗：选功能模块 + 写具体内容，提交到 /api/feedback
import { computed, nextTick, onMounted, ref } from "vue"
import FormField from "./FormField.vue"
import api from "../api"
import { notify } from "../feedback"
import { friendlyError, t } from "../strings"

const emit = defineEmits(["close"])

const FEATURES = [
  { key: "home", label: "feedback.featureHome" },
  { key: "students", label: "feedback.featureStudents" },
  { key: "classes", label: "feedback.featureClasses" },
  { key: "exams", label: "feedback.featureExams" },
  { key: "visits", label: "feedback.featureVisits" },
  { key: "settings", label: "feedback.featureSettings" },
  { key: "other", label: "feedback.featureOther" },
]

const feature = ref("home")
const content = ref("")
const error = ref("")
const busy = ref(false)
const input = ref(null)

const CONTENT_MAX = 2000
const remaining = computed(() => CONTENT_MAX - content.value.length)

onMounted(async () => {
  await nextTick()
  input.value?.focus()
})

async function submit() {
  if (!content.value.trim()) {
    error.value = t("feedback.required")
    return
  }
  busy.value = true
  error.value = ""
  try {
    await api.post("/feedback", {
      feature: feature.value,
      content: content.value.trim(),
    })
    notify({ tone: "ok", title: t("feedback.sent"), timeout: 2800 })
    emit("close")
  } catch (e) {
    error.value = friendlyError(e)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="overlay" role="dialog" aria-modal="true" aria-labelledby="feedback-title" @click.self="$emit('close')">
    <div class="modal">
      <div class="modal__head">
        <div class="grow">
          <h2 id="feedback-title" class="modal__title">{{ t("feedback.title") }}</h2>
        </div>
        <button class="icon-btn" aria-label="关闭" @click="$emit('close')">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M18 6 6 18M6 6l12 12" /></svg>
        </button>
      </div>

      <div class="modal__body">
        <FormField :label="t('feedback.feature')">
          <select v-model="feature" class="input">
            <option v-for="f in FEATURES" :key="f.key" :value="f.key">
              {{ t(f.label) }}
            </option>
          </select>
        </FormField>
        <FormField :label="t('feedback.content')" :error="error">
          <textarea
            ref="input"
            v-model="content"
            class="input"
            rows="5"
            maxlength="2000"
            :placeholder="t('feedback.contentPlaceholder')"
          />
          <span class="field__hint" :style="remaining < 0 ? 'color: var(--danger)' : ''">
            {{ t("feedback.remaining", { n: remaining }) }}
          </span>
        </FormField>
      </div>

      <div class="modal__foot">
        <button type="button" class="btn" :disabled="busy" @click="$emit('close')">
          {{ t("action.cancel") }}
        </button>
        <button type="button" class="btn btn--primary" :disabled="busy" @click="submit">
          {{ busy ? t("feedback.submitting") : t("feedback.submit") }}
        </button>
      </div>
    </div>
  </div>
</template>
