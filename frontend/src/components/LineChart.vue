<script setup>
// 纯 SVG 折线图。除鼠标悬停外，也可用键盘左右箭头逐场查看，
// 让只用键盘的老师同样能读到每个数值（识别优于回忆 + 无障碍）。
import { computed, ref } from "vue"

const props = defineProps({
  // x categories, one per exam, already localized by the caller
  labels: { type: Array, default: () => [] },
  // [{ key, label, color, values: [number | null] }] — null renders a gap
  series: { type: Array, default: () => [] },
  yMax: { type: Number, default: 100 },
  highlightIndex: { type: Number, default: -1 },
})

const W = 640
const H = 300
const PAD = { top: 16, right: 16, bottom: 34, left: 42 }
const plotW = W - PAD.left - PAD.right
const plotH = H - PAD.top - PAD.bottom

function yFor(v) {
  return PAD.top + plotH - (v / props.yMax) * plotH
}

function xFor(i) {
  if (props.labels.length <= 1) return PAD.left + plotW / 2
  return PAD.left + (i / (props.labels.length - 1)) * plotW
}

const ticks = computed(() =>
  Array.from({ length: 5 }, (_, i) => {
    const v = Math.round((props.yMax / 4) * i * 10) / 10
    return { v, y: yFor(v) }
  })
)

const lines = computed(() => {
  const out = []
  for (const s of props.series) {
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

const dots = computed(() => {
  const out = []
  for (const s of props.series) {
    s.values.forEach((v, i) => {
      if (v != null) {
        out.push({ key: `${s.key}-${i}`, color: s.color, x: xFor(i), y: yFor(v) })
      }
    })
  }
  return out
})

const hover = ref(-1)

const tip = computed(() => {
  if (hover.value < 0 || hover.value >= props.labels.length) return null
  const rows = props.series
    .map((s) => ({ label: s.label, color: s.color, value: s.values[hover.value] }))
    .filter((r) => r.value != null)
  return { label: props.labels[hover.value], rows, x: xFor(hover.value) }
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
  return s.length > 10 ? s.slice(0, 9) + "…" : s
}

// X 轴标签：字多放不下时自动跳着显示，而不是挤成一团。
// 首尾与“当前这次考试”的标签始终保留，其余在放得下的前提下尽量多放。
const xLabels = computed(() => {
  const n = props.labels.length
  if (!n) return []
  if (n === 1) return [{ i: 0, text: shortLabel(props.labels[0]) }]

  const items = props.labels.map((l, i) => {
    const text = shortLabel(l)
    return { i, text, w: Math.min(text.length * 11 + 6, 96) }
  })
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
    <div class="chart">
      <svg
        :viewBox="`0 0 ${W} ${H}`"
        class="chart__svg"
        role="img"
        tabindex="0"
        :aria-label="`折线图：${labels.join('、')}`"
        @mouseleave="hover = -1"
        @keydown="onKeydown"
        @blur="hover = -1"
      >
        <g v-for="tk in ticks" :key="tk.v">
          <line :x1="PAD.left" :x2="W - PAD.right" :y1="tk.y" :y2="tk.y" class="chart__grid" />
          <text :x="PAD.left - 8" :y="tk.y + 4" class="chart__tick" text-anchor="end">{{ tk.v }}</text>
        </g>

        <line
          v-if="highlightIndex >= 0 && highlightIndex < labels.length"
          :x1="xFor(highlightIndex)"
          :x2="xFor(highlightIndex)"
          :y1="PAD.top"
          :y2="H - PAD.bottom"
          class="chart__highlight"
        />

        <rect
          v-for="(l, i) in labels"
          :key="`col-${i}`"
          :x="xFor(i) - plotW / Math.max(labels.length, 1) / 2"
          :y="PAD.top"
          :width="plotW / Math.max(labels.length, 1)"
          :height="plotH"
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
        />

        <circle
          v-for="d in dots"
          :key="`dot-${d.key}`"
          :cx="d.x"
          :cy="d.y"
          :r="hover >= 0 && labels[hover] ? 4 : 3.5"
          :fill="d.color"
          stroke="#fff"
          stroke-width="1.5"
        />

        <text
          v-for="xl in xLabels"
          :key="`xl-${xl.i}`"
          :x="xFor(xl.i) + (xl.i === 0 ? 2 : xl.i === labels.length - 1 ? -2 : 0)"
          :y="H - 10"
          class="chart__tick"
          :text-anchor="xl.i === 0 ? 'start' : xl.i === labels.length - 1 ? 'end' : 'middle'"
        >{{ xl.text }}</text>
      </svg>

      <div v-if="tip" class="chart__tip" :style="{ left: `${(tip.x / W) * 100}%` }">
        <div class="chart__tip-label">{{ tip.label }}</div>
        <div v-for="r in tip.rows" :key="r.label" class="chart__tip-row">
          <span class="chart__dot" :style="{ background: r.color }" /> {{ r.label }}:
          <b class="tnum">{{ r.value }}</b>
        </div>
      </div>
    </div>

    <div class="chart__legend">
      <span v-for="s in series" :key="s.key" class="chart__legend-item">
        <span class="chart__dot" :style="{ background: s.color }" />{{ s.label }}
      </span>
      <span class="muted" style="font-size: 12px">← → 逐场查看</span>
    </div>
  </div>
</template>
