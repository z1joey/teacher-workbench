<script setup>
// 考试列表：进行中/未来的考试给全卡科目满分；已结束的默认折叠成一行，
// 展开后仍可点进详情（不做置灰/透明处理）。
import { computed, onMounted, ref } from "vue"
import Icon from "../components/Icon.vue"
import PageHeader from "../components/PageHeader.vue"
import AsyncState from "../components/AsyncState.vue"
import api from "../api"
import { formatDateRange, friendlyError, subject, subjectColor, t, todayStr } from "../strings"

const exams = ref([])
const loading = ref(true)
const error = ref("")
const showPast = ref(false)

async function load() {
  loading.value = true
  error.value = ""
  try {
    exams.value = await api.get("/exams")
  } catch (e) {
    error.value = friendlyError(e)
  } finally {
    loading.value = false
  }
}
onMounted(load)

// 已结束 = 最后一天（无结束日期即考试当天）早于今天；进行中/未来的不算。
// 全部学生参与者都已毕业的考试也视为结束。
function isPast(e) {
  return (e.end_date || e.exam_date) < todayStr() || e.students_graduated === true
}

const activeExams = computed(() => exams.value.filter((e) => !isPast(e)))
const pastExams = computed(() => exams.value.filter(isPast))
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

    <div v-if="activeExams.length" class="grid grid--2">
      <router-link
        v-for="e in activeExams"
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
              {{ subject(s.subject) }} · {{ s.full_score }}
            </span>
          </div>
        </div>
      </router-link>
    </div>

    <!-- 已结束的考试：默认折叠，不做透明置灰，展开后卡片照常 -->
    <section v-if="pastExams.length" style="margin-top: var(--sp-5)">
      <button type="button" class="btn btn--sm btn--quiet" @click="showPast = !showPast">
        <Icon :name="showPast ? 'chevron-up' : 'chevron-down'" :size="14" />
        {{ t("exams.pastSection") }}
        <span class="pill pill--muted pill--count">{{ pastExams.length }}</span>
      </button>
      <div v-if="showPast" class="grid grid--2" style="margin-top: var(--sp-4)">
        <router-link
          v-for="e in pastExams"
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
                {{ subject(s.subject) }} · {{ s.full_score }}
              </span>
            </div>
          </div>
        </router-link>
      </div>
    </section>
  </AsyncState>
</template>
