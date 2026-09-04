<script setup>
// 顶栏全局搜索：输入即出结果，↑↓ 选择、Enter 打开、Esc 清空。
// 查询词与学生列表页共享，所以「在这里搜」和「去列表里筛」是同一件事。
import { computed, ref, watch } from "vue"
import { useRouter } from "vue-router"
import Icon from "./Icon.vue"
import { ensureSearchStudents, searchQuery, searchStudents } from "../search"
import { t } from "../strings"

const router = useRouter()
const inputEl = ref(null)
const open = ref(false)
const cursor = ref(-1)

const matches = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return []
  return searchStudents.value
    .filter(
      (s) =>
        s.name.toLowerCase().includes(q) ||
        s.admission_no.toLowerCase().includes(q) ||
        (s.class && s.class.name.toLowerCase().includes(q))
    )
    .slice(0, 7)
})

watch(searchQuery, (q) => {
  cursor.value = -1
  if (q.trim()) ensureSearchStudents()
})

function focus() {
  inputEl.value?.focus()
  inputEl.value?.select()
}
defineExpose({ focus })

function openStudent(s) {
  searchQuery.value = ""
  open.value = false
  inputEl.value?.blur()
  router.push(`/students/${s.id}`)
}

function goList() {
  open.value = false
  inputEl.value?.blur()
  router.push("/students")
}

function onKeydown(e) {
  if (e.key === "ArrowDown") {
    e.preventDefault()
    if (matches.value.length) cursor.value = (cursor.value + 1) % matches.value.length
  } else if (e.key === "ArrowUp") {
    e.preventDefault()
    if (matches.value.length) cursor.value = (cursor.value - 1 + matches.value.length) % matches.value.length
  } else if (e.key === "Enter") {
    e.preventDefault()
    if (cursor.value >= 0 && matches.value[cursor.value]) openStudent(matches.value[cursor.value])
    else goList()
  } else if (e.key === "Escape") {
    e.preventDefault()
    if (searchQuery.value) {
      searchQuery.value = ""
    } else {
      open.value = false
      inputEl.value?.blur()
    }
  }
}

function clear() {
  searchQuery.value = ""
  focus()
}
</script>

<template>
  <div class="topbar__search">
    <div class="search-box" role="search">
      <Icon name="search" :size="15" />
      <input
        ref="inputEl"
        v-model="searchQuery"
        class="input input--search"
        type="text"
        :placeholder="t('students.search')"
        autocomplete="off"
        role="combobox"
        aria-label="搜索学生"
        :aria-expanded="open && matches.length > 0"
        aria-controls="nav-search-results"
        @focus="open = true; ensureSearchStudents()"
        @blur="setTimeout(() => (open = false), 120)"
        @keydown="onKeydown"
      />
      <button
        v-if="searchQuery"
        class="icon-btn search-box__clear"
        aria-label="清空搜索"
        @mousedown.prevent="clear"
      >
        <Icon name="close" :size="13" />
      </button>
      <kbd v-else class="kbd" style="position: absolute; right: 8px">/</kbd>
    </div>

    <div
      v-if="open && searchQuery.trim()"
      id="nav-search-results"
      class="search-results"
      role="listbox"
      aria-label="搜索结果"
    >
      <button
        v-for="(s, i) in matches"
        :key="s.id"
        class="search-results__item"
        :class="{ 'is-cursor': cursor === i }"
        role="option"
        :aria-selected="cursor === i"
        type="button"
        @mousedown.prevent="openStudent(s)"
      >
        <span class="avatar avatar--onpaper" style="width: 26px; height: 26px; font-size: 12px">
          {{ s.name.charAt(0) }}
        </span>
        <span class="search-results__text">
          <span class="search-results__name">{{ s.name }}</span>
          <span class="search-results__meta">
            {{ s.admission_no }} · {{ s.class ? s.class.name : t("students.ungrouped") }}
          </span>
        </span>
      </button>

      <p v-if="!matches.length" class="state__desc" style="padding: 14px; text-align: center">
        {{ t("common.noMatch") }}
      </p>

      <div v-if="matches.length" class="search-results__foot">
        Enter 查看全部结果 · ↑↓ 选择
      </div>
    </div>
  </div>
</template>
