<script setup>
// 登录 / 注册：错误就地说明怎么改，而不是弹出一个看不懂的提示
import { computed, ref } from "vue"
import { useRouter } from "vue-router"
import Icon from "../components/Icon.vue"
import FormField from "../components/FormField.vue"
import api, { setToken } from "../api"
import { loadMe } from "../auth"
import { friendlyError, t } from "../strings"

const router = useRouter()
const mode = ref("login") // login | register
const form = ref({ phone: "", password: "", password2: "" })
const error = ref("")
const busy = ref(false)
const showPassword = ref(false)
const errors = ref({})

function validate() {
  const e = {}
  if (mode.value === "register" && form.value.password.length < 6) {
    e.password = t("login.passwordTooShort")
  }
  if (mode.value === "register" && form.value.password !== form.value.password2) {
    e.password2 = t("login.passwordMismatch")
  }
  errors.value = e
  return !Object.keys(e).length
}

async function submit() {
  error.value = ""
  if (!validate()) return
  busy.value = true
  try {
    const path = mode.value === "login" ? "/auth/login" : "/auth/register"
    const res = await api.post(path, {
      phone: form.value.phone,
      password: form.value.password,
    })
    setToken(res.token)
    await loadMe()
    router.push(res.user?.role === "admin" ? "/admin" : "/")
  } catch (e) {
    error.value = friendlyError(e)
  } finally {
    busy.value = false
  }
}

function switchMode(next) {
  mode.value = next
  error.value = ""
  errors.value = {}
}

function fillDemo() {
  switchMode("login")
  form.value.phone = "13800000001"
  form.value.password = "123456"
}

const submitLabel = computed(() =>
  mode.value === "login" ? t("login.submit") : t("login.submitRegister")
)
</script>

<template>
  <div class="auth-wrap">
    <div class="card auth-card">
      <div class="auth-mark"><Icon name="board" :size="24" /></div>
      <h1 class="auth-title">{{ t("app.title") }}</h1>
      <p class="auth-sub">{{ t("login.subtitle") }}</p>

      <div class="segmented" style="width: 100%; margin-bottom: 20px" role="tablist">
        <button
          class="segmented__item"
          :class="{ 'is-active': mode === 'login' }"
          role="tab"
          :aria-selected="mode === 'login'"
          @click="switchMode('login')"
        >{{ t("login.tabLogin") }}</button>
        <button
          class="segmented__item"
          :class="{ 'is-active': mode === 'register' }"
          role="tab"
          :aria-selected="mode === 'register'"
          @click="switchMode('register')"
        >{{ t("login.tabRegister") }}</button>
      </div>

      <form @submit.prevent="submit" novalidate>
        <FormField :label="t('login.phone')" required :error="''">
          <input
            v-model="form.phone"
            class="input"
            type="tel"
            inputmode="numeric"
            autocomplete="username"
            required
          />
        </FormField>

        <FormField
          :label="t('login.password')"
          required
          :error="errors.password || ''"
        >
          <div class="row" style="gap: 8px">
            <input
              v-model="form.password"
              class="input"
              :type="showPassword ? 'text' : 'password'"
              :autocomplete="mode === 'login' ? 'current-password' : 'new-password'"
              required
            />
            <button
              type="button"
              class="btn btn--icon"
              :aria-label="showPassword ? '隐藏密码' : '显示密码'"
              :title="showPassword ? '隐藏密码' : '显示密码'"
              @click="showPassword = !showPassword"
            >
              <Icon :name="showPassword ? 'eye-off' : 'eye'" :size="15" />
            </button>
          </div>
        </FormField>

        <FormField
          v-if="mode === 'register'"
          :label="t('login.password2')"
          required
          :error="errors.password2 || ''"
        >
          <input
            v-model="form.password2"
            class="input"
            type="password"
            autocomplete="new-password"
            required
          />
        </FormField>

        <p v-if="error" class="field__error" style="margin-bottom: 12px">
          <Icon name="alert-circle" :size="13" /> {{ error }}
        </p>

        <button type="submit" class="btn btn--primary btn--lg btn--block" :disabled="busy">
          <span v-if="busy" class="spinner" />
          {{ busy ? t("login.submitting") : submitLabel }}
        </button>
      </form>

      <div v-if="mode === 'register'" class="auth-note auth-note--center">
        {{ t("login.minimalHint") }}
      </div>

      <div v-else class="auth-note">
        <span class="row nowrap" style="gap: 6px">
          <Icon name="info" :size="14" />
          {{ t("login.needHelp") }}
        </span>
        <button class="btn btn--sm nowrap" @click="fillDemo">
          {{ t("login.demoHint") }}：13800000001 / 123456
        </button>
      </div>
    </div>
  </div>
</template>
