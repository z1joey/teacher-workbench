<script setup>
// 纯 SVG 折线图。除鼠标悬停外，也可用键盘左右箭头逐场查看，
// 让只用键盘的老师同样能读到每个数值（识别优于回忆 + 无障碍）。
import { computed, ref, watch } from "vue"

const props = defineProps({
  // x categories, one per exam, already localized by the caller
  labels: { type: Array, default: () => [] },
  // optional ISO dates — shown under the label when exam names repeat
  dates: { type: Array, default: () => [] },
  // [{ key, label, color, values: [number | null] }] — null renders a gap
  series: { type: Array, default: () => [] },
  yMax: { type: Number, default: 100 },
  highlightIndex: { type: Number, default: -1 },
  // 可选：自定义悬停数值的显示（如原始分 + 满分），入参 (series, value, index)
  formatTip: { type: Function, default: null },
})

const CORE_KEYS = new Set(["chinese", "math", "english"])

// 图例点击可隐藏/显示对应科目线，9 条线挤在一起时便于聚焦
const hidden = ref(new Set())
const didAutoHide = ref(false)

watch(
  () => props.series,
  (s) => {
    if (didAutoHide.value || s.length < 7) return
    didAutoHide.value = true
    hidden.value = new Set(s.filter((x) => !CORE_KEYS.has(x.key)).map((x) => x.key))
  },
  { immediate: true }
)

function toggleSeries(key) {
  const next = new Set(hidden.value)
  if (next.has(key)) next.delete(key)
  else next.add(key)
  hidden.value = next
}

const visibleSeries = computed(() =>
  props.series.filter((s) => !hidden.value.has(s.key))
)

const MIN_GAP = 84
const BASE_H = 380
const PAD = { top: 24, right: 24, bottom: 58, left: 48 }

const layout = computed(() => {
  const n = props.labels.length
  const plotW = n <= 1 ? 160 : Math.max(520, (n - 1) * MIN_GAP)
  const W = PAD.left + PAD.right + plotW
  const H = BASE_H
  const plotH = H - PAD.top - PAD.bottom
  return { W, H, plotW, plotH, PAD }
})

function yFor(v) {
  const { plotH, PAD: p } = layout.value
  return p.top + plotH - (v / props.yMax) * plotH
}

function xFor(i) {
  const { plotW, PAD: p } = layout.value
  const n = props.labels.length
  if (n <= 1) return p.left + plotW / 2
  return p.left + (i / (n - 1)) * plotW
}

const lineStroke = computed(() => {
  const n = visibleSeries.value.length
  if (n <= 4) return 2.5
  if (n <= 6) return 2
  return 1.5
})

const ticks = computed(() =>
  Array.from({ length: 5 }, (_, i) => {
    const v = Math.round((props.yMax / 4) * i * 10) / 10
    return { v, y: yFor(v) }
  })
)

const lines = computed(() => {
  const out = []
  for (const s of visibleSeries.value) {
    let run = []
    const flush = () => {
      if (run.length > 1) out.push({ key: s.key, color: s.color, points: run.join(" ") })
      run = []
    }
    s.values.forEach((v, i) => {
      if (v == null) {
        flush()
        return
      }
      run.push(`${xFor(i)},${yFor(v)}`)
    })
    flush()
  }
  return out
})

const activeIndex = computed(() => {
  if (hover.value >= 0) return hover.value
  if (props.highlightIndex >= 0 && props.highlightIndex < props.labels.length) {
    return props.highlightIndex
  }
  return -1
})

const dots = computed(() => {
  const idx = activeIndex.value
  if (idx < 0) return []
  const out = []
  for (const s of visibleSeries.value) {
    const v = s.values[idx]
    if (v != null) {
      out.push({ key: `${s.key}-${idx}`, color: s.color, x: xFor(idx), y: yFor(v) })
    }
  }
  return out
})

const hoverBand = computed(() => {
  const idx = activeIndex.value
  if (idx < 0) return null
  const n = props.labels.length
  const { plotW, plotH, PAD: p } = layout.value
  const w = n <= 1 ? plotW : Math.min(MIN_GAP, plotW / Math.max(n - 1, 1))
  return {
    x: xFor(idx) - w / 2,
    y: p.top,
    width: w,
    height: plotH,
  }
})

const hover = ref(-1)

const tip = computed(() => {
  const idx = activeIndex.value
  if (idx < 0 || idx >= props.labels.length) return null
  const rows = visibleSeries.value
    .map((s) => ({
      label: s.label,
      color: s.color,
      value: props.formatTip
        ? props.formatTip(s, s.values[idx], idx)
        : s.values[idx],
    }))
    .filter((r) => r.value != null)
  return { label: props.labels[idx], rows, x: xFor(idx) }
})

function step(delta) {
  const n = props.labels.length
  if (!n) return
  hover.value = hover.value < 0 ? (delta > 0 ? 0 : n - 1) : (hover.value + delta + n) % n
}

function onKeydown(e) {
  if (e.key === "ArrowRight") {
    e.preventDefault()
    step(1)
  } else if (e.key === "ArrowLeft") {
    e.preventDefault()
    step(-1)
  } else if (e.key === "Escape") {
    hover.value = -1
  }
}

function shortLabel(l) {
  const s = String(l)
  return s.length > 8 ? s.slice(0, 7) + "…" : s
}

function fmtShortDate(d) {
  if (!d) return ""
  const t = Date.parse(d)
  if (Number.isNaN(t)) return String(d)
  return new Date(t).toLocaleDateString("zh-CN", { month: "numeric", day: "numeric" })
}

