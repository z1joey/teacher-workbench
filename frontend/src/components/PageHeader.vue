<script setup>
// 页面头部：标题、说明、关键数据、操作区 —— 每页结构一致，位置可预期。
// 返回路径统一由顶栏面包屑承担，避免页面上出现两套返回入口。
defineProps({
  title: { type: String, required: true },
  subtitle: { type: String, default: "" },
  meta: { type: Array, default: () => [] }, // [{ label, value }] 标题下方的简要数据
})
</script>

<template>
  <header class="page-head">
    <div class="page-head__main">
      <!-- #title 允许把标题位换成控件（如班级切换下拉框），替代纯文本 h1 -->
      <h1 v-if="$slots.title" class="page-title page-title--loose">
        <slot name="title" />
      </h1>
      <h1 v-else class="page-title">{{ title }}</h1>
      <p v-if="subtitle" class="page-sub">{{ subtitle }}</p>

      <div v-if="meta.length || $slots.meta" class="page-head__meta-wrap">
        <slot name="meta">
          <div class="row-wrap">
            <span v-for="m in meta" :key="m.label" class="pill pill--outline">
              {{ m.label }} <b class="tnum">{{ m.value }}</b>
            </span>
          </div>
        </slot>
      </div>
    </div>

    <div v-if="$slots.actions" class="page-head__actions">
      <slot name="actions" />
    </div>
  </header>
</template>
