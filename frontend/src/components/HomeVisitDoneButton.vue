<script setup>
// 家访「标记完成」：列表和时间线共用，完成后显示「已完成」标签。
import { ref } from "vue"
import { notify } from "../feedback"
import { friendlyError, t } from "../strings"
import { markHomeVisitDone } from "../homeVisit"

const props = defineProps({
  visit: { type: Object, required: true },
  showPill: { type: Boolean, default: true },
  showButton: { type: Boolean, default: true },
  compact: { type: Boolean, default: false },
})
const emit = defineEmits(["done"])

const marking = ref(false)

async function onClick(e) {
  e?.stopPropagation()
  e?.preventDefault()
  const { visit } = props
  if (!visit?.student_id || visit?.payload?.done || marking.value) return
  marking.value = true
  try {
    const next = await markHomeVisitDone(visit.student_id, visit.id, visit.payload)
    visit.payload = next
    emit("done", next)
    notify({ tone: "ok", title: t("visits.done"), timeout: 2400 })
  } catch (err) {
    notify({ tone: "error", title: friendlyError(err), timeout: 4000 })
  } finally {
    marking.value = false
  }
}
</script>

<template>
  <span class="home-visit-done">
    <span v-if="visit.payload?.done && showPill" class="pill pill--ok">
      {{ t("visits.done") }}
    </span>
    <button
      v-else-if="showButton && !visit.payload?.done && visit.student_id"
      type="button"
      class="btn btn--sm"
      :class="compact ? 'btn--ghost' : ''"
      :disabled="marking"
      @click="onClick"
    >
      <span v-if="marking" class="spinner" />
      {{ t("visits.markDone") }}
    </button>
  </span>
</template>
