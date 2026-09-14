<script setup>
// 首次进入（姓名为空）时问一声称呼：可设置可跳过。
// 是否再弹由 App.vue 决定（跳过/保存后同一浏览器不再弹）。
import { nextTick, onMounted, ref } from "vue"
import FormField from "./FormField.vue"
import api from "../api"
import { loadMe } from "../auth"
import { notify } from "../feedback"
import { friendlyError, t } from "../strings"

const emit = defineEmits(["close"])

const name = ref("")
const error = ref("")
const busy = ref(false)
const input = ref(null)

onMounted(async () => {
  await nextTick()
  input.value?.focus()
})

async function save() {
  const trimmed = name.value.trim()
  if (!trimmed) {
    error.value = t("namePrompt.required")
    return
  }
  busy.value = true
  error.value = ""
  try {
    await api.patch("/profile", { name: trimmed })
    await loadMe()
    notify({ tone: "ok", title: t("namePrompt.saved"), timeout: 2400 })
    emit("close")
  } catch (e) {
    error.value = friendlyError(e)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="overlay" role="dialog" aria-modal="true" :aria-labelledby="'name-prompt-title'">
    <div class="modal">
      <div class="modal__head">
        <div class="grow">
          <h2 id="name-prompt-title" class="modal__title">{{ t("namePrompt.title") }}</h2>
        </div>
      </div>

      <div class="modal__body">
        <FormField :label="t('login.name')" :error="error">
          <input
            ref="input"
            v-model="name"
            class="input"
            type="text"
            maxlength="100"
            autocomplete="name"
            :placeholder="t('namePrompt.placeholder')"
            @keydown.enter="save"
          />
        </FormField>
        <p style="margin-top: 10px; color: var(--muted, #888); font-size: 13px">
          {{ t("namePrompt.hint") }}
        </p>
      </div>

      <div class="modal__foot">
        <button type="button" class="btn" :disabled="busy" @click="$emit('close')">
          {{ t("namePrompt.skip") }}
        </button>
        <button type="button" class="btn btn--primary" :disabled="busy" @click="save">
          {{ busy ? t("namePrompt.saving") : t("namePrompt.save") }}
        </button>
      </div>
    </div>
  </div>
</template>
