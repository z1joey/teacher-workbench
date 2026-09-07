<script setup>
// 考试列表：每张卡直接给出科目和满分。
import { onMounted, ref } from "vue"
import Icon from "../components/Icon.vue"
import PageHeader from "../components/PageHeader.vue"
import AsyncState from "../components/AsyncState.vue"
import api from "../api"
import { formatDateRange, friendlyError, subject, subjectColor, t } from "../strings"

const exams = ref([])
const loading = ref(true)
const error = ref("")

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

    <div v-if="exams.length" class="grid grid--2">
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
