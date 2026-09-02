<script setup>
import { onMounted, ref, watch } from "vue"
import { useRoute, useRouter } from "vue-router"
import Icon from "./components/Icon.vue"
import api, { getToken, setToken } from "./api"
import { clearMe, loadMe, me } from "./auth"
import { t } from "./strings"

const route = useRoute()
const router = useRouter()
const loggingOut = ref(false)

onMounted(loadMe)
// after login the token appears without a remount — pick the user up then
watch(
  () => route.path,
  (path) => {
    if (path !== "/login" && getToken() && !me.value) loadMe()
  }
)

async function logout() {
  if (loggingOut.value) return
  loggingOut.value = true
  try {
    await api.post("/auth/logout")
  } catch {
    // ignore — we clear the client token regardless
  }
  setToken(null)
  clearMe()
  loggingOut.value = false
  router.replace("/login")
}

// Computed: admin-specific nav vs teacher nav.
// Admins are developers, not teachers — they get a stripped-down nav and
// are redirected away from all teacher-only pages.
const isAdmin = () => me.value?.is_admin === true
</script>

<template>
  <div class="app">
    <nav v-if="route.path !== '/login'" class="topnav">
      <!-- Admin nav — standalone, no teacher workflow links -->
      <template v-if="me && isAdmin()">
        <router-link to="/admin" class="brand">
          <Icon name="board" :size="20" />
          {{ t("app.title") }}
        </router-link>
        <div class="nav-links">
          <router-link to="/admin">{{ t("nav.admin") }}</router-link>
        </div>
        <div class="nav-user">
          <span class="nav-teacher">
            <span class="nav-avatar" style="background: var(--danger); border-color: rgba(255,255,255,0.4);">
              A
            </span>
            {{ t("nav.admin") }}
          </span>
          <button
            class="small"
            style="padding: 4px 10px; font-size: 13px; background: rgba(255,255,255,0.12); border-color: rgba(255,255,255,0.28); color: var(--chalk-ink);"
            :disabled="loggingOut"
            @click="logout"
          >{{ t("auth.logout") }}</button>
        </div>
      </template>

      <!-- Teacher nav — unchanged from before -->
      <template v-else>
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
      </template>
    </nav>
    <main class="content">
      <router-view />
    </main>
  </div>
</template>
