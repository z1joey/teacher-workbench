<script setup>
// 班级列表：班均摘要 + 最近事件，点卡片进详情看完整名单。
import { computed, onMounted, ref, watch } from "vue"
import { useRoute } from "vue-router"
import Icon from "../components/Icon.vue"
import PageHeader from "../components/PageHeader.vue"
import AsyncState from "../components/AsyncState.vue"
import FormField from "../components/FormField.vue"
import FeedEventItem from "../components/FeedEventItem.vue"
import api from "../api"
import { notify } from "../feedback"
import { friendlyError, genderLabel, subject, COMMON_SUBJECT_KEYS, t } from "../strings"

const route = useRoute()

const classes = ref([])
const unassigned = ref([])
const loading = ref(true)
const error = ref("")

const showCreate = ref(false)
const creating = ref(false)
const createError = ref("")
const createForm = ref(emptyForm())

const EVENTS_VISIBLE = 3
const expandedEvents = ref({})

function emptyForm() {
  return { name: "", academic_year: defaultYear() }
}

function defaultYear() {
  const now = new Date()
  const start = now.getMonth() + 1 >= 8 ? now.getFullYear() : now.getFullYear() - 1
  return `${start}/${start + 1}`
}

async function load() {
  loading.value = true
  error.value = ""
  try {
    const [cs, students] = await Promise.all([
      api.get("/classes"),
      api.get("/students"),
    ])
    classes.value = cs
    unassigned.value = students.filter((s) => s.status === "active" && !s.class)
  } catch (e) {
    error.value = friendlyError(e)
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await load()
  if (route.query.create === "1") showCreate.value = true
})
watch(() => route.query.create, (v) => {
  if (v === "1") showCreate.value = true
})

async function createClass() {
  createError.value = ""
  if (!createForm.value.name.trim()) {
    createError.value = t("classes.nameRequired")
    return
  }
  creating.value = true
  try {
    await api.post("/classes", {
      name: createForm.value.name.trim(),
      academic_year: createForm.value.academic_year.trim(),
    })
    createForm.value = emptyForm()
    showCreate.value = false
    notify({ tone: "ok", title: "班级已创建", timeout: 2600 })
    await load()
  } catch (e) {
    createError.value = friendlyError(e)
  } finally {
    creating.value = false
  }
}

function avgSummary(c) {
  const trend = c.avg_trend || []
  if (!trend.length) return []
  const last = trend[trend.length - 1]
  const prev = trend.length > 1 ? trend[trend.length - 2] : null
  const subs = Object.keys(last.averages).sort((a, b) => {
    const ia = COMMON_SUBJECT_KEYS.indexOf(a)
    const ib = COMMON_SUBJECT_KEYS.indexOf(b)
    return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib)
  })
  return subs.map((sub) => {
    const avg = last.averages[sub]
    const p = prev ? prev.averages[sub] : null
    const delta = p != null && avg != null ? Math.round((avg - p) * 10) / 10 : null
    return { sub, label: subject(sub), avg, delta }
  })
}

function visitedCount(c) {
  return (c.students || []).filter((s) => s.home_visited).length
}

function visibleEvents(c) {
  const evs = c.recent_events || []
  return expandedEvents.value[c.id] ? evs : evs.slice(0, EVENTS_VISIBLE)
}

const totalStudents = computed(() =>
  classes.value.reduce((n, c) => n + (c.student_count || 0), 0) + unassigned.value.length
)
const hasContent = computed(() => classes.value.length > 0 || unassigned.value.length > 0)

// ------------------------------------------------------------------ 拖拽转班

// 正在拖拽的学生 { id, name, from }；from 为班级 id，未分班是 null
const dragStudent = ref(null)
// 当前高亮的投放目标；未分班用 null，和 from 对齐
const dropTargetId = ref(null)
const dropTargetActive = computed(() => dragStudent.value !== null)

