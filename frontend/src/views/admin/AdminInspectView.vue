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

const { cellDetail, openCellDetail, closeCellDetail } = useAdminCellDetail()

const tables = ref([])
const loadingTables = ref(true)
const selectedTable = ref("")
const inspectLimit = ref(20)
const inspectResult = ref(null)
const inspectLoading = ref(false)

async function loadTables() {
  loadingTables.value = true
  try {
    const res = await api.get("/admin/inspect/tables")
    tables.value = res.tables || []
    if (!selectedTable.value && tables.value.length) {
      selectedTable.value = tables.value.includes("person") ? "person" : tables.value[0]
    }
  } catch (e) {
    notify({ tone: "error", title: "表列表加载失败", detail: friendlyError(e) })
    tables.value = []
  }
  loadingTables.value = false
}

async function runInspect() {
  if (!selectedTable.value) return
  inspectLoading.value = true
  inspectResult.value = null
  closeCellDetail()
  try {
    inspectResult.value = await api.post("/admin/inspect", {
      table: selectedTable.value,
      limit: inspectLimit.value,
    })
  } catch (e) {
    notify({ tone: "error", title: "预览失败", detail: friendlyError(e) })
  } finally {
    inspectLoading.value = false
  }
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

  <div class="card">
    <div class="card__head">
      <h2 class="card__title"><Icon name="search" :size="16" /> {{ t("admin.sectionInspect") }}</h2>
    </div>
    <div class="card__body">
      <div class="admin-inspect-form">
        <div class="field">
          <span class="field__label">{{ t("admin.inspectTable") }}</span>
          <select v-model="selectedTable" class="select" :disabled="loadingTables || !tables.length">
            <option v-if="loadingTables" value="" disabled>加载中…</option>
            <option v-else-if="!tables.length" value="" disabled>暂无可用表</option>
            <option v-for="tbl in tables" :key="tbl" :value="tbl">{{ tbl }}</option>
          </select>
        </div>

        <div class="admin-inspect-actions">
          <div class="field admin-inspect-actions__limit">
            <span class="field__label">{{ t("admin.inspectLimit") }}</span>
            <input v-model="inspectLimit" class="input" type="number" min="1" max="100" />
          </div>
          <button class="btn btn--primary" :disabled="inspectLoading || !selectedTable" @click="runInspect">
            <span v-if="inspectLoading" class="spinner" />
            {{ inspectLoading ? t("admin.loading") : t("admin.inspectRun") }}
          </button>
        </div>

        <p v-if="!loadingTables" class="muted admin-inspect-hint">
          学生、教师等身份都在 <code>person</code> 表（<code>payload.role</code> 区分角色）；事件与成绩在 <code>event</code> 表。点击省略的单元格查看完整内容。
        </p>
      </div>

      <div v-if="inspectResult" class="table-wrap admin-table-wrap">
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
                  :row-label="`第 ${ri + 1} 行`"
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
  </div>

  <AdminCellDetailModal :detail="cellDetail" @close="closeCellDetail" />
</template>
