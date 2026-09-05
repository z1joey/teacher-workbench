<script setup>
// 登录：错误就地说明怎么改，而不是弹出一个看不懂的提示。
// 单教师应用：账号来自初始化数据，不提供自助注册。
import { ref } from "vue"
import { useRouter } from "vue-router"
import Icon from "../components/Icon.vue"
import FormField from "../components/FormField.vue"
import api, { setToken } from "../api"
import { loadMe } from "../auth"
import { friendlyError, t } from "../strings"

const router = useRouter()
const form = ref({ phone: "", password: "" })
const error = ref("")
const busy = ref(false)
const showPassword = ref(false)

async function submit() {
  error.value = ""
  busy.value = true
  try {
    const res = await api.post("/auth/login", {
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

function fillDemo() {
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
          :error="''"
        >
          <div class="row" style="gap: 8px">
            <input
              v-model="form.password"
              class="input"
              :type="showPassword ? 'text' : 'password'"
              autocomplete="current-password"
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

        <p v-if="error" class="field__error" style="margin-bottom: 12px">
          <Icon name="alert-circle" :size="13" /> {{ error }}
        </p>

        <button type="submit" class="btn btn--primary btn--lg btn--block" :disabled="busy">
          <span v-if="busy" class="spinner" />
          {{ busy ? t("login.submitting") : t("login.submit") }}
        </button>
      </form>

      <div class="auth-note">
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
