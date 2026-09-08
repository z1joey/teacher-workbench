<script setup>
// 学生列表：按班级分组，可折叠；每组内用卡片网格展示学生。
import { computed, onMounted, ref } from "vue"
import { useRouter } from "vue-router"
import Icon from "../components/Icon.vue"
import PageHeader from "../components/PageHeader.vue"
import AsyncState from "../components/AsyncState.vue"
import api from "../api"
import { searchQuery, searchStudents, studentMatchesQuery, matchedGuardiansOf } from "../search"
import Highlight from "../components/Highlight.vue"
import { friendlyError, tagStyle, t, eventTitle, describeEvent, dateLocale } from "../strings"

const router = useRouter()
const students = ref([])
const query = searchQuery // global — the top bar search box filters this list
const loading = ref(true)
const error = ref("")
const collapsed = ref({})

async function load() {
  loading.value = true
  error.value = ""
  try {
    students.value = await api.get("/students")
    searchStudents.value = students.value // keep the top bar dropdown in sync
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

// First-appearance order (admission_no order); students without a class go last.
const groups = computed(() => {
  const byName = new Map()
  for (const s of filtered.value) {
    const name = s.class ? s.class.name : t("students.ungrouped")
    if (!byName.has(name)) byName.set(name, [])
    byName.get(name).push(s)
  }
  const ungrouped = t("students.ungrouped")
  return [...byName.entries()]
    .sort(([a], [b]) => (a === ungrouped) - (b === ungrouped))
    .map(([name, list]) => ({ name, list }))
})

const searching = computed(() => query.value.trim().length > 0)

// While searching, always expand so matches are never hidden inside a collapsed group.
function isCollapsed(group) {
  return !searching.value && !!collapsed.value[group.name]
}
function toggleGroup(group) {
  collapsed.value[group.name] = !collapsed.value[group.name]
}

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
    :subtitle="t('students.subtitle', { count: students.length })"
  >
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
    :empty="!loading && !filtered.length"
    :empty-title="searching ? t('common.noMatch') : t('students.emptyTitle')"
    :empty-desc="searching ? '换个姓名、学号或班级再试试。' : t('students.emptyDesc')"
    empty-icon="users"
    @retry="load"
  >
    <template #emptyAction>
      <button v-if="searching" class="btn" @click="query = ''">清除筛选</button>
      <router-link v-else to="/students/new">
        <button class="btn btn--primary"><Icon name="plus" :size="15" /> {{ t("students.add") }}</button>
      </router-link>
    </template>

    <div class="stack stack--flush">
      <section
        v-for="g in groups"
        :key="g.name"
        class="card student-group"
        :class="{ 'is-collapsed': isCollapsed(g) }"
      >
        <button
          :id="`group-head-${g.name}`"
          class="student-group__toggle"
          type="button"
          :aria-expanded="!isCollapsed(g)"
          :aria-controls="`group-body-${g.name}`"
          @click="toggleGroup(g)"
        >
          <Icon
            :name="isCollapsed(g) ? 'chevron-right' : 'chevron-down'"
            :size="16"
            class="student-group__chevron"
          />
          <span class="student-group__name">{{ g.name }}</span>
          <span class="pill pill--muted pill--count">{{ g.list.length }}</span>
        </button>

        <div
          v-show="!isCollapsed(g)"
          :id="`group-body-${g.name}`"
          class="student-group__body"
          role="region"
          :aria-labelledby="`group-head-${g.name}`"
        >
          <div class="student-cards">
            <article
              v-for="s in g.list"
              :key="s.id"
              class="student-card is-clickable"
              tabindex="0"
              @click="router.push(`/students/${s.id}`)"
              @keydown.enter.prevent="router.push(`/students/${s.id}`)"
            >
              <header class="student-card__head">
                <div class="student-card__identity">
                  <h3 class="student-card__name">{{ s.name }}</h3>
                  <span class="student-card__no muted tnum">{{ s.admission_no }}</span>
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
                <p v-if="lastEventText(s.last_event)" class="student-card__event-desc muted">
                  {{ lastEventText(s.last_event) }}
                </p>
              </footer>
              <p v-else class="student-card__empty muted">
                <Icon name="clock" :size="12" /> {{ t("students.noRecentEvent") }}
              </p>
            </article>
          </div>
        </div>
      </section>
    </div>
  </AsyncState>
</template>