function onDragStart(student, fromClassId, ev) {
  dragStudent.value = { id: student.id, name: student.name, from: fromClassId }
  // Firefox 只有 set 了 data 才会真正开始拖拽
  ev.dataTransfer.setData("text/plain", student.name)
  ev.dataTransfer.effectAllowed = "move"
}

function onDragEnd() {
  dragStudent.value = null
  dropTargetId.value = null
}

function onDragLeave(targetId, ev) {
  // 在卡片子元素间移动也会触发 dragleave，只有真正离开卡片才熄灭高亮
  if (!ev.currentTarget.contains(ev.relatedTarget)) {
    if (dropTargetId.value === targetId) dropTargetId.value = null
  }
}

function onDropTo(targetClassId) {
  const s = dragStudent.value
  dropTargetId.value = null
  if (!s || s.from === targetClassId) return // 放回原班级 = 什么都不做
  moveStudent(s, targetClassId)
}

async function moveStudent(s, targetClassId) {
  const target = classes.value.find((c) => c.id === targetClassId)
  const targetName = target ? target.name : t("students.ungrouped")
  try {
    await api.patch(`/students/${s.id}`, { class_id: targetClassId })
    await load()
    notify({
      tone: "ok",
      title: target ? `已把 ${s.name} 移到 ${targetName}` : `已把 ${s.name} 移到未分班`,
      timeout: 3000,
    })
  } catch (e) {
    notify({ tone: "danger", title: "转班失败", detail: friendlyError(e) })
  }
}

// ------------------------------------------------------------------ 座位表

const seatingClass = ref(null) // 正在编辑座位表的班级
const seating = ref(null) // { rows, cols, cells: Array(学生id|null)，行优先
const seatingSaving = ref(false)
const seatingError = ref("")
const seatDrag = ref(null) // { studentId, from: "seat"|"pool", index? }

const studentById = computed(() => {
  const map = new Map()
  for (const s of seatingClass.value?.students || []) map.set(s.id, s)
  return map
})

const poolStudents = computed(() => {
  const seated = new Set((seating.value?.cells ?? []).filter(Boolean))
  return (seatingClass.value?.students || []).filter((s) => !seated.has(s.id))
})

async function openSeating(c) {
  seatingClass.value = c
  seatingError.value = ""
  seatDrag.value = null
  seating.value = null
  try {
    const res = await api.get(`/classes/${c.id}/seating`)
    const rows = res.rows > 0 ? res.rows : Math.max(1, Math.ceil((c.students || []).length / 8))
    const cols = res.cols > 0 ? res.cols : 8
    const cells = Array(rows * cols).fill(null)
    for (const [pos, sid] of Object.entries(res.seats || {})) {
      const i = Number(pos)
      // 转走的学生不再占座
      if (i >= 0 && i < cells.length && studentById.value.has(sid)) cells[i] = sid
    }
    seating.value = { rows, cols, cells }
  } catch (e) {
    seatingError.value = friendlyError(e)
    seating.value = { rows: 4, cols: 8, cells: Array(32).fill(null) }
  }
}

function closeSeating() {
  seatingClass.value = null
  seating.value = null
  seatDrag.value = null
}

function resizeSeating() {
  const s = seating.value
  if (!s) return
  s.rows = Math.min(20, Math.max(1, Math.round(Number(s.rows) || 1)))
  s.cols = Math.min(12, Math.max(1, Math.round(Number(s.cols) || 1)))
  const cells = s.cells.slice(0, s.rows * s.cols)
  while (cells.length < s.rows * s.cols) cells.push(null)
  s.cells = cells
}

function onSeatDragStart(studentId, index, ev) {
  seatDrag.value = { studentId, from: "seat", index }
  ev.dataTransfer.setData("text/plain", studentId)
  ev.dataTransfer.effectAllowed = "move"
}

