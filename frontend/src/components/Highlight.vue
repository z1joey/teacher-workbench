<script setup>
// 把 text 里与 query 命中的片段包上 <mark class="hl">，用于搜索结果高亮。
// 大小写不敏感；query 为空时原样输出。
import { computed } from "vue"

const props = defineProps({
  text: { type: String, default: "" },
  query: { type: String, default: "" },
})

const parts = computed(() => {
  const text = props.text ?? ""
  const q = props.query.trim().toLowerCase()
  if (!q) return [{ text, hit: false }]
  const lower = text.toLowerCase()
  const out = []
  let i = 0
  while (i < text.length) {
    const idx = lower.indexOf(q, i)
    if (idx === -1) {
      out.push({ text: text.slice(i), hit: false })
      break
    }
    if (idx > i) out.push({ text: text.slice(i, idx), hit: false })
    out.push({ text: text.slice(idx, idx + q.length), hit: true })
    i = idx + q.length
  }
  return out
})
</script>

<template>
  <template v-for="(p, i) in parts" :key="i">
    <mark v-if="p.hit" class="hl">{{ p.text }}</mark>
    <template v-else>{{ p.text }}</template>
  </template>
</template>
