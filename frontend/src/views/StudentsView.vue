<script setup>
// 学生列表：一次只看一个班（页头标题位下拉切换，未分班也是一个选项），
// 顶部搜索时跨全部学生匹配、平铺展示结果。
import { computed, onMounted, ref } from "vue"
import { useRoute, useRouter } from "vue-router"
import Icon from "../components/Icon.vue"
import SelectMenu from "../components/SelectMenu.vue"
import PageHeader from "../components/PageHeader.vue"
import AsyncState from "../components/AsyncState.vue"
import api from "../api"
import { ensureSearchStudents, searchQuery, studentMatchesQuery, matchedGuardiansOf } from "../search"
import Highlight from "../components/Highlight.vue"
import { friendlyError, tagStyle, t, eventTitle, describeEvent, dateLocale } from "../strings"

const route = useRoute()
const router = useRouter()
const students = ref([])
const query = searchQuery // global — the top bar search box filters this list
const loading = ref(true)
const error = ref("")

const UNGROUPED = "ungrouped" // ?class= 的未分班哨兵值

async function load() {
  loading.value = true
  error.value = ""
  try {
    students.value = await api.get("/students")
    // 搜索目录是含已毕业的超集，且在数据变化后强制刷新
    await ensureSearchStudents(true)
  } catch (e) {
    error.value = friendlyError(e)
  } finally {
    loading.value = false
  }
}
onMounted(load)

const filtered = computed(() => {
  const q = query.value.trim().toLowerCase()
  if (!q) return students.value
  return students.value.filter((s) => studentMatchesQuery(s, q))
})

const searching = computed(() => query.value.trim().length > 0)

// 班级选项来自学生数据本身（没有学生的班不出现在学生页）
const classOptions = computed(() => {
  const byId = new Map()
  for (const s of students.value) {
    if (s.class && !byId.has(s.class.id)) byId.set(s.class.id, { id: s.class.id, name: s.class.name })
  }
  return [...byId.values()]
})
const hasUngrouped = computed(() => students.value.some((s) => !s.class))
const groupCount = computed(() => classOptions.value.length + (hasUngrouped.value ? 1 : 0))

const switcherOptions = computed(() => {
  const opts = classOptions.value.map((c) => ({ value: c.id, label: c.name }))
  if (hasUngrouped.value) opts.push({ value: UNGROUPED, label: t("students.ungrouped") })
  return opts
})

// 选中班：URL ?class= 优先（班 id 或 "ungrouped"），否则第一个班
const selectedKey = computed(() => {
  const raw = route.query.class
  const wanted = Array.isArray(raw) ? raw[0] : raw
  if (wanted === UNGROUPED) return UNGROUPED
  if (wanted && classOptions.value.some((c) => c.id === wanted)) return wanted
  return classOptions.value[0]?.id ?? (students.value.length ? UNGROUPED : null)
})

function switchClass(key) {
  router.replace({ query: { ...route.query, class: key } })
}

// 搜索时跨全部学生匹配；平时只看选中班
const visibleStudents = computed(() => {
  if (searching.value) return filtered.value
  if (!selectedKey.value) return []
  if (selectedKey.value === UNGROUPED) return students.value.filter((s) => !s.class)
  return students.value.filter((s) => s.class?.id === selectedKey.value)
})

const classEmpty = computed(
  () => !searching.value && !!students.value.length && !visibleStudents.value.length
)

function fmtDate(ts) {
  return new Date(ts).toLocaleDateString(dateLocale(), {
    year: "numeric",
    month: "short",
    day: "numeric",
  })
}

function lastEventText(ev) {
  if (!ev) return ""
  return describeEvent(ev.event_type, ev.payload)
}

// 搜索时该学生被监护人命中的记录；卡片上单独一行展示（否则看不到匹配依据）
function guardianHits(s) {
  const q = query.value.trim().toLowerCase()
  return q ? matchedGuardiansOf(s, q) : []
}
</script>

