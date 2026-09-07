<script setup>
import { ref } from "vue"
import Icon from "./Icon.vue"

defineProps({
  modelValue: { type: String, default: "" },
  autocomplete: { type: String, default: "current-password" },
  minlength: { type: [Number, String], default: undefined },
  required: { type: Boolean, default: false },
  invalid: { type: Boolean, default: false },
  sm: { type: Boolean, default: false },
  placeholder: { type: String, default: "" },
})

defineEmits(["update:modelValue"])

const show = ref(false)
</script>

<template>
  <div class="password-input">
    <input
      class="input password-input__field"
      :class="{ 'input--sm': sm }"
      :value="modelValue"
      :type="show ? 'text' : 'password'"
      :autocomplete="autocomplete"
      :minlength="minlength"
      :required="required"
      :placeholder="placeholder"
      :aria-invalid="invalid || undefined"
      @input="$emit('update:modelValue', $event.target.value)"
    />
    <button
      type="button"
      class="password-input__toggle"
      :aria-label="show ? '隐藏密码' : '显示密码'"
      :title="show ? '隐藏密码' : '显示密码'"
      @click="show = !show"
    >
      <Icon :name="show ? 'eye-off' : 'eye'" :size="15" />
    </button>
  </div>
</template>
