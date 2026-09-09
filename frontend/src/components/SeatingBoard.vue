<script setup>
// 座位表：拖拽编排 + 行列调整，就地编辑（无弹窗），保存到 /classes/:id/seating。
import { computed, onMounted, ref, watch } from "vue"
import api from "../api"
import Icon from "./Icon.vue"
import { notify } from "../feedback"
import { friendlyError, genderLabel, t } from "../strings"

const props = defineProps({
  classId: { type: String, required: true },
  students: { type: Array, default: () => [] },
})

const seating = ref(null) // { rows, cols, cells: Array(学生id|null) }，行优先
const pristine = ref("") // 上次加载/保存成功后的快照，用于判断有无未保存改动
const saving = ref(false)
const error = ref("")
const seatDrag = ref(null) // { studentId, from: "seat"|"pool", index? }

function snapshot(s) {
  return `${s.rows}x${s.cols}|${s.cells.map((v) => v ?? "-").join(",")}`
}

// 行列或座位任一处有改动即视为待保存
const dirty = computed(() => !!seating.value && snapshot(seating.value) !== pristine.value)

const studentById = computed(() => {
  const map = new Map()
  for (const s of props.students) map.set(s.id, s)
  return map
})

const poolStudents = computed(() => {
  const seated = new Set((seating.value?.cells ?? []).filter(Boolean))
  return props.students.filter((s) => !seated.has(s.id))
})

async function load() {
  error.value = ""
  seatDrag.value = null
  seating.value = null
  try {
    const res = await api.get(`/classes/${props.classId}/seating`)
    const rows = res.rows > 0 ? res.rows : Math.max(1, Math.ceil(props.students.length / 8))
    const cols = res.cols > 0 ? res.cols : 8
    const cells = Array(rows * cols).fill(null)
    for (const [pos, sid] of Object.entries(res.seats || {})) {
      const i = Number(pos)
      // 转走的学生不再占座
      if (i >= 0 && i < cells.length && studentById.value.has(sid)) cells[i] = sid
    }
    seating.value = { rows, cols, cells }
    pristine.value = snapshot(seating.value)
  } catch (e) {
    error.value = friendlyError(e)
    seating.value = { rows: 4, cols: 8, cells: Array(32).fill(null) }
    pristine.value = snapshot(seating.value)
  }
}
onMounted(load)
watch(() => props.classId, load)

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
  saving.value = true
  error.value = ""
  try {
    await api.put(`/classes/${props.classId}/seating`, {
      rows: s.rows,
      cols: s.cols,
      seats,
    })
    pristine.value = snapshot(seating.value)
    notify({ tone: "ok", title: "座位表已保存", timeout: 2600 })
  } catch (e) {
    error.value = friendlyError(e)
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="card" style="margin-bottom: var(--sp-5)">
    <div class="card__head">
      <div>
        <h2 class="card__title"><Icon name="board" :size="16" /> {{ t("classes.seating") }}</h2>
        <p class="card__desc">拖动学生调整座位，改完记得保存</p>
      </div>
      <div v-if="seating" class="row" style="gap: 10px; align-items: center">
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
        <button
          type="button"
          class="btn btn--primary btn--sm"
          :disabled="saving || !dirty"
          @click="saveSeating"
        >
          <span v-if="saving" class="spinner" />
          {{ saving ? t("action.saving") : t("action.save") }}
        </button>
      </div>
    </div>
    <div class="card__body">
      <div v-if="!seating" class="state state--in-card">
        <p class="state__desc">{{ t("common.loading") }}</p>
      </div>
      <template v-else>
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

        <p v-if="error" class="field__error" style="margin-top: 10px">
          <Icon name="alert-circle" :size="12" /> {{ error }}
        </p>
      </template>
    </div>
  </div>
</template>
