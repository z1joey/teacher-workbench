<script setup>
import { ref, computed } from "vue"

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

function shortLabel(l) {
  const s = String(l)
  return s.length > 8 ? s.slice(0, 7) + "…" : s
}
</script>

<template>
  <div>
    <div class="chart-wrap">
      <svg :viewBox="`0 0 ${W} ${H}`" class="chart-svg" @mouseleave="hover = -1">
        <g v-for="tk in ticks" :key="tk.v">
          <line :x1="PAD.left" :x2="W - PAD.right" :y1="tk.y" :y2="tk.y" class="chart-grid" />
          <text :x="PAD.left - 8" :y="tk.y + 4" class="chart-tick" text-anchor="end">{{ tk.v }}</text>
        </g>

        <line
          v-if="highlightIndex >= 0 && highlightIndex < labels.length"
          :x1="xFor(highlightIndex)"
          :x2="xFor(highlightIndex)"
          :y1="PAD.top"
          :y2="H - PAD.bottom"
          class="chart-highlight"
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
        />

        <polyline
          v-for="seg in lines"
          :key="`line-${seg.key}`"
          :points="seg.points"
          class="chart-line"
          :stroke="seg.color"
        />

        <circle
          v-for="d in dots"
          :key="`dot-${d.key}`"
          :cx="d.x"
          :cy="d.y"
          r="4"
          :fill="d.color"
          stroke="#fff"
          stroke-width="1.5"
        />

        <text
          v-for="(l, i) in labels"
          :key="`xl-${i}`"
          :x="xFor(i)"
          :y="H - 10"
          class="chart-tick"
          text-anchor="middle"
        >{{ shortLabel(l) }}</text>
      </svg>

      <div v-if="tip" class="chart-tip" :style="{ left: (tip.x / W) * 100 + '%' }">
        <div class="chart-tip-label">{{ tip.label }}</div>
        <div v-for="r in tip.rows" :key="r.label" class="chart-tip-row">
          <span class="chart-tip-dot" :style="{ background: r.color }"></span>
          {{ r.label }}: <b>{{ r.value }}</b>
        </div>
      </div>
    </div>

    <div class="chart-legend">
      <span v-for="s in series" :key="s.key" class="chart-legend-item">
        <span class="chart-tip-dot" :style="{ background: s.color }"></span>{{ s.label }}
      </span>
    </div>
  </div>
</template>
