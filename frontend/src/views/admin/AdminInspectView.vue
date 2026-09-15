<script setup>
import { onMounted, ref } from "vue"
import api from "../../api"
import AdminCellDetailModal from "../../components/admin/AdminCellDetailModal.vue"
import AdminCompactCell from "../../components/admin/AdminCompactCell.vue"
import Icon from "../../components/Icon.vue"
import PageHeader from "../../components/PageHeader.vue"
import { notify } from "../../feedback"
import { friendlyError, t } from "../../strings"
import { cellPreview, useAdminCellDetail } from "./adminTable"

const INSPECT_PAGE_SIZE = 20

const { cellDetail, openCellDetail, closeCellDetail } = useAdminCellDetail()

const tables = ref([])
const loadingTables = ref(true)
const selectedTable = ref("")
const page = ref(1)
const inspectResult = ref(null)
const inspectLoading = ref(false)

async function loadTables() {
  loadingTables.value = true
  page.value = 1
  inspectResult.value = null
  closeCellDetail()
  try {
    const res = await api.get("/admin/inspect/tables")
    tables.value = res.tables || []
    if (tables.value.length) {
      selectedTable.value = tables.value.includes("person") ? "person" : tables.value[0]
      await loadPage()
    } else {
      selectedTable.value = ""
    }
  } catch (e) {
    notify({ tone: "error", title: "表列表加载失败", detail: friendlyError(e) })
    tables.value = []
  }
  loadingTables.value = false
}

async function selectTable(tbl) {
  if (selectedTable.value === tbl) return
  selectedTable.value = tbl
  page.value = 1
  await loadPage()
}

async function loadPage(nextPage = page.value) {
  if (!selectedTable.value) return
  page.value = nextPage
  inspectLoading.value = true
  closeCellDetail()
  try {
    inspectResult.value = await api.post("/admin/inspect", {
      table: selectedTable.value,
      page: page.value,
    })
  } catch (e) {
    notify({ tone: "error", title: "数据加载失败", detail: friendlyError(e) })
  } finally {
    inspectLoading.value = false
  }
}

function rowLabel(ri) {
  return `第 ${(page.value - 1) * INSPECT_PAGE_SIZE + ri + 1} 行`
}

function rowCells(row, columns) {
  return row.map((cell, ci) => ({
    column: columns[ci],
    cell,
    ...cellPreview(cell),
  }))
}

onMounted(loadTables)
</script>

<template>
  <PageHeader :title="t('admin.sectionInspect')" :subtitle="t('admin.subtitleInspect')" />

  <div v-if="loadingTables" class="segmented-scroll">
    <div class="skeleton skeleton--row" style="height: 34px; width: min(100%, 480px)" />
  </div>
  <div v-else-if="tables.length" class="segmented-scroll">
    <div class="segmented" role="radiogroup" :aria-label="t('admin.inspectTable')">
      <button
        v-for="tbl in tables"
        :key="tbl"
        type="button"
        class="segmented__item"
        :class="{ 'is-active': selectedTable === tbl }"
        @click="selectTable(tbl)"
      >
        {{ tbl }}
      </button>
    </div>
  </div>

  <div class="card">
    <div class="card__head">
      <h2 class="card__title"><Icon name="search" :size="16" /> {{ t("admin.sectionInspect") }}</h2>
      <code v-if="selectedTable" class="muted">{{ selectedTable }}</code>
    </div>
    <div class="card__body">
      <p v-if="!loadingTables" class="muted admin-inspect-hint">
        学生、教师等身份都在 <code>person</code> 表（<code>payload.role</code> 区分角色）；事件与成绩在 <code>event</code> 表。点击省略的单元格查看完整内容。
      </p>

      <div v-if="inspectLoading && !inspectResult" class="skeleton skeleton--row" />

      <div v-else-if="inspectResult" class="table-wrap admin-table-wrap">
        <p v-if="!inspectResult.rows.length" class="state__desc" style="padding: 16px 0; text-align: center">
          {{ t("admin.inspectNoData") }}
        </p>
        <table v-else class="table table--admin">
          <thead>
            <tr>
              <th v-for="(col, i) in inspectResult.columns" :key="i">{{ col }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, ri) in inspectResult.rows" :key="ri">
              <td v-for="(item, ci) in rowCells(row, inspectResult.columns)" :key="ci">
                <AdminCompactCell
                  v-if="item.preview !== null"
                  :value="item.cell"
                  :column="item.column"
                  :row-label="rowLabel(ri)"
                  monospace
                  @expand="openCellDetail"
                />
                <span v-else class="pill pill--muted">null</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div
      v-if="inspectResult && inspectResult.total_pages > 0"
      class="card__foot admin-inspect-pager"
    >
      <button
        class="btn btn--sm"
        :disabled="inspectLoading || page <= 1"
        @click="loadPage(page - 1)"
      >
        {{ t("admin.inspectPrev") }}
      </button>
      <span class="muted admin-inspect-pager__meta tnum">
        {{ t("admin.inspectPage", { page, total: inspectResult.total_pages }) }}
        ·
        {{ t("admin.inspectTotal", { total: inspectResult.total }) }}
      </span>
      <button
        class="btn btn--sm"
        :disabled="inspectLoading || page >= inspectResult.total_pages"
        @click="loadPage(page + 1)"
      >
        {{ t("admin.inspectNext") }}
      </button>
    </div>
  </div>

  <AdminCellDetailModal :detail="cellDetail" @close="closeCellDetail" />
</template>
