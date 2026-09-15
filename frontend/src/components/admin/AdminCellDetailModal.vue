<script setup>
import Icon from "../Icon.vue"
import { t } from "../../strings"

defineProps({
  detail: { type: Object, default: null },
})

const emit = defineEmits(["close"])
</script>

<template>
  <div
    v-if="detail"
    class="overlay"
    role="dialog"
    aria-modal="true"
    aria-label="完整内容"
    @click.self="emit('close')"
  >
    <div class="modal admin-detail-modal">
      <button class="icon-btn admin-detail-modal__close" :aria-label="t('action.close')" @click="emit('close')">
        <Icon name="close" :size="16" />
      </button>
      <pre class="admin-detail">{{ detail.text }}</pre>
    </div>
  </div>
</template>
