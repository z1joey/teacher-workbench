<script setup>
import { computed, onMounted, ref } from "vue"
import api from "../../api"
import Icon from "../../components/Icon.vue"
import PageHeader from "../../components/PageHeader.vue"
import { notify } from "../../feedback"
import { friendlyError, t } from "../../strings"

const stats = ref(null)
const loadingStats = ref(true)

async function loadStats() {
  loadingStats.value = true
  try {
    stats.value = await api.get("/admin/stats")
  } catch (e) {
    notify({ tone: "error", title: "概览加载失败", detail: friendlyError(e) })
  }
  loadingStats.value = false
}

onMounted(loadStats)

const tableRows = computed(() => {
  if (!stats.value?.tables) return []
  return Object.entries(stats.value.tables)
    .map(([name, count]) => ({ name, count }))
    .sort((a, b) => b.count - a.count)
})

const overviewCards = computed(() => {
  if (!stats.value) return []
  return [
    { label: t("admin.personsTotal"), value: stats.value.persons_total },
    { label: t("admin.accountsTotal"), value: stats.value.accounts_total },
    { label: t("admin.sessionsActive"), value: stats.value.sessions_active },
  ]
})
</script>

<template>
  <PageHeader :title="t('admin.navOverview')" :subtitle="t('admin.subtitleOverview')">
    <template #actions>
      <button class="btn" @click="loadStats">
        <Icon name="refresh" :size="15" /> {{ t("admin.refresh") }}
      </button>
    </template>
  </PageHeader>

  <div class="card">
    <div class="card__head">
      <h2 class="card__title"><Icon name="chart" :size="16" /> {{ t("admin.sectionOverview") }}</h2>
    </div>
    <div class="card__body">
      <div v-if="loadingStats" class="stack">
        <div class="skeleton skeleton--row" />
      </div>
      <template v-else-if="stats">
        <div class="stat-grid">
          <div v-for="s in overviewCards" :key="s.label" class="stat">
            <div class="stat__label">{{ s.label }}</div>
            <div class="stat__value tnum">{{ s.value }}</div>
          </div>
        </div>

        <h3 class="section-title" style="margin: 20px 0 12px">{{ t("admin.dbTables") }}</h3>
        <div class="table-wrap admin-table-wrap">
          <table class="table table--admin">
            <thead>
              <tr>
                <th>{{ t("admin.table") }}</th>
                <th class="cell-num">{{ t("admin.rows") }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="r in tableRows" :key="r.name">
                <td data-label="表名"><code>{{ r.name }}</code></td>
                <td data-label="行数" class="cell-num tnum">{{ r.count }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p class="stat__sub" style="margin-top: 12px">{{ t("admin.dbDriver") }}：{{ stats.database }}</p>
      </template>
    </div>
  </div>
</template>
