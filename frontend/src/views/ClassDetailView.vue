<script setup>
// 班级详情：趋势图 + 学生名单 + 各科平均。编辑就地展开，删除走撤销窗口。
import { computed, onMounted, ref, watch } from "vue"
import { useRouter } from "vue-router"
import api from "../api"
import Icon from "../components/Icon.vue"
import PageHeader from "../components/PageHeader.vue"
import AsyncState from "../components/AsyncState.vue"
import FormField from "../components/FormField.vue"
import LineChart from "../components/LineChart.vue"
import { ask } from "../confirm"
import { notify, runUndoable } from "../feedback"
import { setPageTitle } from "../title"
import { friendlyError, genderLabel, subject, subjectColor, t } from "../strings"

const props = defineProps({ id: { type: String, required: true } })
const router = useRouter()

const detail = ref(null)
const loading = ref(true)
const error = ref("")

const editing = ref(false)
const editSaving = ref(false)
const editError = ref("")
const editForm = ref({})

function emptyEditForm(c) {
  return {
    name: c.name || "",
    academic_year: c.academic_year,
  }
}

async function load() {
  loading.value = true
  error.value = ""
  try {
    detail.value = await api.get(`/classes/${props.id}`)
    setPageTitle(detail.value.class.name)
  } catch (e) {
    error.value = friendlyError(e)
  } finally {
    loading.value = false
  }
}
onMounted(load)
watch(() => props.id, load)

function startEdit() {
  editing.value = true
  editError.value = ""
  editForm.value = emptyEditForm(detail.value.class)
}
function cancelEdit() {
  editing.value = false
  editForm.value = {}
  editError.value = ""
}

async function saveEdit() {
  editError.value = ""
  if (!editForm.value.name.trim()) {
    editError.value = t("classes.nameRequired")
    return
  }
  editSaving.value = true
  try {
    const updated = await api.patch(`/classes/${props.id}`, {
      name: editForm.value.name.trim(),
      academic_year: editForm.value.academic_year.trim(),
    })
    detail.value.class = { ...detail.value.class, ...updated }
    editing.value = false
    notify({ tone: "ok", title: t("common.saved"), timeout: 2400 })
    await load()
  } catch (e) {
    editError.value = friendlyError(e)
  } finally {
    editSaving.value = false
  }
}

async function removeClass() {
  const name = detail.value.class.name
  const ok = await ask({
    title: `删除班级「${name}」？`,
    consequences: [t("classes.deleteConfirm"), "班级里还有学生时，系统会拒绝删除。"],
    confirmLabel: t("action.delete"),
  })
  if (!ok) return

  runUndoable({
    title: `已删除班级「${name}」`,
    run: () => api.delete(`/classes/${props.id}`),
    onDone: () => router.replace("/classes"),
  })
}

// 语数英 120 分、其余 100 分——原始分同轴比较不公平，统一画成得分率（%）
const trendChart = computed(() => {
  if (!detail.value || !detail.value.trend.exams.length) return null
  const series = detail.value.trend.series.map((s) => {
    const full = s.full_score || 100
    return {
      key: s.subject,
      label: subject(s.subject),
      color: subjectColor(s.subject),
      values: s.values.map((v) => (v == null ? null : Math.round((v / full) * 1000) / 10)),
    }
  })
  return {
    labels: detail.value.trend.exams.map((e) => e.name),
    dates: detail.value.trend.exams.map((e) => e.exam_date),
    series,
    yMax: 100,
    formatTip: (s, pct, i) => {
      const orig = detail.value.trend.series.find((x) => x.subject === s.key)
      const raw = orig ? orig.values[i] : null
      const full = orig ? orig.full_score || 100 : 100
      return raw != null ? `${pct}%（${raw}/${full} 分）` : `${pct}%`
    },
  }
})

const hasScores = computed(() => detail.value && detail.value.averages.length > 0)

function fmtPct(score, full) {
  return full ? Math.round((score / full) * 100) : 0
}
</script>

