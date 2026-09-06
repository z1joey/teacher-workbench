<script setup>
// 确认对话框：说清「删掉什么」和「连带什么」，不逼用户猜
import { computed, nextTick, ref, watch } from "vue"
import Icon from "./Icon.vue"
import { closeConfirm, confirmDialog, confirmEnabled } from "../confirm"

const wordInput = ref(null)
const cancelBtn = ref(null)

// 破坏性对话框默认焦点落在「取消」上，避免顺手回车造成误删
watch(confirmDialog, async (d) => {
  if (!d) return
  await nextTick()
  if (d.confirmWord) wordInput.value?.focus()
  else cancelBtn.value?.focus()
})

const canConfirm = computed(() => confirmEnabled(confirmDialog.value))

function onConfirm() {
  if (canConfirm.value) closeConfirm(true)
}
</script>

<template>
  <div
    v-if="confirmDialog"
    class="overlay"
    role="dialog"
    aria-modal="true"
    :aria-labelledby="'confirm-title'"
    @click.self="closeConfirm(false)"
  >
    <div class="modal">
      <div class="modal__head">
        <span
          class="modal__icon"
          :class="{ 'modal__icon--danger': confirmDialog.tone === 'danger' }"
        >
          <Icon :name="confirmDialog.tone === 'danger' ? 'alert' : 'help'" :size="18" />
        </span>
        <div class="grow">
          <h2 id="confirm-title" class="modal__title">{{ confirmDialog.title }}</h2>
        </div>
        <button class="icon-btn" aria-label="关闭" @click="closeConfirm(false)">
          <Icon name="close" :size="16" />
        </button>
      </div>

      <div class="modal__body">
        <p v-if="confirmDialog.message">{{ confirmDialog.message }}</p>

        <ul v-if="confirmDialog.consequences.length" class="consequence">
          <li v-for="(c, i) in confirmDialog.consequences" :key="i">{{ c }}</li>
        </ul>

        <div v-if="confirmDialog.confirmWord" style="margin-top: 16px">
          <label class="field__label" for="confirm-word">
            请输入 <b>{{ confirmDialog.confirmWord }}</b> 以确认
          </label>
          <input
            id="confirm-word"
            ref="wordInput"
            v-model="confirmDialog.input"
            class="input"
            type="text"
            autocomplete="off"
            :placeholder="confirmDialog.confirmWord"
            @keydown.enter="onConfirm"
          />
        </div>
      </div>

      <div class="modal__foot">
        <button ref="cancelBtn" class="btn" @click="closeConfirm(false)">
          {{ confirmDialog.cancelLabel }}
        </button>
        <button
          class="btn"
          :class="confirmDialog.tone === 'danger' ? 'btn--danger-solid' : 'btn--primary'"
          :disabled="!canConfirm"
          @click="onConfirm"
        >
          {{ confirmDialog.confirmLabel }}
        </button>
      </div>
    </div>
  </div>
</template>
