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
const form = ref({ name: "", phone: "", password: "", password2: "" })
const error = ref("")
const busy = ref(false)

async function submit() {
  error.value = ""
  if (!form.value.name.trim()) {
    error.value = t("signup.nameRequired")
    return
  }
  if (form.value.password !== form.value.password2) {
    error.value = t("signup.passwordMismatch")
    return
  }
  busy.value = true
  try {
    const res = await api.post("/auth/register", {
      name: form.value.name.trim(),
      phone: form.value.phone,
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
        <FormField :label="t('login.name')" :error="''">
          <input
            v-model="form.name"
            class="input"
            type="text"
            autocomplete="name"
            required
          />
        </FormField>

        <FormField :label="t('login.phone')" :error="''">
          <input
            v-model="form.phone"
            class="input"
            type="tel"
            inputmode="numeric"
            autocomplete="username"
            required
          />
        </FormField>

        <FormField :label="t('login.password')" :error="''">
          <PasswordInput
            v-model="form.password"
            autocomplete="new-password"
            minlength="6"
            required
          />
        </FormField>

        <FormField :label="t('signup.password2')" :error="''">
          <PasswordInput
            v-model="form.password2"
            autocomplete="new-password"
            minlength="6"
            required
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
