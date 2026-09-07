<script setup>
// 考试列表：按个人中心设置的学期分组；每张卡直接给出科目和满分。
import { computed, onMounted, ref } from "vue"
import Icon from "../components/Icon.vue"
import PageHeader from "../components/PageHeader.vue"
import AsyncState from "../components/AsyncState.vue"
import api from "../api"
import {
  formatDateRange,
  friendlyError,
  groupExamsBySemester,
  subject,
  subjectColor,
  t,
} from "../strings"

const exams = ref([])
const semesters = ref([])
const loading = ref(true)
const error = ref("")

const examGroups = computed(() => groupExamsBySemester(exams.value, semesters.value))
const hasSemesters = computed(() => semesters.value.length > 0)

async function load() {
  loading.value = true
  error.value = ""
  try {
    const [examList, profile] = await Promise.all([api.get("/exams"), api.get("/profile")])
    exams.value = examList
    semesters.value = profile.semesters || []
  } catch (e) {
    error.value = friendlyError(e)
  } finally {
    loading.value = false
  }
}
onMounted(load)
</script>

<template>
  <PageHeader
    :title="t('exams.title')"
    :subtitle="t('exams.subtitle', { count: exams.length })"
  >
    <template #actions>
      <router-link to="/exams/new">
        <button class="btn btn--primary"><Icon name="plus" :size="15" /> {{ t("exams.create") }}</button>
      </router-link>
    </template>
  </PageHeader>

  <AsyncState
    :loading="loading"
    :error="error"
    :empty="!loading && !exams.length"
    :empty-title="t('exams.emptyTitle')"
    :empty-desc="t('exams.emptyDesc')"
    empty-icon="clipboard"
    :rows="3"
    @retry="load"
  >
    <template #emptyAction>
      <router-link to="/exams/new">
        <button class="btn btn--primary"><Icon name="plus" :size="15" /> {{ t("exams.create") }}</button>
      </router-link>
    </template>

    <div v-if="!hasSemesters && exams.length" class="card" style="margin-bottom: var(--sp-3)">
      <div class="card__body row-wrap" style="justify-content: space-between">
        <p class="state__desc" style="margin: 0">{{ t("exams.noSemesters") }}</p>
        <router-link to="/profile">
          <button class="btn btn--sm">{{ t("exams.setupSemesters") }}</button>
        </router-link>
      </div>
    </div>

    <div v-if="hasSemesters" class="stack">
      <section v-for="g in examGroups" :key="g.id" class="exam-group">
        <header class="exam-group__head">
          <div class="grow">
            <h2 class="exam-group__title">{{ g.name }}</h2>
            <p v-if="g.start_date" class="exam-group__range">
              {{ formatDateRange(g.start_date, g.end_date) }}
            </p>
          </div>
          <span class="pill pill--muted pill--count">{{ g.exams.length }}</span>
        </header>
        <div class="grid grid--2">
          <router-link
            v-for="e in g.exams"
            :key="e.id"
            :to="`/exams/${e.id}`"
            class="card card--link"
          >
            <div class="card__head">
              <div class="grow">
                <h3 class="card__title" style="font-size: 16px">{{ e.name }}</h3>
                <p class="card__desc">{{ formatDateRange(e.exam_date, e.end_date) }}</p>
              </div>
              <Icon name="chevron-right" :size="16" style="color: var(--muted)" />
            </div>
            <div class="card__body">
              <div class="chips">
                <span v-for="s in e.subjects" :key="s.id" class="pill pill--outline">
                  <span class="subject-dot" :style="{ background: subjectColor(s.subject, s.color) }" />
                  {{ subject(s.subject) }} · {{ t("exams.fullScore") }} {{ s.full_score }}
                </span>
              </div>
            </div>
          </router-link>
        </div>
      </section>
    </div>

    <div v-else-if="exams.length" class="grid grid--2">
      <router-link
        v-for="e in exams"
        :key="e.id"
        :to="`/exams/${e.id}`"
        class="card card--link"
      >
        <div class="card__head">
          <div class="grow">
            <h3 class="card__title" style="font-size: 16px">{{ e.name }}</h3>
            <p class="card__desc">{{ formatDateRange(e.exam_date, e.end_date) }}</p>
          </div>
          <Icon name="chevron-right" :size="16" style="color: var(--muted)" />
        </div>
        <div class="card__body">
          <div class="chips">
            <span v-for="s in e.subjects" :key="s.id" class="pill pill--outline">
              <span class="subject-dot" :style="{ background: subjectColor(s.subject, s.color) }" />
              {{ subject(s.subject) }} · {{ t("exams.fullScore") }} {{ s.full_score }}
            </span>
          </div>
        </div>
      </router-link>
    </div>
  </AsyncState>
</template>
