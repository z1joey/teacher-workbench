<script setup>
// 全局提示条：状态可见 + 撤销入口 + 失败重试
import Icon from "./Icon.vue"
import { dismiss, pauseToast, resumeToast, toasts } from "../feedback"

const TONE_ICON = {
  ok: "check-circle",
  error: "alert-circle",
  info: "info",
  pending: "clock",
}
</script>

<template>
  <div class="toast-stack" role="region" aria-label="操作提示">
    <div
      v-for="t in toasts"
      :key="t.id"
      class="toast"
      :class="`toast--${t.tone}`"
      role="status"
      aria-live="polite"
      @mouseenter="pauseToast(t.id)"
      @mouseleave="resumeToast(t.id)"
    >
      <span class="toast__icon">
        <span v-if="t.state === 'running'" class="spinner" />
        <Icon v-else :name="TONE_ICON[t.tone] || 'info'" :size="18" />
      </span>

      <div class="toast__body">
        <p class="toast__title">{{ t.title }}</p>
        <p v-if="t.detail" class="toast__desc">{{ t.detail }}</p>
      </div>

      <button
        v-if="t.action"
        class="btn btn--sm toast__action"
        @click="t.action.run()"
      >{{ t.action.label }}</button>

      <button class="icon-btn toast__close" aria-label="关闭提示" @click="dismiss(t.id)">
        <Icon name="close" :size="14" />
      </button>

      <span
        v-if="t.state === 'pending'"
        class="toast__bar"
        :style="{ width: `${t.progress * 100}%` }"
        aria-hidden="true"
      />
    </div>
  </div>
</template>
