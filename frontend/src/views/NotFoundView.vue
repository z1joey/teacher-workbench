<script setup>
// 404：说清发生了什么，并给两条明确的出路
import Icon from "../components/Icon.vue"
import { t } from "../strings"
</script>

<template>
  <div class="nf-wrap">
    <div class="nf-board">
      <Icon name="board" :size="38" />
      <div class="nf-code">404</div>
      <p class="nf-title">{{ t("nf.title") }}</p>
      <p class="nf-sub">{{ t("nf.sub") }}</p>
    </div>
    <div class="nf-actions">
      <router-link to="/"><button class="btn btn--primary">{{ t("nf.backHome") }}</button></router-link>
      <router-link to="/students"><button class="btn">{{ t("nf.backStudents") }}</button></router-link>
    </div>
  </div>
</template>
