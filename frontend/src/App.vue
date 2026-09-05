<script setup>
// 应用外壳：
//   侧栏导航（识别优于回忆）+ 顶栏面包屑（随时知道自己在哪）
//   + 移动端抽屉与底部标签栏 + 全局搜索 / 命令面板 / 帮助 / 提示条
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue"
import { useRoute, useRouter } from "vue-router"
import Icon from "./components/Icon.vue"
import NavSearch from "./components/NavSearch.vue"
import AppToasts from "./components/AppToasts.vue"
import ConfirmHost from "./components/ConfirmHost.vue"
import HelpDrawer from "./components/HelpDrawer.vue"
import CommandPalette from "./components/CommandPalette.vue"
import api, { getToken, setToken } from "./api"
import { clearMe, loadMe, me } from "./auth"
import { clearSearch } from "./search"
import { ADMIN_NAV, TABBAR_KEYS, TEACHER_NAV, isNavActive } from "./nav"
import { t } from "./strings"
import { pageTitle, setPageTitle } from "./title"
import { ask, closeConfirm, confirmDialog } from "./confirm"
import { closeHelp, helpOpen, openHelp, toggleHelp } from "./help"
import { clearAll } from "./feedback"

const route = useRoute()
const router = useRouter()

const drawerOpen = ref(false)
const paletteOpen = ref(false)
const searchRef = ref(null)
const loggingOut = ref(false)

const isLogin = computed(() => route.path === "/login")
const isAdmin = computed(() => me.value?.role === "admin")
const navItems = computed(() => (isAdmin.value ? ADMIN_NAV : TEACHER_NAV))
const tabItems = computed(() => TEACHER_NAV.filter((n) => TABBAR_KEYS.includes(n.key)))

// 面包屑：父级 + 当前页（详情页会把真实名字写进 pageTitle）
const crumbs = computed(() => {
  const meta = route.meta || {}
  const out = []
  if (meta.parent) out.push({ ...meta.parent })
  const label = pageTitle.value || meta.title
  if (label) out.push({ label })
  return out
})

onMounted(loadMe)
watch(
  () => route.path,
  (path) => {
    drawerOpen.value = false
    setPageTitle("") // 切换页面先清掉上一个详情页留下的名字
    if (path !== "/login" && getToken() && !me.value) loadMe()
  }
)

// ------------------------------------------------------------------ 退出

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
  clearAll()
  loggingOut.value = false
  router.replace("/login")
}

async function onLogout() {
  const ok = await ask({
    title: "退出登录？",
    message: "退出后需要重新输入手机号和密码。",
    confirmLabel: "退出登录",
    tone: "warn",
  })
  if (ok) logout()
}

// -------------------------------------------------------- 命令面板数据源

const paletteActions = computed(() => {
  if (isAdmin.value) {
    return [
      { id: "reload", label: "重新加载数据", icon: "refresh", run: () => window.location.reload() },
      { id: "help", label: "帮助与快捷键", icon: "help", hint: "?", run: () => openHelp() },
      { id: "logout", label: "退出登录", icon: "logout", run: onLogout },
    ]
  }
  return [
    { id: "new-student", label: "添加学生", icon: "plus", hint: "新建", run: () => router.push("/students/new") },
    { id: "new-exam", label: "新建考试", icon: "clipboard", hint: "新建", run: () => router.push("/exams/new") },
    { id: "new-class", label: "新建班级", icon: "building", hint: "新建", run: () => router.push("/classes?create=1") },
    { id: "events", label: "查看事件", icon: "checklist", run: () => router.push("/events") },
    { id: "profile", label: "个人中心", icon: "user", run: () => router.push("/profile") },
    { id: "help", label: "帮助与快捷键", icon: "help", hint: "?", run: () => openHelp() },
    { id: "logout", label: "退出登录", icon: "logout", run: onLogout },
  ]
})

// -------------------------------------------------------------- 键盘快捷键

let lastG = 0

function isTyping(e) {
  const el = e.target
  return (
    el &&
    (el.tagName === "INPUT" ||
      el.tagName === "TEXTAREA" ||
      el.tagName === "SELECT" ||
      el.isContentEditable)
  )
}

function onKeydown(e) {
  // Esc 永远先关最上层浮层
  if (e.key === "Escape") {
    if (paletteOpen.value) return void (paletteOpen.value = false)
    if (helpOpen.value) return closeHelp()
    if (confirmDialog.value) return closeConfirm(false)
    if (drawerOpen.value) return void (drawerOpen.value = false)
    if (isTyping(e)) e.target.blur()
    return
  }

  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
    e.preventDefault()
    paletteOpen.value = !paletteOpen.value
    return
  }

  if (isLogin.value || e.metaKey || e.ctrlKey || e.altKey) return

  if (e.key === "?") {
    e.preventDefault()
    toggleHelp()
    return
  }

  if (isTyping(e)) return

  if (e.key === "/") {
    e.preventDefault()
    searchRef.value?.focus()
    return
  }

  // g 之后接 h / s / c / e / v / r / p —— 高手不用摸鼠标
  if (e.key.toLowerCase() === "g") {
    lastG = Date.now()
    return
  }
  if (lastG && Date.now() - lastG < 1400) {
    const to = { h: "/", s: "/students", c: "/classes", e: "/exams", v: "/visits", r: "/events", p: "/profile" }[
      e.key.toLowerCase()
    ]
    lastG = 0
    if (to) {
      e.preventDefault()
      router.push(to)
    }
  }
}

