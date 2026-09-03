<script setup>
import { computed, onMounted, ref, watch } from "vue"
import { useRoute, useRouter } from "vue-router"
import Icon from "./components/Icon.vue"
import api, { getToken, setToken } from "./api"
import { clearMe, loadMe, me } from "./auth"
import {
  clearSearch,
  ensureSearchStudents,
  searchQuery,
  searchStudents,
} from "./search"
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
  clearSearch()
  loggingOut.value = false
  router.replace("/login")
}

// Computed: admin-specific nav vs teacher nav.
// Admins are developers, not teachers — they get a stripped-down nav and
// are redirected away from all teacher-only pages.
const isAdmin = () => me.value?.role === "admin"

// --- global student search (nav) ---
const searchInput = ref(null)

const searchMatches = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return []
  return searchStudents.value
    .filter(
      (s) =>
        s.name.toLowerCase().includes(q) ||
        s.admission_no.toLowerCase().includes(q) ||
        (s.class && s.class.name.toLowerCase().includes(q))
    )
    .slice(0, 8)
})

// Typing from any page must have the directory ready, even if the input's
// focus event never fired (autofill, programmatic focus).
watch(searchQuery, (q) => {
  if (q.trim()) ensureSearchStudents()
})

function openStudent(s) {
  searchQuery.value = ""
  searchInput.value?.blur()
  router.push(`/students/${s.id}`)
}

function searchGoList() {
  searchInput.value?.blur()
  router.push("/students")
}

function searchDismiss() {
  searchQuery.value = ""
  searchInput.value?.blur()
}
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

      <!-- Teacher nav — search-first: brand removed so the search box sits centered -->
      <template v-else>
        <div class="nav-links">
          <router-link to="/">{{ t("nav.home") }}</router-link>
          <router-link to="/students">{{ t("nav.students") }}</router-link>
          <router-link to="/classes">{{ t("nav.classes") }}</router-link>
          <router-link to="/exams">{{ t("nav.exams") }}</router-link>
        </div>
        <div class="nav-search">
          <div class="nav-search-inner">
            <Icon name="search" :size="14" class="nav-search-icon" />
            <input
              ref="searchInput"
              v-model="searchQuery"
              type="text"
              :placeholder="t('students.search')"
              autocomplete="off"
              @focus="ensureSearchStudents()"
              @keydown.enter="searchGoList"
              @keydown.esc="searchDismiss"
            />
            <!-- no dropdown on /students — the grouped list there is the live result view -->
            <div v-if="searchQuery.trim() && route.path !== '/students'" class="nav-search-menu">
              <div
                v-for="s in searchMatches"
                :key="s.id"
                class="nav-search-item"
                @mousedown.prevent="openStudent(s)"
              >
                <strong>{{ s.name }}</strong>
                <span class="nav-search-meta">
                  {{ s.admission_no }} · {{ s.class ? s.class.name : t("students.ungrouped") }}
                </span>
              </div>
              <div v-if="!searchMatches.length" class="nav-search-empty">
                {{ t("common.noMatch") }}
              </div>
            </div>
          </div>
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