const axisLabels = computed(() => {
  const counts = {}
  props.labels.forEach((l) => {
    counts[l] = (counts[l] || 0) + 1
  })
  return props.labels.map((label, i) => {
    const dup = counts[label] > 1
    const sub = dup && props.dates[i] ? fmtShortDate(props.dates[i]) : null
    const main = shortLabel(label)
    const w = Math.max(main.length * 11 + 10, sub ? sub.length * 9 + 10 : 0, 52)
    return { i, main, sub, w }
  })
})

// X 轴标签：字多放不下时自动跳着显示，而不是挤成一团。
// 首尾与“当前这次考试”的标签始终保留，其余在放得下的前提下尽量多放。
const xLabels = computed(() => {
  const items = axisLabels.value
  const n = items.length
  if (!n) return []
  if (n === 1) return [items[0]]

  const priority = [props.highlightIndex >= 0 && props.highlightIndex < n ? props.highlightIndex : -1, 0, n - 1]
    .filter((i) => i >= 0)
  const shown = []
  const canPlace = (it) => {
    const x = xFor(it.i)
    const s = x - it.w / 2
    const e = x + it.w / 2
    return !shown.some((o) => {
      const ox = xFor(o.i)
      return s < ox + o.w / 2 && e > ox - o.w / 2
    })
  }
  for (const p of priority) {
    if (!shown.some((o) => o.i === p) && canPlace(items[p])) shown.push(items[p])
  }
  for (const it of items) {
    if (!shown.some((o) => o.i === it.i) && canPlace(it)) shown.push(it)
  }
  return shown.sort((a, b) => a.i - b.i)
})
</script>

<template>
  <div>
    <div class="chart__viewport">
      <div class="chart" :style="{ minWidth: `${layout.W}px` }">
        <svg
          :viewBox="`0 0 ${layout.W} ${layout.H}`"
          class="chart__svg"
          role="img"
          tabindex="0"
          :aria-label="`折线图：${labels.join('、')}`"
          @mouseleave="hover = -1"
          @keydown="onKeydown"
          @blur="hover = -1"
        >
          <g v-for="tk in ticks" :key="tk.v">
            <line
              :x1="layout.PAD.left"
              :x2="layout.W - layout.PAD.right"
              :y1="tk.y"
              :y2="tk.y"
              class="chart__grid"
            />
            <text
              :x="layout.PAD.left - 10"
              :y="tk.y + 4"
              class="chart__tick"
              text-anchor="end"
            >{{ tk.v }}</text>
          </g>

          <rect
            v-if="hoverBand"
            :x="hoverBand.x"
            :y="hoverBand.y"
            :width="hoverBand.width"
            :height="hoverBand.height"
            class="chart__hover-band"
            rx="4"
          />

          <line
            v-if="highlightIndex >= 0 && highlightIndex < labels.length"
            :x1="xFor(highlightIndex)"
            :x2="xFor(highlightIndex)"
            :y1="layout.PAD.top"
            :y2="layout.H - layout.PAD.bottom"
            class="chart__highlight"
          />

          <rect
            v-for="(l, i) in labels"
            :key="`col-${i}`"
            :x="xFor(i) - layout.plotW / Math.max(labels.length, 1) / 2"
            :y="layout.PAD.top"
            :width="layout.plotW / Math.max(labels.length, 1)"
            :height="layout.plotH"
            fill="transparent"
            @mouseenter="hover = i"
            @touchstart="hover = i"
          />

          <polyline
            v-for="seg in lines"
            :key="`line-${seg.key}`"
            :points="seg.points"
            class="chart__line"
            :stroke="seg.color"
            :stroke-width="lineStroke"
          />

          <circle
            v-for="d in dots"
            :key="`dot-${d.key}`"
            :cx="d.x"
            :cy="d.y"
            r="4.5"
            :fill="d.color"
            stroke="#fff"
            stroke-width="2"
          />

          <g v-for="xl in xLabels" :key="`xl-${xl.i}`">
            <text
              :x="xFor(xl.i) + (xl.i === 0 ? 2 : xl.i === labels.length - 1 ? -2 : 0)"
              :y="layout.H - (xl.sub ? 28 : 14)"
              class="chart__tick"
              :text-anchor="xl.i === 0 ? 'start' : xl.i === labels.length - 1 ? 'end' : 'middle'"
            >{{ xl.main }}</text>
            <text
              v-if="xl.sub"
              :x="xFor(xl.i) + (xl.i === 0 ? 2 : xl.i === labels.length - 1 ? -2 : 0)"
              :y="layout.H - 10"
              class="chart__tick chart__tick-sub"
              :text-anchor="xl.i === 0 ? 'start' : xl.i === labels.length - 1 ? 'end' : 'middle'"
            >{{ xl.sub }}</text>
          </g>
        </svg>

        <div
          v-if="tip"
          class="chart__tip"
          :style="{ left: `${(tip.x / layout.W) * 100}%` }"
        >
          <div class="chart__tip-label">{{ tip.label }}</div>
          <div v-for="r in tip.rows" :key="r.label" class="chart__tip-row">
            <span class="chart__dot" :style="{ background: r.color }" /> {{ r.label }}:
            <b class="tnum">{{ r.value }}</b>
          </div>
        </div>
      </div>
    </div>

    <div class="chart__legend">
      <button
        v-for="s in series"
        :key="s.key"
        type="button"
        class="chart__legend-item"
        :class="{ 'is-off': hidden.has(s.key) }"
        :aria-pressed="!hidden.has(s.key)"
        @click="toggleSeries(s.key)"
      >
        <span class="chart__dot" :style="{ background: s.color }" />{{ s.label }}
      </button>
      <span class="muted chart__legend-hint">← → 逐场查看 · 点击科目显示/隐藏</span>
    </div>
  </div>
</template>
