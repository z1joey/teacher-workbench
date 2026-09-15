<script setup>
// 数据管理：花名册导入导出（Excel）。只导入学生，不创建班级。
// 数据入口收敛到个人中心，本组件作为其内嵌区块使用（无独立页头）。
import { computed, onMounted, ref } from "vue"
import Icon from "../components/Icon.vue"
import AsyncState from "../components/AsyncState.vue"
import FormField from "../components/FormField.vue"
import api, { downloadFile, triggerDownload, uploadFile } from "../api"
import { ask } from "../confirm"
import { notify } from "../feedback"
import { friendlyError, t } from "../strings"

const loading = ref(true)
const error = ref("")
const classes = ref([])
const hasBusinessData = ref(false)

async function loadDemoStatus() {
  try {
    const status = await api.get("/data/demo/status")
    hasBusinessData.value = !!status.has_business_data
  } catch {
    hasBusinessData.value = false
  }
}

async function load() {
  loading.value = true
  error.value = ""
  try {
    classes.value = await api.get("/classes")
    await loadDemoStatus()
  } catch (e) {
    error.value = friendlyError(e)
  } finally {
    loading.value = false
  }
}
onMounted(load)

const rosterClassId = ref("")
const rosterFileInput = ref(null)
const rosterFile = ref(null)
const importing = ref(false)
const rosterResult = ref(null)
// 「更新」里真正改动了资料的学生（姓名/性别/出生日期），供明细展示
const changedRows = computed(() =>
  (rosterResult.value?.rows ?? []).filter((r) => r.status === "updated" && r.changes)
)

function onRosterFile(e) {
  rosterFile.value = e.target.files[0] || null
}

async function importRoster() {
  if (!rosterFile.value) {
    notify({ tone: "warn", title: "请先选择要导入的 Excel 文件" })
    return
  }
  const fields = {}
  if (rosterClassId.value) fields.class_id = rosterClassId.value
  importing.value = true
  rosterResult.value = null
  try {
    rosterResult.value = await uploadFile("/data/import/roster", rosterFile.value, fields)
    const r = rosterResult.value
    if (!r.created && !r.updated && !r.errors.length) {
      notify({ tone: "warn", title: "没有可导入的数据行", detail: "文件里没有同时含学号和姓名的行" })
    } else {
      notify({
        tone: r.errors.length ? "warn" : "ok",
        title: `导入完成：新建 ${r.created} 人` +
          (r.updated ? `，更新 ${r.updated} 人（按学号匹配已有学生）` : "") +
          (r.errors.length ? `，${r.errors.length} 行未导入` : ""),
      })
    }
    await load()
  } catch (e) {
    notify({ tone: "danger", title: "导入失败", detail: friendlyError(e) })
  } finally {
    importing.value = false
  }
}

const exportClassId = ref("")
const exportingRoster = ref(false)
const exportingVisits = ref(false)
const exportingScores = ref(false)

// 系统未分班（is_unassigned）：导入默认就落未分班，无需重复列出；
// 0 人时也没有可导出的名单，不进导出选项
const importClassOptions = computed(() =>
  classes.value.filter((c) => !c.is_unassigned)
)
const exportClassOptions = computed(() =>
  classes.value.filter((c) => !(c.is_unassigned && !c.student_count))
)

function requireExportClass() {
  if (!exportClassId.value) {
    notify({ tone: "warn", title: t("data.exportSelectClass") })
    return false
  }
  return true
}

async function runExport(path, busyRef) {
  if (!requireExportClass()) return
  busyRef.value = true
  try {
    const { blob, filename } = await downloadFile(
      `${path}?class_id=${exportClassId.value}`
    )
    triggerDownload(blob, filename)
  } catch (e) {
    notify({ tone: "danger", title: t("data.exportFail"), detail: friendlyError(e) })
  } finally {
    busyRef.value = false
  }
}

async function exportRoster() {
  await runExport("/data/export/roster", exportingRoster)
}

async function exportHomeVisits() {
  await runExport("/data/export/home-visits", exportingVisits)
}

async function exportScores() {
  await runExport("/data/export/scores", exportingScores)
}

async function downloadTemplate() {
  try {
    const { blob, filename } = await downloadFile("/data/export/roster-template")
    triggerDownload(blob, filename)
  } catch (e) {
    notify({ tone: "danger", title: "下载失败", detail: friendlyError(e) })
  }
}

function targetClassLabel(result) {
  if (!result?.target_class) return t("students.ungrouped")
  const c = result.target_class
  return `${c.name}（${c.academic_year}）`
}