onMounted(() => window.addEventListener("keydown", onKeydown))
onBeforeUnmount(() => window.removeEventListener("keydown", onKeydown))

watch(paletteOpen, (v) => {
  if (v) helpOpen.value = false
})
</script>

<template>
  <a class="skip-link" href="#main">跳到主要内容</a>

  <!-- 登录页独立呈现，不带导航 -->
  <router-view v-if="isLogin" />

  <div v-else class="shell">
    <!-- 移动端抽屉遮罩 -->
    <button
      v-if="drawerOpen"
      class="scrim"
      aria-label="关闭菜单"
      @click="drawerOpen = false"
    />

    <!-- 侧栏：黑板 -->
    <aside class="sidebar" :class="{ 'is-open': drawerOpen }">
      <router-link :to="isAdmin ? '/admin' : '/'" class="brand">
        <span class="brand__mark"><Icon name="board" :size="18" /></span>
        <span class="brand__text">{{ t("app.title") }}</span>
      </router-link>

      <nav aria-label="主导航">
        <p class="nav-label">{{ isAdmin ? "系统" : "教学" }}</p>
        <router-link
          v-for="item in navItems"
          :key="item.key"
          :to="item.to"
          class="nav-item"
          :class="{ 'is-active': isNavActive(item, route.path) }"
          :title="item.label"
          @click="drawerOpen = false"
        >
          <Icon :name="item.icon" :size="18" />
          <span class="nav-item__text">{{ item.label }}</span>
          <kbd v-if="item.g" class="kbd nav-item__count">{{ item.g }}</kbd>
        </router-link>
      </nav>

      <div class="sidebar__foot">
        <router-link v-if="!isAdmin && me" to="/profile" class="sidebar-user" @click="drawerOpen = false">
          <span class="avatar">{{ me.name.charAt(0) }}</span>
          <span class="sidebar-user__meta">
            <span class="sidebar-user__name">{{ me.name }}</span>
            <span class="sidebar-user__role">{{ me.subject || t("nav.profile") }}</span>
          </span>
        </router-link>

        <button class="nav-item" @click="openHelp()">
          <Icon name="help" :size="18" />
          <span class="nav-item__text">帮助与快捷键</span>
          <kbd class="kbd nav-item__count">?</kbd>
        </button>

        <button class="nav-item" :disabled="loggingOut" @click="onLogout">
          <Icon name="logout" :size="18" />
          <span class="nav-item__text">{{ t("auth.logout") }}</span>
        </button>
      </div>
    </aside>

    <div class="main">
      <!-- 顶栏 -->
      <header class="topbar">
        <button
          class="icon-btn topbar__burger"
          :aria-expanded="drawerOpen"
          :aria-label="t('nav.menu')"
          @click="drawerOpen = !drawerOpen"
        >
          <Icon name="menu" :size="18" />
        </button>

        <nav class="topbar__crumbs" aria-label="当前位置">
          <template v-for="(c, i) in crumbs" :key="i">
            <span v-if="i > 0" class="sep" aria-hidden="true">/</span>
            <router-link v-if="c.to" :to="c.to">{{ c.label }}</router-link>
            <span v-else class="truncate" aria-current="page">{{ c.label }}</span>
          </template>
        </nav>

        <div class="topbar__actions">
          <NavSearch v-if="!isAdmin" ref="searchRef" />
          <button class="icon-btn" aria-label="打开命令面板" :title="'命令面板 ⌘K'" @click="paletteOpen = true">
            <Icon name="search" :size="17" />
          </button>
          <button class="icon-btn" aria-label="帮助与快捷键" @click="openHelp()">
            <Icon name="help" :size="17" />
          </button>
        </div>
      </header>

      <main id="main" class="content" tabindex="-1">
        <router-view />
      </main>
    </div>

    <!-- 移动端底部标签栏 -->
    <nav v-if="!isAdmin" class="tabbar" aria-label="快捷导航">
      <div class="tabbar__inner">
        <router-link
          v-for="item in tabItems"
          :key="item.key"
          :to="item.to"
          class="tabbar__item"
          :class="{ 'is-active': isNavActive(item, route.path) }"
        >
          <Icon :name="item.icon" :size="20" />
          <span>{{ item.label }}</span>
        </router-link>
      </div>
    </nav>
  </div>

  <!-- 全局浮层 -->
  <AppToasts />
  <ConfirmHost />
  <HelpDrawer v-if="helpOpen" />
  <CommandPalette
    v-if="paletteOpen"
    :pages="navItems"
    :actions="paletteActions"
    @close="paletteOpen = false"
  />
</template>