function onPoolDragStart(studentId, ev) {
  seatDrag.value = { studentId, from: "pool" }
  ev.dataTransfer.setData("text/plain", studentId)
  ev.dataTransfer.effectAllowed = "move"
}

function onDropSeat(index) {
  const d = seatDrag.value
  if (!d) return
  const cells = seating.value.cells
  if (d.from === "seat") {
    if (d.index !== index) {
      // 座位互换：目标座位上的人换到拖拽起点
      ;[cells[index], cells[d.index]] = [cells[d.index], cells[index]]
    }
  } else {
    // 从未安排池入座；目标座位原来的人回到池里
    cells[index] = d.studentId
  }
  seatDrag.value = null
}

function onDropPool() {
  const d = seatDrag.value
  if (!d) return
  if (d.from === "seat") seating.value.cells[d.index] = null
  seatDrag.value = null
}

async function saveSeating() {
  const s = seating.value
  const seats = {}
  s.cells.forEach((sid, i) => {
    if (sid) seats[i] = sid
  })
  seatingSaving.value = true
  seatingError.value = ""
  try {
    await api.put(`/classes/${seatingClass.value.id}/seating`, {
      rows: s.rows,
      cols: s.cols,
      seats,
    })
    notify({ tone: "ok", title: "座位表已保存", timeout: 2600 })
    closeSeating()
  } catch (e) {
    seatingError.value = friendlyError(e)
  } finally {
    seatingSaving.value = false
  }
}
</script>

