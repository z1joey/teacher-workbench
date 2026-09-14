<script setup>
// 登录：错误就地说明怎么改，而不是弹出一个看不懂的提示。
// 新用户请前往注册页。
import { ref } from "vue"
import { useRouter } from "vue-router"
import AppMeta from "../components/AppMeta.vue"
import Icon from "../components/Icon.vue"
import FormField from "../components/FormField.vue"
import PasswordInput from "../components/PasswordInput.vue"
import api, { setToken } from "../api"
import { loadMe } from "../auth"
import { friendlyError, t } from "../strings"

const router = useRouter()
const form = ref({ email: "", password: "" })
const error = ref("")
const busy = ref(false)

async function submit() {
  error.value = ""
  busy.value = true
  try {
    const res = await api.post("/auth/login", {
      email: form.value.email,
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
</script>

<template>
  <div class="auth-wrap">
    <div class="card auth-card">
      <div class="auth-mark"><Icon name="board" :size="24" /></div>
      <h1 class="auth-title">{{ t("app.title") }}</h1>
      <AppMeta layout="login" />

      <form @submit.prevent="submit" novalidate>
        <FormField :label="t('login.email')" required :error="''">
          <input
            v-model="form.email"
            class="input"
            type="email"
            autocomplete="username"
            required
          />
        </FormField>

        <FormField
          :label="t('login.password')"
          required
          :error="''"
        >
          <PasswordInput
            v-model="form.password"
            autocomplete="current-password"
            required
          />
        </FormField>

        <p v-if="error" class="field__error" style="margin-bottom: 12px">
          <Icon name="alert-circle" :size="13" /> {{ error }}
        </p>

        <button type="submit" class="btn btn--primary btn--lg btn--block" :disabled="busy">
          <span v-if="busy" class="spinner" />
          {{ busy ? t("login.submitting") : t("login.submit") }}
        </button>

        <p class="muted" style="margin: 10px 0 0; text-align: right">
          <router-link to="/forgot-password">{{ t("login.needHelp") }}</router-link>
        </p>
      </form>

      <div class="auth-note">
        <p class="muted" style="margin: 0">
          {{ t("login.noAccount") }}
          <router-link to="/signup">{{ t("login.goSignup") }}</router-link>
        </p>
      </div>
    </div>
  </div>
</template>
