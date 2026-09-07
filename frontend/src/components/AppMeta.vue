<script setup>
// Beta badge + app version — shown in the sidebar footer and login screen.
import { APP_VERSION, IS_BETA } from "../version"

defineProps({
  layout: { type: String, default: "sidebar" }, // sidebar | login
})
</script>

<template>
  <div class="app-meta" :class="`app-meta--${layout}`" aria-label="应用版本">
    <span v-if="IS_BETA" class="pill pill--beta">Beta</span>
    <span class="app-meta__version tnum">v{{ APP_VERSION }}</span>
  </div>
</template>
