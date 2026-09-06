<script setup>
// 统一的异步状态容器：加载中给骨架屏，出错给可恢复的失败态，空数据给带引导的空态。
// 这样每个页面都不必各自发明一套状态文案（一致性 + 错误可恢复 + 新手友好）。
import Icon from "./Icon.vue"

defineProps({
  loading: { type: Boolean, default: false },
  error: { type: String, default: "" },
  empty: { type: Boolean, default: false },
  emptyTitle: { type: String, default: "这里还没有内容" },
  emptyDesc: { type: String, default: "" },
  emptyIcon: { type: String, default: "note" },
  rows: { type: Number, default: 3 },
  bare: { type: Boolean, default: false }, // 不套卡片
})
const emit = defineEmits(["retry"])
</script>

<template>
  <!-- 加载中：骨架屏而不是空白，用户知道系统在干活 -->
  <div v-if="loading" :class="bare ? '' : 'card'">
    <div :class="bare ? '' : 'card__body'" class="stack">
      <div class="skeleton skeleton--title" />
      <div v-for="i in rows" :key="i" class="skeleton skeleton--row" />
    </div>
  </div>

  <!-- 出错：说明发生了什么，并给一个明确的重试出口 -->
  <div v-else-if="error" :class="bare ? '' : 'card'">
    <div class="state" :class="bare ? '' : 'state--in-card'">
      <span class="state__icon state__icon--error"><Icon name="alert-circle" :size="22" /></span>
      <p class="state__title">没能加载这部分内容</p>
      <p class="state__desc">{{ error }}</p>
      <div class="state__actions">
        <button class="btn btn--primary" @click="emit('retry')">
          <Icon name="refresh" :size="14" /> 重试
        </button>
      </div>
    </div>
  </div>

  <!-- 空数据：告诉用户下一步该做什么，而不是只说「暂无数据」 -->
  <div v-else-if="empty" :class="bare ? '' : 'card'">
    <div class="state" :class="bare ? '' : 'state--in-card'">
      <span class="state__icon"><Icon :name="emptyIcon" :size="22" /></span>
      <p class="state__title">{{ emptyTitle }}</p>
      <p v-if="emptyDesc" class="state__desc">{{ emptyDesc }}</p>
      <div v-if="$slots.emptyAction" class="state__actions">
        <slot name="emptyAction" />
      </div>
    </div>
  </div>

  <slot v-else />
</template>
