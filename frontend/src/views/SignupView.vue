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
const errors = ref({ name: "", phone: "", password: "", password2: "" })
const error = ref("")
const busy = ref(false)

// 与后端 /auth/register 同规则：去掉空格/短横线后须为 6-15 位数字
function normalizePhone(phone) {
  return phone.replace(/[\s-]/g, "")
}

// 就地校验：错误出现在各自的输入框下，而不是提交后才弹一条笼统提示
function validate() {
  errors.value = { name: "", phone: "", password: "", password2: "" }
  let ok = true
  if (!form.value.name.trim()) {
    errors.value.name = t("signup.nameRequired")
    ok = false
  }
  const phone = normalizePhone(form.value.phone.trim())
  if (!phone) {
    errors.value.phone = t("signup.phoneRequired")
    ok = false
  } else if (!/^\d{6,15}$/.test(phone)) {
    errors.value.phone = t("signup.phoneInvalid")
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
      name: form.value.name.trim(),
      phone: normalizePhone(form.value.phone.trim()),
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
        <FormField :label="t('login.name')" required :error="errors.name || ''">
          <input
            v-model="form.name"
            class="input"
            type="text"
            autocomplete="name"
            required
            :aria-invalid="!!errors.name"
          />
        </FormField>

        <FormField
          :label="t('login.phone')"
          required
          :error="errors.phone || ''"
          :hint="t('signup.phoneHint')"
        >
          <input
            v-model="form.phone"
            class="input"
            type="tel"
            inputmode="numeric"
            autocomplete="username"
            required
            :aria-invalid="!!errors.phone"
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
