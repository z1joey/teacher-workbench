<script setup>
// 监护人详情：联系方式与名下全部被监护人。同一位监护人（相同手机号）
// 关联多个学生时，这里会一并列出。
import { onMounted, ref } from "vue"
import Icon from "../components/Icon.vue"
import PageHeader from "../components/PageHeader.vue"
import AsyncState from "../components/AsyncState.vue"
import api from "../api"
import { friendlyError, t } from "../strings"

const props = defineProps({
  id: { type: String, required: true },
})

const guardian = ref(null)
const loading = ref(true)
const error = ref("")
const notFound = ref(false)

async function load() {
  loading.value = true
  error.value = ""
  try {
    guardian.value = await api.get(`/guardians/${props.id}`)
  } catch (e) {
    if (/not found/i.test(e.message || "")) notFound.value = true
    else error.value = friendlyError(e)
  } finally {
    loading.value = false
  }
}
onMounted(load)
</script>

<template>
  <!-- 监护人已被删除：给出明确出路 -->
  <div v-if="notFound" class="nf-wrap">
    <div class="nf-board">
      <Icon name="alert" :size="30" />
      <p class="nf-title">{{ t("nf.guardianGone") }}</p>
      <p class="nf-sub">{{ t("nf.guardianGoneSub") }}</p>
    </div>
    <div class="nf-actions">
      <router-link to="/students">
        <button class="btn btn--primary">{{ t("nf.backStudents") }}</button>
      </router-link>
    </div>
  </div>

  <template v-else>
    <PageHeader
      :title="guardian?.name ?? ''"
      :subtitle="t('guardian.subtitle')"
      :meta="[
        { label: t('guardian.phone'), value: guardian?.phone || t('common.none') },
        { label: t('guardian.wardCount'), value: guardian?.wards.length ?? 0 },
      ]"
    />

    <AsyncState :loading="loading" :error="error" :rows="3" @retry="load">
      <div class="card">
        <div class="card__head">
          <div>
            <h2 class="card__title"><Icon name="users" :size="16" /> {{ t("guardian.wards") }}</h2>
            <p class="card__desc">{{ t("guardian.wardsSub") }}</p>
          </div>
        </div>
        <div class="card__body card__body--tight">
          <div class="feed">
            <div v-for="w in guardian?.wards ?? []" :key="w.id" class="feed__item">
              <span class="feed__dot" style="background: #2e6ba8">
                <Icon name="user" :size="13" />
              </span>
              <div class="feed__body">
                <div class="feed__head">
                  <span>
                    <router-link :to="`/students/${w.id}`">{{ w.name }}</router-link>
                    <template v-if="w.relationship"> · {{ w.relationship }}</template>
                    <template v-if="w.class"> · {{ w.class.name }}</template>
                  </span>
                  <span class="muted tnum">{{ w.admission_no }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </AsyncState>
  </template>
</template>
