<script setup>
// 班级列表：班均摘要 + 最近事件，点卡片进详情看完整名单。
import { computed, onMounted, ref, watch } from "vue"
import { useRoute } from "vue-router"
import Icon from "../components/Icon.vue"
import PageHeader from "../components/PageHeader.vue"
import AsyncState from "../components/AsyncState.vue"
import FormField from "../components/FormField.vue"
import FeedEventItem from "../components/FeedEventItem.vue"
import api from "../api"
import { notify } from "../feedback"
import { friendlyError, subject, COMMON_SUBJECT_KEYS, t } from "../strings"

const route = useRoute()

const classes = ref([])
const unassigned = ref([])
const loading = ref(true)
const error = ref("")

const showCreate = ref(false)
const creating = ref(false)
const createError = ref("")
const createForm = ref(emptyForm())

const EVENTS_VISIBLE = 3
const expandedEvents = ref({})

function emptyForm() {
  return { name: "", academic_year: defaultYear() }
}

function defaultYear() {
  const now = new Date()
  const start = now.getMonth() + 1 >= 8 ? now.getFullYear() : now.getFullYear() - 1
  return `${start}/${start + 1}`
}

async function load() {
  loading.value = true
  error.value = ""
  try {
    const [cs, students] = await Promise.all([
      api.get("/classes"),
      api.get("/students"),
    ])
    classes.value = cs
    unassigned.value = students.filter((s) => s.status === "active" && !s.class)
  } catch (e) {
    error.value = friendlyError(e)
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await load()
  if (route.query.create === "1") showCreate.value = true
})
watch(() => route.query.create, (v) => {
  if (v === "1") showCreate.value = true
})

async function createClass() {
  createError.value = ""
  if (!createForm.value.name.trim()) {
    createError.value = t("classes.nameRequired")
    return
  }
  creating.value = true
  try {
    await api.post("/classes", {
      name: createForm.value.name.trim(),
      academic_year: createForm.value.academic_year.trim(),
    })
    createForm.value = emptyForm()
    showCreate.value = false
    notify({ tone: "ok", title: "班级已创建", timeout: 2600 })
    await load()
  } catch (e) {
    createError.value = friendlyError(e)
  } finally {
    creating.value = false
  }
}

function avgSummary(c) {
  const trend = c.avg_trend || []
  if (!trend.length) return []
  const last = trend[trend.length - 1]
  const prev = trend.length > 1 ? trend[trend.length - 2] : null
  const subs = Object.keys(last.averages).sort((a, b) => {
    const ia = COMMON_SUBJECT_KEYS.indexOf(a)
    const ib = COMMON_SUBJECT_KEYS.indexOf(b)
    return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib)
  })
  return subs.map((sub) => {
    const avg = last.averages[sub]
    const p = prev ? prev.averages[sub] : null
    const delta = p != null && avg != null ? Math.round((avg - p) * 10) / 10 : null
    return { sub, label: subject(sub), avg, delta }
  })
}

function visitedCount(c) {
  return (c.students || []).filter((s) => s.home_visited).length
}

function visibleEvents(c) {
  const evs = c.recent_events || []
  return expandedEvents.value[c.id] ? evs : evs.slice(0, EVENTS_VISIBLE)
}

const totalStudents = computed(() =>
  classes.value.reduce((n, c) => n + (c.student_count || 0), 0) + unassigned.value.length
)
const hasContent = computed(() => classes.value.length > 0 || unassigned.value.length > 0)
</script>

