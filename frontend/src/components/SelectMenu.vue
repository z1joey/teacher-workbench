<script setup>
// 自绘下拉菜单：内嵌浏览器里原生 select 的弹出菜单又大又跑位，
// 这里把菜单固定渲染在触发器正下方，宽度、样式跟随应用本身。
// 触发器外观可用 triggerClass 覆盖，也可用 #trigger 插槽完全自定义。
import { computed, onBeforeUnmount, onMounted, ref } from "vue"
import Icon from "./Icon.vue"

const props = defineProps({
  modelValue: { type: [String, Number], default: "" },
  options: { type: Array, default: () => [] }, // [{ value, label }]
  placeholder: { type: String, default: "" },
  disabled: { type: Boolean, default: false },
  ariaLabel: { type: String, default: "" },
  triggerClass: { type: String, default: "" },
})
const emit = defineEmits(["update:modelValue"])

const open = ref(false)
const root = ref(null)

const current = computed(() => props.options.find((o) => o.value === props.modelValue))

function choose(option) {
  open.value = false
  emit("update:modelValue", option.value)
}

function onDocClick(e) {
  if (open.value && root.value && !root.value.contains(e.target)) open.value = false
}
function onKeydown(e) {
  if (e.key === "Escape") open.value = false
}
onMounted(() => {
  document.addEventListener("click", onDocClick)
  document.addEventListener("keydown", onKeydown)
})
onBeforeUnmount(() => {
  document.removeEventListener("click", onDocClick)
  document.removeEventListener("keydown", onKeydown)
})
</script>

<template>
  <div ref="root" class="select-menu">
    <button
      type="button"
      class="select-menu__trigger"
      :class="triggerClass"
      :disabled="disabled"
      :aria-haspopup="options.length ? 'listbox' : undefined"
      :aria-expanded="open"
      :aria-label="ariaLabel || undefined"
      @click="open = !open"
    >
      <slot name="trigger" :label="current?.label || placeholder" :open="open">
        <span :class="{ 'select-menu__placeholder': !current }">{{ current?.label || placeholder }}</span>
        <Icon name="chevron-down" :size="14" class="select-menu__chevron" />
      </slot>
    </button>
    <div v-if="open" class="select-menu__menu" role="listbox" :aria-label="ariaLabel || undefined">
      <button
        v-for="o in options"
        :key="o.value"
        type="button"
        role="option"
        :aria-selected="o.value === modelValue"
        class="select-menu__option"
        :class="{ 'is-selected': o.value === modelValue }"
        @click="choose(o)"
      >
        {{ o.label }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.select-menu {
  position: relative;
  display: inline-block;
}
.select-menu__trigger {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  width: auto;
  max-width: 280px;
  cursor: pointer;
  white-space: nowrap;
}
.select-menu__chevron {
  flex-shrink: 0;
  color: var(--muted);
}
.select-menu__placeholder {
  color: var(--muted);
}
.select-menu__menu {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  z-index: 70;
  min-width: 100%;
  max-width: 320px;
  max-height: 264px;
  overflow-y: auto;
  padding: 4px;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 10px;
  box-shadow: var(--shadow-lg);
}
.select-menu__option {
  display: flex;
  align-items: center;
  width: 100%;
  padding: 7px 10px;
  border: 0;
  border-radius: 7px;
  background: none;
  color: var(--ink);
  font: inherit;
  font-size: var(--fs-sm);
  text-align: left;
  white-space: nowrap;
  cursor: pointer;
}
.select-menu__option:hover {
  background: color-mix(in srgb, var(--primary) 8%, var(--surface));
}
.select-menu__option.is-selected {
  color: var(--primary);
  font-weight: 600;
}
.select-menu__trigger:disabled {
  cursor: default;
  opacity: 0.6;
}
</style>