<template>
  <AsyncState :loading="loading" :error="error" :rows="4" @retry="load">
    <template v-if="detail">
      <PageHeader
        :title="detail.class.name"
        :subtitle="detail.class.academic_year"
        :meta="[
          { label: '学生', value: detail.students.length },
        ]"
      >
        <template #actions>
          <button class="btn" @click="startEdit">
            <Icon name="pencil" :size="15" /> {{ t("action.edit") }}
          </button>
          <button class="btn btn--danger" @click="removeClass">
            <Icon name="trash" :size="15" /> {{ t("action.delete") }}
          </button>
        </template>
      </PageHeader>

      <!-- 就地编辑 -->
      <div v-if="editing" class="card" style="max-width: 720px">
        <div class="card__head">
          <h2 class="card__title">{{ t("action.edit") }} · {{ detail.class.name }}</h2>
        </div>
        <form class="card__body" @submit.prevent="saveEdit">
          <div class="form-grid">
            <FormField :label="t('classes.name')" required>
              <input v-model="editForm.name" class="input" type="text" maxlength="60" />
            </FormField>
            <FormField :label="t('classes.year')">
              <input v-model="editForm.academic_year" class="input" type="text" />
            </FormField>
          </div>

          <p v-if="editError" class="field__error" style="margin-bottom: 12px">
            <Icon name="alert-circle" :size="13" /> {{ editError }}
          </p>

          <div class="form-actions">
            <button type="submit" class="btn btn--primary" :disabled="editSaving">
              <span v-if="editSaving" class="spinner" />
              {{ editSaving ? t("action.saving") : t("action.save") }}
            </button>
            <button type="button" class="btn btn--ghost" @click="cancelEdit">
              {{ t("action.cancel") }}
            </button>
          </div>
        </form>
      </div>

      <div class="split">
        <div>
          <div class="card">
            <div class="card__head">
              <div>
                <h2 class="card__title"><Icon name="trending" :size="16" /> {{ t("classdetail.trendTitle") }}</h2>
                <p class="card__desc">{{ t("classdetail.trendSub") }}</p>
              </div>
            </div>
            <div class="card__body">
              <p v-if="!trendChart || !trendChart.series.length" class="state__desc" style="text-align: center; padding: 16px 0">
                {{ t("classdetail.noScores") }}
              </p>
              <LineChart
                v-else
                :labels="trendChart.labels"
                :dates="trendChart.dates"
                :series="trendChart.series"
                :y-max="trendChart.yMax"
                :format-tip="trendChart.formatTip"
              />
            </div>
          </div>

          <div class="card">
            <div class="card__head">
              <h2 class="card__title"><Icon name="users" :size="16" /> {{ t("classdetail.roster") }}</h2>
              <span class="pill pill--muted pill--count">{{ detail.students.length }}</span>
            </div>
            <div class="card__body">
              <div v-if="detail.students.length" class="chips">
                <router-link
                  v-for="s in detail.students"
                  :key="s.id"
                  :to="`/students/${s.id}`"
                  class="chip"
                  :title="s.admission_no"
                >
                  {{ s.name }}
                  <span class="muted" style="font-size: 12px">{{ genderLabel(s.gender) }}</span>
                </router-link>
              </div>
              <p v-else class="state__desc" style="text-align: center; padding: 16px 0">
                {{ t("classes.noStudents") }}
              </p>
            </div>
          </div>
        </div>

        <div class="card">
          <div class="card__head">
            <h2 class="card__title"><Icon name="chart" :size="16" /> {{ t("classdetail.averages") }}</h2>
          </div>
          <div class="card__body">
            <p v-if="!hasScores" class="state__desc" style="text-align: center; padding: 16px 0">
              {{ t("classdetail.noScores") }}
            </p>
            <div v-for="a in detail.averages" :key="a.subject" class="stat stat--plain">
              <div class="stat__label">{{ subject(a.subject) }}</div>
              <div class="stat__value tnum">{{ a.avg ?? t("common.none") }}</div>
              <div class="stat__sub">
                {{ t("exam.outOf") }} {{ a.full_score }}（{{ fmtPct(a.avg, a.full_score) }}%） ·
                {{ t("exam.exams", { count: a.count }) }}
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>
  </AsyncState>
</template>
