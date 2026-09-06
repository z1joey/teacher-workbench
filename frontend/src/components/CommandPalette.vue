<script setup>
// 命令面板（⌘K / Ctrl+K）：高手的加速器 —— 一次输入即可跳转、搜索、新建
import { computed, nextTick, onMounted, ref, watch } from "vue"
import { useRouter } from "vue-router"
import Icon from "./Icon.vue"
import { ensureSearchStudents, searchStudents } from "../search"

const props = defineProps({
  actions: { type: Array, default: () => [] }, // [{ id, label, hint, icon, run }]
  pages: { type: Array, default: () => [] }, // [{ label, to, icon, hint }]
})
const emit = defineEmits(["close"])

const router = useRouter()
const query = ref("")
const cursor = ref(0)
const inputEl = ref(null)

onMounted(async () => {
  inputEl.value?.focus()
  ensureSearchStudents()
})

const q = computed(() => query.value.trim().toLowerCase())

const studentItems = computed(() => {
  if (!q.value) return []
  return searchStudents.value
    .filter(
      (s) =>
        s.name.toLowerCase().includes(q.value) ||
        s.admission_no.toLowerCase().includes(q.value) ||
        (s.class && s.class.name.toLowerCase().includes(q.value))
    )
    .slice(0, 6)
    .map((s) => ({
      key: `student-${s.id}`,
      label: s.name,
      hint: `${s.admission_no} · ${s.class ? s.class.name : "未分班"}`,
      icon: "user",
      group: "学生",
      run: () => router.push(`/students/${s.id}`),
    }))
})

const pageItems = computed(() =>
  props.pages
    .filter((p) => !q.value || p.label.toLowerCase().includes(q.value) || (p.hint || "").toLowerCase().includes(q.value))
    .map((p) => ({ ...p, key: `page-${p.to}`, group: "前往", run: () => router.push(p.to) }))
)

const actionItems = computed(() =>
  props.actions
    .filter((a) => !q.value || a.label.toLowerCase().includes(q.value) || (a.hint || "").toLowerCase().includes(q.value))
    .map((a) => ({ ...a, key: `act-${a.id}`, group: "操作" }))
)

const groups = computed(() => {
  const out = []
  if (pageItems.value.length) out.push({ name: "前往", items: pageItems.value })
  if (actionItems.value.length) out.push({ name: "操作", items: actionItems.value })
  if (studentItems.value.length) out.push({ name: "学生", items: studentItems.value })
  return out
})

const flat = computed(() => groups.value.flatMap((g) => g.items))

watch(flat, () => {
  cursor.value = 0
})

function move(delta) {
  const n = flat.value.length
  if (!n) return
  cursor.value = (cursor.value + delta + n) % n
}

function choose(item) {
  emit("close")
  item.run()
}

function onKeydown(e) {
  if (e.key === "ArrowDown") {
    e.preventDefault()
    move(1)
  } else if (e.key === "ArrowUp") {
    e.preventDefault()
    move(-1)
  } else if (e.key === "Enter") {
    e.preventDefault()
    const item = flat.value[cursor.value]
    if (item) choose(item)
  } else if (e.key === "Escape") {
    e.preventDefault()
    emit("close")
  }
}

// 让光标项始终留在可视区内
watch(cursor, async () => {
  await nextTick()
  document.querySelector(".palette__item.is-cursor")?.scrollIntoView({ block: "nearest" })
})
</script>

<template>
  <div class="overlay" style="z-index: 130" @click.self="emit('close')">
    <div class="palette" role="dialog" aria-modal="true" aria-label="命令面板">
      <div class="palette__input">
        <Icon name="search" :size="18" />
        <input
          ref="inputEl"
          v-model="query"
          type="text"
          placeholder="搜索学生、跳转页面或执行操作…"
          autocomplete="off"
          aria-label="搜索学生、页面或操作"
          @keydown="onKeydown"
        />
        <kbd class="kbd">Esc</kbd>
      </div>

      <div class="palette__list">
        <template v-for="g in groups" :key="g.name">
          <p class="palette__group">{{ g.name }}</p>
          <button
            v-for="item in g.items"
            :key="item.key"
            class="palette__item"
            :class="{ 'is-cursor': flat[cursor] && flat[cursor].key === item.key }"
            type="button"
            @mouseenter="cursor = flat.findIndex((x) => x.key === item.key)"
            @click="choose(item)"
          >
            <Icon :name="item.icon || 'arrow-right'" :size="16" />
            <span class="truncate">{{ item.label }}</span>
            <span v-if="item.hint" class="palette__meta">{{ item.hint }}</span>
          </button>
        </template>

        <p v-if="!flat.length" class="state__desc" style="padding: 24px; text-align: center">
          没有匹配的结果
        </p>
      </div>

      <div class="palette__foot">
        <span><kbd class="kbd">↑</kbd> <kbd class="kbd">↓</kbd> 选择</span>
        <span><kbd class="kbd">Enter</kbd> 打开</span>
        <span><kbd class="kbd">Esc</kbd> 关闭</span>
      </div>
    </div>
  </div>
</template>
