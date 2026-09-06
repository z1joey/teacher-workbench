<script setup>
// 学生列表：按班级分组，可折叠；顶栏搜索框与这里共享查询词。
// 窄屏时表格自动转为「标签 + 值」的堆叠行，不需要横向滚动。
import { computed, onMounted, ref } from "vue"
import { useRouter } from "vue-router"
import Icon from "../components/Icon.vue"
import PageHeader from "../components/PageHeader.vue"
import AsyncState from "../components/AsyncState.vue"
import api from "../api"
import { searchQuery, searchStudents } from "../search"
import { friendlyError, t } from "../strings"

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
  return students.value.filter(
    (s) =>
      s.name.toLowerCase().includes(q) ||
      s.admission_no.toLowerCase().includes(q) ||
      (s.class && s.class.name.toLowerCase().includes(q))
  )
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

    <div class="stack">
      <section v-for="g in groups" :key="g.name" class="card">
        <div class="card__head card__head--plain" :class="{ 'is-collapsed': isCollapsed(g) }">
          <button
            :id="`group-head-${g.name}`"
            class="card__title"
            type="button"
            style="background: none; border: 0; cursor: pointer; padding: 0; font: inherit; font-weight: 600"
            :aria-expanded="!isCollapsed(g)"
            :aria-controls="`group-body-${g.name}`"
            @click="toggleGroup(g)"
          >
            <Icon
              :name="isCollapsed(g) ? 'chevron-right' : 'chevron-down'"
              :size="16"
              style="color: var(--muted)"
            />
            {{ g.name }}
            <span class="pill pill--muted pill--count">{{ g.list.length }}</span>
          </button>
        </div>

        <div v-show="!isCollapsed(g)" :id="`group-body-${g.name}`" role="region" :aria-labelledby="`group-head-${g.name}`">
          <div class="table-wrap">
            <table class="table table--stack">
              <thead>
                <tr>
                  <th style="width: 130px">{{ t("th.admissionNo") }}</th>
                  <th>{{ t("th.name") }}</th>
                  <th>{{ t("th.tags") }}</th>
                  <th style="width: 40px" />
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="s in g.list"
                  :key="s.id"
                  class="is-clickable"
                  tabindex="0"
                  @click="router.push(`/students/${s.id}`)"
                  @keydown.enter.prevent="router.push(`/students/${s.id}`)"
                >
                  <td data-label="学号">
                    <span class="muted tnum">{{ s.admission_no }}</span>
                  </td>
                  <td data-label="姓名" class="cell-main">
                    <span class="row">
                      <span class="avatar avatar--onpaper" style="width: 26px; height: 26px; font-size: 12px">
                        {{ s.name.charAt(0) }}
                      </span>
                      {{ s.name }}
                    </span>
                  </td>
                  <td data-label="标签">
                    <span v-if="s.tags && s.tags.length" class="chips">
                      <span
                        v-for="tag in s.tags"
                        :key="tag.id"
                        class="tag"
                        :style="{ background: tag.color }"
                      >{{ tag.name }}</span>
                    </span>
                    <span v-else class="muted">{{ t("common.none") }}</span>
                  </td>
                  <td data-hidden-mobile>
                    <Icon name="chevron-right" :size="15" style="color: var(--muted)" />
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </section>
    </div>
  </AsyncState>
</template>
