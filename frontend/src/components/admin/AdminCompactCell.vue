<script setup>
import { computed } from "vue"
import { cellPreview } from "../../views/admin/adminTable.js"
import { t } from "../../strings"

const props = defineProps({
  value: { default: null },
  column: { type: String, default: "" },
  rowLabel: { type: String, default: "" },
  monospace: { type: Boolean, default: false },
  showNull: { type: Boolean, default: true },
})

const emit = defineEmits(["expand"])

const item = computed(() => cellPreview(props.value))

function onExpand() {
  if (!item.value.expandable) return
  emit("expand", {
    column: props.column,
    rowLabel: props.rowLabel,
    text: item.value.full,
  })
}
</script>

<template>
  <span v-if="item.preview === null && showNull" class="pill pill--muted">null</span>
  <button
    v-else-if="item.expandable"
    type="button"
    class="admin-cell admin-cell--btn"
    :title="t('admin.inspectViewFull')"
    :data-full="item.full"
    @click="onExpand"
  >
    <code v-if="monospace">{{ item.preview }}</code>
    <span v-else>{{ item.preview }}</span>
  </button>
  <code v-else-if="monospace" class="admin-cell">{{ item.preview }}</code>
  <span v-else class="admin-cell">{{ item.preview }}</span>
</template>
