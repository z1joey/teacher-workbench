<script setup>
// 表单字段：标签 + 说明 + 就地错误，三者永远一起出现。
// 用 <label> 包裹控件，点击标签即可聚焦，且错误信息会被读屏一起念出。
import Icon from "./Icon.vue"

defineProps({
  label: { type: String, required: true },
  required: { type: Boolean, default: false },
  optional: { type: Boolean, default: false },
  hint: { type: String, default: "" },
  error: { type: String, default: "" },
})
</script>

<template>
  <div class="field">
    <label>
      <span class="field__label">
        {{ label }}
        <span v-if="required" class="field__req" aria-hidden="true">*</span>
        <span v-if="optional" class="field__opt">选填</span>
      </span>
      <slot :invalid="!!error" />
      <span v-if="error" class="field__error">
        <Icon name="alert-circle" :size="12" /> {{ error }}
      </span>
      <span v-else-if="hint" class="field__hint">{{ hint }}</span>
    </label>
  </div>
</template>
