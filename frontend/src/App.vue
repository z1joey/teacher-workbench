<script setup>
import { onMounted, watch } from "vue"
import { useRoute } from "vue-router"
import Icon from "./components/Icon.vue"
import { getToken } from "./api"
import { loadMe, me } from "./auth"
import { t } from "./strings"

const route = useRoute()

onMounted(loadMe)
// after login the token appears without a remount — pick the user up then
watch(
  () => route.path,
  (path) => {
    if (path !== "/login" && getToken() && !me.value) loadMe()
  }
)
</script>

<template>
  <div class="app">
    <nav v-if="route.path !== '/login'" class="topnav">
      <router-link to="/" class="brand">
        <Icon name="board" :size="20" />
        {{ t("app.title") }}
      </router-link>
      <div class="nav-links">
        <router-link to="/">{{ t("nav.home") }}</router-link>
        <router-link to="/students">{{ t("nav.students") }}</router-link>
        <router-link to="/classes">{{ t("nav.classes") }}</router-link>
        <router-link to="/exams">{{ t("nav.exams") }}</router-link>
      </div>
      <div class="nav-user">
        <router-link v-if="me" to="/profile" class="nav-teacher" :title="t('profile.title')">
          <span class="nav-avatar">{{ me.name.charAt(0) }}</span>
          {{ me.name }}
        </router-link>
      </div>
    </nav>
    <main class="content">
      <router-view />
    </main>
  </div>
</template>
