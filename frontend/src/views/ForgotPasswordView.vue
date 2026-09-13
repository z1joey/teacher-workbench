<script setup>
// 忘记密码：两步——①邮箱发验证码 ②验证码+新密码重置。
// 后端对不存在的邮箱也返回成功（防账号枚举），前端统一提示"若已注册"。
import { computed, onUnmounted, ref } from "vue"
import { useRouter } from "vue-router"
import Icon from "../components/Icon.vue"
import FormField from "../components/FormField.vue"
import PasswordInput from "../components/PasswordInput.vue"
import api from "../api"
import { notify } from "../feedback"
import { friendlyError, t } from "../strings"

const router = useRouter()

const step = ref(1)
const email = ref("")
const code = ref("")
const newPassword = ref("")
const confirmPassword = ref("")

const error = ref("")
const sending = ref(false)
const submitting = ref(false)
const cooldown = ref(0)

let timer = 0

function startCooldown() {
  cooldown.value = 60
  clearInterval(timer)
  timer = setInterval(() => {
    cooldown.value -= 1
    if (cooldown.value <= 0) clearInterval(timer)
  }, 1000)
}

onUnmounted(() => clearInterval(timer))

const canSend = computed(() => email.value.trim() && cooldown.value <= 0 && !sending.value)
const canSubmit = computed(
  () =>
    code.value.trim() &&
    newPassword.value &&
    confirmPassword.value &&
    !submitting.value
)

function validateStep1() {
  if (!email.value.trim() || !email.value.includes("@")) return t("signup.emailInvalid")
  return ""
}

function validateStep2() {
  if (!code.value.trim()) return t("forgot.codeRequired")
  if (!newPassword.value) return t("forgot.passwordRequired")
  if (newPassword.value.length < 6) return t("signup.passwordShort")
  if (newPassword.value !== confirmPassword.value) return t("forgot.confirmMismatch")
  return ""
}

async function sendCode() {
  error.value = ""
  const invalid = validateStep1()
  if (invalid) {
    error.value = invalid
    return
  }
  sending.value = true
  try {
    await api.post("/auth/password/forgot", { email: email.value.trim() })
    step.value = 2
    startCooldown()
  } catch (e) {
    error.value = friendlyError(e)
  } finally {
    sending.value = false
  }
}

async function submit() {
  error.value = ""
  const invalid = validateStep2()
  if (invalid) {
    error.value = invalid
    return
  }
  submitting.value = true
  try {
    await api.post("/auth/password/reset", {
      email: email.value.trim(),
      code: code.value.trim(),
      new_password: newPassword.value,
    })
    notify({ tone: "ok", title: t("forgot.success"), timeout: 3600 })
    router.push("/login")
  } catch (e) {
    error.value = friendlyError(e)
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="auth-wrap">
    <div class="card auth-card">
      <div class="auth-mark"><Icon name="board" :size="24" /></div>
      <h1 class="auth-title">{{ t("forgot.title") }}</h1>
      <p class="muted" style="margin: 0 0 18px">{{ t("forgot.subtitle") }}</p>

      <form @submit.prevent="step === 1 ? sendCode() : submit()" novalidate>
        <FormField :label="t('forgot.emailLabel')" required>
          <input
            v-model="email"
            class="input"
            type="email"
            autocomplete="username"
            :disabled="step === 2"
          />
        </FormField>

        <template v-if="step === 2">
          <p class="field__hint" style="margin: -6px 0 14px">{{ t("forgot.sentHint") }}</p>

          <FormField :label="t('forgot.codeLabel')" required>
            <input
              v-model="code"
              class="input"
              type="text"
              inputmode="numeric"
              maxlength="6"
              :placeholder="t('forgot.codePlaceholder')"
              autocomplete="one-time-code"
            />
          </FormField>

          <FormField
            :label="t('forgot.newPasswordLabel')"
            required
            :hint="t('forgot.newPasswordHint')"
          >
            <PasswordInput v-model="newPassword" autocomplete="new-password" />
          </FormField>

          <FormField :label="t('forgot.confirmLabel')" required>
            <PasswordInput v-model="confirmPassword" autocomplete="new-password" />
          </FormField>
        </template>

        <p v-if="error" class="field__error" style="margin-bottom: 12px">
          <Icon name="alert-circle" :size="13" /> {{ error }}
        </p>

        <button
          type="submit"
          class="btn btn--primary btn--lg btn--block"
          :disabled="step === 1 ? !canSend : !canSubmit"
        >
          <span v-if="sending || submitting" class="spinner" />
          <template v-if="step === 1">
            {{ sending ? t("forgot.sending") : t("forgot.sendCode") }}
          </template>
          <template v-else>
            {{ submitting ? t("forgot.submitting") : t("forgot.submit") }}
          </template>
        </button>

        <p
          v-if="step === 2"
          class="muted"
          style="margin: 10px 0 0; text-align: center"
        >
          <template v-if="cooldown > 0">{{ t("forgot.resendIn", { n: cooldown }) }}</template>
          <a href="#" @click.prevent="sendCode" v-else>{{ t("forgot.sendCode") }}</a>
        </p>
      </form>

      <div class="auth-note">
        <p class="muted" style="margin: 0">
          <router-link to="/login">{{ t("forgot.backToLogin") }}</router-link>
        </p>
      </div>
    </div>
  </div>
</template>