<template>
  <PageHeader
    :title="t('students.title')"
    :subtitle="t('students.subtitle', { count: visibleStudents.length })"
  >
    <template v-if="groupCount > 1" #title>
      <SelectMenu
        :model-value="selectedKey"
        :options="switcherOptions"
        aria-label="选择班级"
        trigger-class="class-switcher__select"
        @update:model-value="switchClass"
      >
        <template #trigger="{ label }">
          <span>{{ label }}</span>
          <Icon name="chevron-down" :size="18" class="class-switcher__chevron" />
        </template>
      </SelectMenu>
    </template>
    <template #actions>
      <span v-if="searching" class="pill pill--info">
        正在筛选「{{ query.trim() }}」· {{ filtered.length }} 人
        <button
          class="btn btn--sm btn--quiet"
          style="height: 18px; padding: 0 4px"
          aria-label="清除筛选"
          @click="query = ''"
        >
          <Icon name="close" :size="11" />
        </button>
      </span>
      <router-link to="/students/new">
        <button class="btn btn--primary"><Icon name="plus" :size="15" /> {{ t("students.add") }}</button>
      </router-link>
    </template>
  </PageHeader>

  <AsyncState
    :loading="loading"
    :error="error"
    :empty="!loading && !error && !visibleStudents.length"
    :empty-title="
      searching ? t('common.noMatch') : classEmpty ? '这个班还没有学生' : t('students.emptyTitle')
    "
    :empty-desc="
      searching
        ? '换个姓名、学号或班级再试试。'
        : classEmpty
          ? '从页头下拉切换其他班级。'
          : t('students.emptyDesc')
    "
    empty-icon="users"
    @retry="load"
  >
    <template #emptyAction>
      <button v-if="searching" class="btn" @click="query = ''">清除筛选</button>
      <router-link v-else to="/students/new">
        <button class="btn btn--primary"><Icon name="plus" :size="15" /> {{ t("students.add") }}</button>
      </router-link>
    </template>

    <section v-if="visibleStudents.length" class="card">
      <div class="student-cards">
        <article
          v-for="s in visibleStudents"
          :key="s.id"
          class="student-card is-clickable"
          tabindex="0"
          @click="router.push(`/students/${s.id}`)"
          @keydown.enter.prevent="router.push(`/students/${s.id}`)"
        >
          <header class="student-card__head">
            <div class="student-card__identity">
              <h3 class="student-card__name">{{ s.name }}</h3>
              <span class="student-card__no muted tnum">
                {{ s.admission_no }}<template v-if="searching && s.class"> · {{ s.class.name }}</template>
              </span>
            </div>
            <Icon name="chevron-right" :size="15" class="student-card__chevron" />
          </header>

          <p v-if="guardianHits(s).length" class="student-card__guardians muted">
            监护人：<template v-for="(g, gi) in guardianHits(s)" :key="g.id"><template v-if="gi">、</template><Highlight :text="g.name" :query="query" /></template>
          </p>

          <div v-if="s.tags?.length" class="chips student-card__tags">
            <span
              v-for="tag in s.tags"
              :key="tag.id"
              class="tag"
              :style="tagStyle(tag.color)"
            >{{ tag.name }}</span>
          </div>

          <footer v-if="s.last_event" class="student-card__event">
            <div class="student-card__event-head">
              <span class="student-card__event-type">
                {{ eventTitle(s.last_event.event_type, s.last_event.payload) }}
              </span>
              <time class="student-card__event-time muted tnum">
                {{ fmtDate(s.last_event.occurred_at) }}
              </time>
            </div>
            <!-- 无文字也渲染：占住两行高度，让各卡片分隔线对齐 -->
            <p class="student-card__event-desc muted">{{ lastEventText(s.last_event) }}</p>
          </footer>
          <footer v-else class="student-card__event">
            <p class="student-card__empty muted">
              <Icon name="clock" :size="12" /> {{ t("students.noRecentEvent") }}
            </p>
          </footer>
        </article>
      </div>
    </section>
  </AsyncState>
</template>