const seeding = ref(false)
const resetting = ref(false)

async function loadDemoData() {
  await loadDemoStatus()
  if (hasBusinessData.value) {
    const goReset = await ask({
      title: t("data.demoSeedBlocked"),
      message: t("data.demoSeedMustClearFirst"),
      consequences: [t("data.demoSeedMustClearHint")],
      confirmLabel: t("data.demoReset"),
      cancelLabel: t("action.cancel"),
      tone: "warn",
    })
    if (goReset) await resetApp()
    return
  }

  const ok = await ask({
    title: t("data.demoSeed"),
    message: t("data.demoSeedWarn"),
    consequences: [
      "现有学生、班级、考试、成绩、跟进记录都会被清空并替换为演示内容。",
      "演示数据会绑定到你当前登录的教师账号，无需重新登录。",
    ],
    confirmLabel: t("data.demoSeed"),
    tone: "warn",
  })
  if (!ok) return
  seeding.value = true
  try {
    await api.post("/data/demo/seed")
    notify({ tone: "ok", title: t("data.demoSeedDone"), timeout: 4000 })
    window.location.reload()
  } catch (e) {
    if (e?.status === 409) {
      hasBusinessData.value = true
      notify({ tone: "warn", title: t("data.demoSeedBlocked"), detail: friendlyError(e), timeout: 8000 })
    } else {
      notify({ tone: "error", title: t("data.demoSeedFail"), detail: friendlyError(e) })
    }
  } finally {
    seeding.value = false
  }
}

async function resetApp() {
  const ok = await ask({
    title: t("data.demoReset"),
    message: t("data.demoResetWarn"),
    consequences: [
      "删除范围是全部数据，包括你真实录入的学生、成绩和跟进记录，不只是演示数据。",
      "删除后无法恢复；你当前登录的教师账号会保留，无需重新登录。",
    ],
    confirmLabel: t("data.demoReset"),
    confirmWord: t("data.demoResetConfirm"),
  })
  if (!ok) return
  resetting.value = true
  try {
    await api.post("/data/demo/reset")
    notify({ tone: "ok", title: t("data.demoResetDone"), timeout: 4000 })
    rosterResult.value = null
    rosterClassId.value = ""
    exportClassId.value = ""
    hasBusinessData.value = false
    await load()
  } catch (e) {
    notify({ tone: "error", title: t("data.demoResetFail"), detail: friendlyError(e) })
  } finally {
    resetting.value = false
  }
}
</script>

