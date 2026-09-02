<script setup>
import { ref } from "vue"
import { useRouter } from "vue-router"
import Icon from "../components/Icon.vue"
import api, { setToken } from "../api"
import { loadMe } from "../auth"
import { t } from "../strings"

const router = useRouter()
const mode = ref("login") // login | register
const form = ref({ name: "", phone: "", password: "", email: "" })
const error = ref("")
const busy = ref(false)

async function submit() {
  error.value = ""
  busy.value = true
  try {
    const path = mode.value === "login" ? "/auth/login" : "/auth/register"
    const body =
      mode.value === "login"
        ? { phone: form.value.phone, password: form.value.password }
        : {
            name: form.value.name,
            phone: form.value.phone,
            password: form.value.password,
            email: form.value.email || null,
          }
    const res = await api.post(path, body)
    setToken(res.token)
    await loadMe()
    router.push(res.teacher?.is_admin ? "/admin" : "/")
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}

function fillDemo() {
  mode.value = "login"
  form.value.phone = "13800000001"
  form.value.password = "123456"
}
</script>

<template>
  <div class="auth-wrap">
    <div class="card auth-card">
      <div class="auth-mark"><Icon name="board" :size="24" /></div>
      <h1 class="auth-title">{{ t("app.title") }}</h1>
      <p class="auth-sub">{{ t("login.subtitle") }}</p>

      <div class="auth-tabs">
        <button :class="{ active: mode === 'login' }" @click="mode = 'login'">
          {{ t("login.tabLogin") }}
        </button>
        <button :class="{ active: mode === 'register' }" @click="mode = 'register'">
          {{ t("login.tabRegister") }}
        </button>
      </div>

      <form @submit.prevent="submit">
        <div v-if="mode === 'register'" class="field">
          <label>{{ t("login.name") }} *</label>
          <input v-model="form.name" type="text" required />
        </div>
        <div class="field">
          <label>{{ t("login.phone") }} *</label>
          <input v-model="form.phone" type="tel" required />
        </div>
        <div v-if="mode === 'register'" class="field">
          <label>{{ t("login.email") }}</label>
          <input v-model="form.email" type="email" />
        </div>
        <div class="field">
          <label>{{ t("login.password") }} *</label>
          <input v-model="form.password" type="password" required minlength="6" />
        </div>
        <p v-if="error" class="error-text">{{ error }}</p>
        <button type="submit" class="primary" style="width: 100%; margin-top: 6px" :disabled="busy">
          {{ (mode === "login" ? t("login.submit") : t("login.submitRegister")) + (busy ? "…" : "") }}
        </button>
      </form>

      <div class="demo-hint">
        <span>{{ t("login.demoHint") }}</span>
        <button class="small" @click="fillDemo">13800000001 / 123456</button>
      </div>
    </div>
  </div>
</template>
