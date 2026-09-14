<script setup>
import { ref } from "vue"
import { useRouter } from "vue-router"
import Icon from "../components/Icon.vue"
import FormField from "../components/FormField.vue"
import PasswordInput from "../components/PasswordInput.vue"
import api, { setToken } from "../api"
import { loadMe } from "../auth"
import { notify } from "../feedback"
import { friendlyError, t } from "../strings"

const router = useRouter()
const form = ref({ email: "", password: "", password2: "" })
const errors = ref({ email: "", password: "", password2: "" })
const error = ref("")
const busy = ref(false)

function validate() {
  errors.value = { email: "", password: "", password2: "" }
  let ok = true
  const email = form.value.email.trim()
  if (!email) {
    errors.value.email = t("signup.emailRequired")
    ok = false
  } else if (!email.includes("@")) {
    errors.value.email = t("signup.emailInvalid")
    ok = false
  }
  if (form.value.password.length < 6) {
    errors.value.password = t("signup.passwordShort")
    ok = false
  }
  if (form.value.password2 !== form.value.password) {
    errors.value.password2 = t("signup.passwordMismatch")
    ok = false
  }
  return ok
}

async function submit() {
  error.value = ""
  if (!validate()) return
  busy.value = true
  try {
    const res = await api.post("/auth/register", {
      email: form.value.email.trim(),
      password: form.value.password,
    })
    setToken(res.token)
    await loadMe()
    notify({ tone: "ok", title: t("signup.success"), timeout: 4000 })
    await router.replace("/")
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
      <p class="auth-sub">{{ t("signup.subtitle") }}</p>

      <form @submit.prevent="submit" novalidate>
        <FormField
          :label="t('login.email')"
          required
          :error="errors.email || ''"
        >
          <input
            v-model="form.email"
            class="input"
            type="email"
            autocomplete="username"
            required
            :aria-invalid="!!errors.email"
          />
        </FormField>

        <FormField :label="t('login.password')" required :error="errors.password || ''">
          <PasswordInput
            v-model="form.password"
            autocomplete="new-password"
            minlength="6"
            required
            :invalid="!!errors.password"
          />
        </FormField>

        <FormField :label="t('signup.password2')" required :error="errors.password2 || ''">
          <PasswordInput
            v-model="form.password2"
            autocomplete="new-password"
            minlength="6"
            required
            :invalid="!!errors.password2"
          />
        </FormField>

        <p v-if="error" class="field__error" style="margin-bottom: 12px">
          <Icon name="alert-circle" :size="13" /> {{ error }}
        </p>

        <button type="submit" class="btn btn--primary btn--lg btn--block" :disabled="busy">
          <span v-if="busy" class="spinner" />
          {{ busy ? t("signup.submitting") : t("signup.submit") }}
        </button>
      </form>

      <div class="auth-note auth-note--center">
        <p class="muted" style="margin: 0">
          {{ t("signup.hasAccount") }}
          <router-link to="/login">{{ t("signup.goLogin") }}</router-link>
        </p>
      </div>
    </div>
  </div>
</template>
