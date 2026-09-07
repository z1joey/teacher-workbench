<script setup>
// 数据管理：花名册导入导出（Excel）。只导入学生，不创建班级。
import { onMounted, ref } from "vue"
import Icon from "../components/Icon.vue"
import PageHeader from "../components/PageHeader.vue"
import AsyncState from "../components/AsyncState.vue"
import FormField from "../components/FormField.vue"
import api, { downloadFile, setToken, triggerDownload, uploadFile } from "../api"
import { ask } from "../confirm"
import { notify } from "../feedback"
import { friendlyError, t } from "../strings"

const loading = ref(true)
const error = ref("")
const classes = ref([])

async function load() {
  loading.value = true
  error.value = ""
  try {
    classes.value = await api.get("/classes")
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
    notify({
      tone: r.errors.length ? "warn" : "ok",
      title: `导入完成：新建 ${r.created} 人，更新 ${r.updated} 人` +
        (r.errors.length ? `，${r.errors.length} 行未导入` : ""),
    })
    await load()
  } catch (e) {
    notify({ tone: "danger", title: "导入失败", detail: friendlyError(e) })
  } finally {
    importing.value = false
  }
}

const exportClassId = ref("")
const exportingRoster = ref(false)

async function exportRoster() {
  if (!exportClassId.value) {
    notify({ tone: "warn", title: "请选择要导出的班级" })
    return
  }
  exportingRoster.value = true
  try {
    const { blob, filename } = await downloadFile(
      `/data/export/roster?class_id=${exportClassId.value}`
    )
    triggerDownload(blob, filename)
  } catch (e) {
    notify({ tone: "danger", title: "导出失败", detail: friendlyError(e) })
  } finally {
    exportingRoster.value = false
  }
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

function goLogin() {
  setToken(null)
  window.location.href = `${import.meta.env.BASE_URL}login`
}

async function loadDemoData() {
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
    notify({ tone: "error", title: t("data.demoSeedFail"), detail: friendlyError(e) })
  } finally {
    seeding.value = false
  }
}

async function resetApp() {
  const ok = await ask({
    title: t("data.demoReset"),
    message: t("data.demoResetWarn"),
    consequences: [
      "所有学生、班级、考试、成绩、跟进记录都会消失。",
      "账号也会一并清空，你需要重新登录或加载演示数据。",
    ],
    confirmLabel: t("data.demoReset"),
    confirmWord: t("data.demoResetConfirm"),
  })
  if (!ok) return
  resetting.value = true
  try {
    await api.post("/data/demo/reset")
    notify({ tone: "ok", title: t("data.demoResetDone"), timeout: 4000 })
    goLogin()
  } catch (e) {
    notify({ tone: "error", title: t("data.demoResetFail"), detail: friendlyError(e) })
  } finally {
    resetting.value = false
  }
}
</script>

<template>
  <PageHeader
    title="数据"
    subtitle="用 Excel 花名册批量导入、导出学生"
  >
    <template #actions>
      <button class="btn" @click="downloadTemplate">
        <Icon name="note" :size="15" /> 花名册模板
      </button>
    </template>
  </PageHeader>

  <AsyncState :loading="loading" :error="error" :rows="4" @retry="load">
    <div class="stack" style="gap: 20px">
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
            <b>学号、姓名、性别</b>（可加出生日期等列，无法识别的列会自动忽略）。
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
                <option v-for="c in classes" :key="c.id" :value="c.id">
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
          <h2 class="card__title"><Icon name="download" :size="16" /> 花名册导出（Excel）</h2>
        </div>
        <div class="card__body stack" style="gap: 16px">
          <p class="muted" style="margin: 0">
            按当前班级名单导出 .xlsx（学号 / 姓名 / 性别），格式与导入格式一致。
          </p>
          <div class="form-grid">
            <FormField label="班级" required>
              <select v-model="exportClassId" class="input">
                <option value="" disabled>选择班级</option>
                <option v-for="c in classes" :key="c.id" :value="c.id">
                  {{ c.name }}（{{ c.academic_year }}，{{ c.student_count }} 人）
                </option>
              </select>
            </FormField>
          </div>
          <div>
            <button class="btn btn--primary" :disabled="exportingRoster" @click="exportRoster">
              <span v-if="exportingRoster" class="spinner" />
              <Icon name="download" :size="15" /> 导出花名册
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