<template>
  <PageHeader
    :title="t('classes.title')"
    :subtitle="t('classes.subtitle')"
    :meta="hasContent ? [
      { label: '班级', value: classes.length },
      { label: '学生', value: totalStudents },
    ] : []"
  >
    <template #actions>
      <button class="btn btn--primary" @click="showCreate = !showCreate">
        <Icon :name="showCreate ? 'close' : 'plus'" :size="15" />
        {{ showCreate ? t("action.cancel") : t("classes.create") }}
      </button>
    </template>
  </PageHeader>

  <!-- 创建表单放在状态容器之外：空列表时也要能随页头按钮展开 -->
  <div v-if="showCreate" class="card" style="max-width: 620px; margin-bottom: var(--sp-5)">
    <div class="card__head">
      <h2 class="card__title"><Icon name="building" :size="16" /> {{ t("classes.create") }}</h2>
    </div>
    <form class="card__body" @submit.prevent="createClass">
      <div class="form-grid">
        <FormField :label="t('classes.name')" required>
          <input v-model="createForm.name" class="input" type="text" maxlength="60" />
        </FormField>
        <FormField :label="t('classes.year')" hint="跨年的学年，比如 2025/2026">
          <input v-model="createForm.academic_year" class="input" type="text" />
        </FormField>
      </div>

      <p v-if="createError" class="field__error" style="margin-bottom: 12px">
        <Icon name="alert-circle" :size="13" /> {{ createError }}
      </p>

      <div class="form-actions">
        <button type="submit" class="btn btn--primary" :disabled="creating">
          <span v-if="creating" class="spinner" />
          {{ creating ? t("classes.creating") : t("classes.create") }}
        </button>
        <button type="button" class="btn btn--ghost" @click="showCreate = false">
          {{ t("action.cancel") }}
        </button>
      </div>
    </form>
  </div>

  <AsyncState
    :loading="loading"
    :error="error"
    :empty="!loading && !hasContent"
    :empty-title="t('classes.emptyTitle')"
    :empty-desc="t('classes.emptyDesc')"
    empty-icon="building"
    @retry="load"
  >
    <div class="grid grid--2">
      <router-link
        v-for="c in classes"
        :key="c.id"
        :to="`/classes/${c.id}`"
        class="card card--link"
      >
        <div class="card__head">
          <div class="grow">
            <h2 class="card__title" style="font-size: 16px">{{ c.name }}</h2>
            <p class="card__desc">
              {{ c.academic_year }}
              · {{ t("profile.studentsCount", { n: c.student_count }) }}
              <template v-if="c.student_count">
                · {{ t("classes.visitedSummary", { n: visitedCount(c), total: c.student_count }) }}
              </template>
            </p>
          </div>
          <Icon name="chevron-right" :size="16" style="color: var(--muted); flex-shrink: 0" />
        </div>

        <div class="card__body">
          <div v-if="avgSummary(c).length" class="stack" style="gap: 8px">
            <span class="field__hint">{{ t("classes.avgLabel") }}</span>
            <div class="row-wrap">
              <span v-for="a in avgSummary(c)" :key="a.sub" class="pill pill--outline">
                {{ a.label }}
                <b class="tnum">{{ a.avg }}</b>
                <span
                  v-if="a.delta !== null"
                  class="tnum"
                  :style="{ color: a.delta >= 0 ? 'var(--ok)' : 'var(--warn)' }"
                >
                  {{ a.delta > 0 ? "↑" : "↓" }}{{ Math.abs(a.delta) }}
                </span>
              </span>
            </div>
          </div>
          <p v-else class="state__desc" style="margin: 0">{{ t("classdetail.noScores") }}</p>

          <div
            v-if="(c.recent_events || []).length"
            class="stack"
            style="gap: 8px; margin-top: 14px; padding-top: 14px; border-top: 1px solid var(--line)"
          >
            <span class="field__hint">{{ t("classes.recentEvents") }}</span>
            <div class="feed" @click.stop>
              <FeedEventItem
                v-for="ev in visibleEvents(c)"
                :key="`e${ev.id}`"
                :event="ev"
                student-first
              />
            </div>
            <button
              v-if="(c.recent_events || []).length > EVENTS_VISIBLE || expandedEvents[c.id]"
              type="button"
              class="btn btn--sm btn--quiet"
              style="align-self: flex-start"
              @click.prevent="expandedEvents[c.id] = !expandedEvents[c.id]"
            >
              {{ expandedEvents[c.id] ? t("action.collapse") : t("classes.showAllEvents") }}
            </button>
          </div>
        </div>
      </router-link>
    </div>

    <section v-if="unassigned.length" class="card class-unassigned" style="margin-top: var(--sp-5)">
      <div class="card__head">
        <div class="grow">
          <h2 class="card__title" style="font-size: 16px">{{ t("students.ungrouped") }}</h2>
          <p class="card__desc">
            {{ t("profile.studentsCount", { n: unassigned.length }) }}
            · {{ t("classes.unassignedHint") }}
          </p>
        </div>
        <router-link to="/students" class="btn btn--sm btn--ghost">
          {{ t("classes.viewUnassigned") }}
        </router-link>
      </div>
      <div class="card__body card__body--tight">
        <div class="chips">
          <router-link
            v-for="s in unassigned"
            :key="s.id"
            :to="`/students/${s.id}`"
            class="chip"
          >
            {{ s.name }}
            <span class="muted tnum" style="font-size: 12px">{{ s.admission_no }}</span>
          </router-link>
        </div>
      </div>
    </section>
  </AsyncState>
</template>
