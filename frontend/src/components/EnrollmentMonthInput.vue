<script setup>
// 入学月份：原生 <input type="month"> 的展示语言随浏览器/OS，无法稳定显示中文。
// 用年、月下拉框，标签与 formatEnrollmentMonth 一致。
import { computed } from "vue"
import {
  ENROLLMENT_MAX_YEAR,
  ENROLLMENT_MIN_YEAR,
  buildEnrollmentMonth,
  parseEnrollmentMonth,
} from "../strings"

const props = defineProps({
  modelValue: { type: String, default: "" },
  required: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false },
})
const emit = defineEmits(["update:modelValue"])

const fallback = (() => {
  const now = new Date()
  return { year: now.getFullYear(), month: now.getMonth() + 1 }
})()

const parsed = computed(() => parseEnrollmentMonth(props.modelValue) || fallback)

const year = computed({
  get: () => parsed.value.year,
  set: (value) => emit("update:modelValue", buildEnrollmentMonth(value, parsed.value.month)),
})

const month = computed({
  get: () => parsed.value.month,
  set: (value) => emit("update:modelValue", buildEnrollmentMonth(parsed.value.year, value)),
})

const yearOptions = computed(() => {
  const options = []
  for (let y = ENROLLMENT_MIN_YEAR; y <= ENROLLMENT_MAX_YEAR; y++) {
    options.push({ value: y, label: `${y}年` })
  }
  return options
})

const monthOptions = Array.from({ length: 12 }, (_, i) => ({
  value: i + 1,
  label: `${i + 1}月`,
}))
</script>

<template>
  <div class="enrollment-month-input">
    <select
      v-model.number="year"
      class="select enrollment-month-input__year"
      :required="required"
      :disabled="disabled"
      aria-label="入学年份"
    >
      <option v-for="o in yearOptions" :key="o.value" :value="o.value">{{ o.label }}</option>
    </select>
    <select
      v-model.number="month"
      class="select enrollment-month-input__month"
      :required="required"
      :disabled="disabled"
      aria-label="入学月份"
    >
      <option v-for="o in monthOptions" :key="o.value" :value="o.value">{{ o.label }}</option>
    </select>
  </div>
</template>

<style scoped>
.enrollment-month-input {
  display: flex;
  gap: var(--sp-2);
}
.enrollment-month-input__year {
  flex: 1.2;
  min-width: 0;
}
.enrollment-month-input__month {
  flex: 1;
  min-width: 0;
}
</style>