<template>
  <PageHeader
    :title="t('classes.title')"
    :subtitle="t('classes.subtitle')"
    :meta="hasContent ? [
      { label: '班级', value: classes.length },
      { label: '学生', value: totalStudents },
    ] : []"
  >
    <template #actions>
      <button class="btn btn--primary" @click="showCreate = !showCreate">
        <Icon :name="showCreate ? 'close' : 'plus'" :size="15" />
        {{ showCreate ? t("action.cancel") : t("classes.create") }}
      </button>
    </template>
  </PageHeader>

  <!-- 创建表单放在状态容器之外：空列表时也要能随页头按钮展开 -->
  <div v-if="showCreate" class="card" style="max-width: 620px; margin-bottom: var(--sp-5)">
    <div class="card__head">
      <h2 class="card__title"><Icon name="building" :size="16" /> {{ t("classes.create") }}</h2>
    </div>
    <form class="card__body" @submit.prevent="createClass">
      <div class="form-grid">
        <FormField :label="t('classes.name')" required>
          <input v-model="createForm.name" class="input" type="text" maxlength="60" />
        </FormField>
        <FormField :label="t('classes.year')" hint="跨年的学年，比如 2025/2026">
          <input v-model="createForm.academic_year" class="input" type="text" />
        </FormField>
      </div>

      <p v-if="createError" class="field__error" style="margin-bottom: 12px">
        <Icon name="alert-circle" :size="13" /> {{ createError }}
      </p>

      <div class="form-actions">
        <button type="submit" class="btn btn--primary" :disabled="creating">
          <span v-if="creating" class="spinner" />
          {{ creating ? t("classes.creating") : t("classes.create") }}
        </button>
        <button type="button" class="btn btn--ghost" @click="showCreate = false">
          {{ t("action.cancel") }}
        </button>
      </div>
    </form>
  </div>

  <AsyncState
    :loading="loading"
    :error="error"
    :empty="!loading && !hasContent"
    :empty-title="t('classes.emptyTitle')"
    :empty-desc="t('classes.emptyDesc')"
    empty-icon="building"
    @retry="load"
  >
    <div class="grid grid--2">
      <router-link
        v-for="c in classes"
        :key="c.id"
        :to="`/classes/${c.id}`"
        class="card card--link"
        :class="{ 'card--drop': dropTargetActive && dropTargetId === c.id && dragStudent.from !== c.id }"
        @dragover.prevent="dropTargetId = c.id"
        @dragleave="onDragLeave(c.id, $event)"
        @drop.prevent="onDropTo(c.id)"
      >
        <div class="card__head">
          <div class="grow">
            <h2 class="card__title" style="font-size: 16px">{{ c.name }}</h2>
            <p class="card__desc">
              {{ c.academic_year }}
              · {{ t("profile.studentsCount", { n: c.student_count }) }}
              <template v-if="c.student_count">
                · {{ t("classes.visitedSummary", { n: visitedCount(c), total: c.student_count }) }}
              </template>
            </p>
          </div>
          <button class="btn btn--sm" @click.stop.prevent="openSeating(c)">
            <Icon name="board" :size="14" /> {{ t("classes.seating") }}
          </button>
          <Icon name="chevron-right" :size="16" style="color: var(--muted); flex-shrink: 0" />
        </div>

        <div class="card__body">
          <div v-if="(c.students || []).length" class="chips" style="margin-bottom: 14px">
            <router-link
              v-for="s in c.students"
              :key="s.id"
              :to="`/students/${s.id}`"
              class="chip"
              draggable="true"
              @dragstart="onDragStart(s, c.id, $event)"
              @dragend="onDragEnd"
              @click.stop
            >
              {{ s.name }}
              <span class="muted tnum" style="font-size: 12px">{{ s.admission_no }}</span>
            </router-link>
          </div>

          <div v-if="avgSummary(c).length" class="stack" style="gap: 8px">
            <span class="field__hint">{{ t("classes.avgLabel") }}</span>
            <div class="row-wrap">
              <span v-for="a in avgSummary(c)" :key="a.sub" class="pill pill--outline">
                {{ a.label }}
                <b class="tnum">{{ a.avg }}</b>
                <span
                  v-if="a.delta !== null"
                  class="tnum"
                  :style="{ color: a.delta >= 0 ? 'var(--ok)' : 'var(--warn)' }"
                >
                  {{ a.delta > 0 ? "↑" : "↓" }}{{ Math.abs(a.delta) }}
                </span>
              </span>
            </div>
          </div>
          <p v-else class="state__desc" style="margin: 0">{{ t("classdetail.noScores") }}</p>

          <div
            v-if="(c.recent_events || []).length"
            class="stack"
            style="gap: 8px; margin-top: 14px; padding-top: 14px; border-top: 1px solid var(--line)"
          >
            <span class="field__hint">{{ t("classes.recentEvents") }}</span>
            <div class="feed" @click.stop>
              <FeedEventItem
                v-for="ev in visibleEvents(c)"
                :key="`e${ev.id}`"
                :event="ev"
                student-first
              />
            </div>
            <button
              v-if="(c.recent_events || []).length > EVENTS_VISIBLE || expandedEvents[c.id]"
              type="button"
              class="btn btn--sm btn--quiet"
              style="align-self: flex-start"
              @click.prevent="expandedEvents[c.id] = !expandedEvents[c.id]"
            >
              {{ expandedEvents[c.id] ? t("action.collapse") : t("classes.showAllEvents") }}
            </button>
          </div>
        </div>
      </router-link>
    </div>

    <section
      v-if="unassigned.length"
      class="card class-unassigned"
      :class="{ 'card--drop': dropTargetActive && dragStudent.from !== null }"
      style="margin-top: var(--sp-5)"
      @dragover.prevent="dropTargetId = null"
      @dragleave="onDragLeave(null, $event)"
      @drop.prevent="onDropTo(null)"
    >
      <div class="card__head">
        <div class="grow">
          <h2 class="card__title" style="font-size: 16px">{{ t("students.ungrouped") }}</h2>
          <p class="card__desc">
            {{ t("profile.studentsCount", { n: unassigned.length }) }}
            · {{ t("classes.unassignedHint") }}
          </p>
        </div>
        <router-link to="/students" class="btn btn--sm btn--ghost">
          {{ t("classes.viewUnassigned") }}
        </router-link>
      </div>
      <div class="card__body card__body--tight">
        <div class="chips">
          <router-link
            v-for="s in unassigned"
            :key="s.id"
            :to="`/students/${s.id}`"
            class="chip"
            draggable="true"
            @dragstart="onDragStart(s, null, $event)"
            @dragend="onDragEnd"
            @click.stop
          >
            {{ s.name }}
            <span class="muted tnum" style="font-size: 12px">{{ s.admission_no }}</span>
          </router-link>
        </div>
      </div>
    </section>
  </AsyncState>

  <!-- 座位表编辑弹窗 -->
  <div
    v-if="seatingClass && seating"
    class="overlay"
    role="dialog"
    aria-modal="true"
    :aria-label="`${t('classes.seating')} · ${seatingClass.name}`"
    @click.self="closeSeating"
  >
    <div class="modal" style="width: min(760px, 94vw)">
      <div class="modal__head">
        <div class="grow">
          <h2 class="modal__title">{{ t("classes.seating") }} · {{ seatingClass.name }}</h2>
        </div>
        <label class="row" style="gap: 4px; align-items: center; font-size: 13px">
          行
          <input
            v-model.number="seating.rows"
            class="input input--sm tnum"
            type="number"
            min="1"
            max="20"
            style="width: 60px"
            @change="resizeSeating"
            @input="resizeSeating"
          />
        </label>
        <label class="row" style="gap: 4px; align-items: center; font-size: 13px">
          列
          <input
            v-model.number="seating.cols"
            class="input input--sm tnum"
            type="number"
            min="1"
            max="12"
            style="width: 60px"
            @change="resizeSeating"
            @input="resizeSeating"
          />
        </label>
        <button class="icon-btn" aria-label="关闭" @click="closeSeating">
          <Icon name="close" :size="16" />
        </button>
      </div>
      <div class="modal__body">
        <div
          class="seating-grid"
          :style="{ gridTemplateColumns: `repeat(${seating.cols}, minmax(0, 1fr))` }"
        >
          <div
            v-for="(sid, i) in seating.cells"
            :key="i"
            class="seat"
            :class="{ 'seat--filled': sid }"
            @dragover.prevent
            @drop.prevent="onDropSeat(i)"
          >
            <div
              v-if="sid"
              class="seat__chip"
              draggable="true"
              @dragstart="onSeatDragStart(sid, i, $event)"
            >
              <b>{{ studentById.get(sid)?.name ?? "—" }}</b>
              <span class="seat__gender">{{ genderLabel(studentById.get(sid)?.gender) }}</span>
            </div>
          </div>
        </div>

        <div style="margin-top: 14px">
          <p class="field__hint" style="margin-bottom: 6px">
            未安排的学生（拖到座位入座，座位间拖动互换，拖回这里移除）
          </p>
          <div class="chips" @dragover.prevent @drop.prevent="onDropPool">
            <div
              v-for="s in poolStudents"
              :key="s.id"
              class="chip"
              draggable="true"
              @dragstart="onPoolDragStart(s.id, $event)"
            >
              {{ s.name }}
              <span class="muted">{{ genderLabel(s.gender) }}</span>
            </div>
            <span v-if="!poolStudents.length" class="muted" style="font-size: 13px">
              全部学生都已安排座位
            </span>
          </div>
        </div>

        <p v-if="seatingError" class="field__error" style="margin-top: 10px">
          <Icon name="alert-circle" :size="12" /> {{ seatingError }}
        </p>
      </div>
      <div class="modal__foot">
        <button type="button" class="btn btn--ghost" @click="closeSeating">
          {{ t("action.cancel") }}
        </button>
        <button type="button" class="btn btn--primary" :disabled="seatingSaving" @click="saveSeating">
          <span v-if="seatingSaving" class="spinner" />
          {{ seatingSaving ? t("action.saving") : t("action.save") }}
        </button>
      </div>
    </div>
  </div>
</template>