<template>
  <AsyncState :loading="loading" :error="error" :rows="4" @retry="load">
    <div style="display: flex; flex-direction: column; margin-top: var(--sp-5)">
      <div class="card">
        <div class="card__head">
          <h2 class="card__title"><Icon name="upload" :size="16" /> 花名册导入（Excel）</h2>
          <button class="btn btn--sm" @click="downloadTemplate">
            <Icon name="download" :size="13" /> 下载模板
          </button>
        </div>
        <div class="card__body stack" style="gap: 16px">
          <p class="muted" style="margin: 0">
            支持学校下发的通用格式：首行班级标题，第二列表头为
            <b>学号、姓名、性别</b>，可另加出生日期、家庭住址、监护人（姓名 / 电话 / 关系）等列，无法识别的列会自动忽略。
            只导入学生，不会创建班级。默认进入「未分班」；选择班级时会把导入的学生分配到该班。
            学号已存在的学生会被<b>更新</b>；未选班级时不改变其当前班级。
          </p>

          <div class="form-grid">
            <FormField
              label="分配到班级"
              optional
              hint="留空则新建学生进入未分班；已有学生仅更新资料"
            >
              <select v-model="rosterClassId" class="input">
                <option value="">{{ t("students.ungrouped") }}（默认）</option>
                <option v-for="c in importClassOptions" :key="c.id" :value="c.id">
                  {{ c.name }}（{{ c.academic_year }}，{{ c.student_count }} 人）
                </option>
              </select>
            </FormField>
          </div>

          <FormField label="Excel 文件" required hint=".xlsx 格式，支持含备注等额外列">
            <button type="button" class="btn" @click="rosterFileInput?.click()">
              <Icon name="note" :size="15" /> {{ rosterFile ? rosterFile.name : "选择花名册文件（.xlsx）" }}
            </button>
            <input
              ref="rosterFileInput"
              type="file"
              accept=".xlsx"
              class="sr-only"
              @change="onRosterFile"
            />
          </FormField>

          <div>
            <button class="btn btn--primary" :disabled="importing" @click="importRoster">
              <span v-if="importing" class="spinner" />
              <Icon name="upload" :size="15" /> 导入花名册
            </button>
          </div>

          <div v-if="rosterResult" class="stack" style="gap: 10px">
            <div class="row-wrap">
              <span class="pill pill--outline">{{ targetClassLabel(rosterResult) }}</span>
              <span class="pill pill--outline">新建 <b class="tnum">{{ rosterResult.created }}</b></span>
              <span class="pill pill--outline">更新 <b class="tnum">{{ rosterResult.updated }}</b></span>
              <span v-if="rosterResult.errors.length" class="pill pill--outline">
                未导入 <b class="tnum">{{ rosterResult.errors.length }}</b>
              </span>
            </div>
            <p class="muted" style="margin: 0">
              「更新」指文件里的学号已经存在，会覆盖对应学生的资料，不会产生新学生。
            </p>
            <div v-if="changedRows.length" class="table-wrap">
              <table class="table">
                <thead>
                  <tr><th>更新明细</th><th>学号</th><th>改动</th></tr>
                </thead>
                <tbody>
                  <tr v-for="r in changedRows" :key="r.row">
                    <td>{{ r.name }}</td>
                    <td class="tnum">{{ r.admission_no }}</td>
                    <td>{{ r.changes }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <p v-if="rosterResult.ignored_columns.length" class="muted" style="margin: 0">
              已忽略无法识别的列：{{ rosterResult.ignored_columns.join("、") }}
            </p>
            <div v-if="rosterResult.errors.length" class="table-wrap">
              <table class="table">
                <thead>
                  <tr><th>行号</th><th>学号</th><th>姓名</th><th>原因</th></tr>
                </thead>
                <tbody>
                  <tr v-for="r in rosterResult.errors" :key="r.row">
                    <td class="tnum">{{ r.row }}</td>
                    <td>{{ r.admission_no || "—" }}</td>
                    <td>{{ r.name || "—" }}</td>
                    <td>{{ r.message }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>

      <div class="card">
        <div class="card__head">
          <h2 class="card__title"><Icon name="download" :size="16" /> {{ t("data.exportTitle") }}</h2>
        </div>
        <div class="card__body stack" style="gap: 16px">
          <p class="muted" style="margin: 0">{{ t("data.exportDesc") }}</p>
          <div class="form-grid">
            <FormField :label="t('data.exportClass')" required>
              <select v-model="exportClassId" class="input">
                <option value="" disabled>{{ t("data.exportClassPlaceholder") }}</option>
                <option v-for="c in exportClassOptions" :key="c.id" :value="c.id">
                  {{ c.name }}（{{ c.academic_year }}，{{ c.student_count }} 人）
                </option>
              </select>
            </FormField>
          </div>
          <div class="row-wrap">
            <button class="btn btn--primary" :disabled="exportingRoster" @click="exportRoster">
              <span v-if="exportingRoster" class="spinner" />
              <Icon name="download" :size="15" /> {{ t("data.exportRoster") }}
            </button>
            <button class="btn" :disabled="exportingVisits" @click="exportHomeVisits">
              <span v-if="exportingVisits" class="spinner" />
              <Icon name="download" :size="15" /> {{ t("data.exportVisits") }}
            </button>
            <button class="btn" :disabled="exportingScores" @click="exportScores">
              <span v-if="exportingScores" class="spinner" />
              <Icon name="download" :size="15" /> {{ t("data.exportScores") }}
            </button>
          </div>
        </div>
      </div>

      <div class="card card--danger">
        <div class="card__head">
          <div>
            <h2 class="card__title"><Icon name="database" :size="16" /> {{ t("data.demoTitle") }}</h2>
            <p class="card__desc">{{ t("data.demoSub") }}</p>
          </div>
        </div>
        <div class="card__body stack" style="gap: 16px">
          <p class="muted" style="margin: 0">
            {{ t("data.demoBody") }}
          </p>
          <p style="margin: 0; color: var(--danger); font-size: 13px; font-weight: 500">
            {{ t("data.demoResetHint") }}
          </p>
          <div class="row-wrap">
            <button class="btn btn--primary" :disabled="seeding || resetting" @click="loadDemoData">
              <span v-if="seeding" class="spinner" />
              <Icon name="refresh" :size="15" /> {{ t("data.demoSeed") }}
            </button>
            <button class="btn btn--danger-solid" :disabled="seeding || resetting" @click="resetApp">
              <span v-if="resetting" class="spinner" />
              <Icon name="trash" :size="15" /> {{ t("data.demoReset") }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </AsyncState>
</template>
