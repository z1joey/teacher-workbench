<script setup>
import { onMounted, ref } from "vue"
import api from "../../api"
import Icon from "../../components/Icon.vue"
import PageHeader from "../../components/PageHeader.vue"
import { ask } from "../../confirm"
import { notify } from "../../feedback"
import { friendlyError, t } from "../../strings"

const settings = ref({ registration_enabled: true })
const loadingSettings = ref(true)
const savingSettings = ref(false)
const resetting = ref(false)

async function loadSettings() {
  loadingSettings.value = true
  try {
    settings.value = await api.get("/admin/settings")
  } catch (e) {
    notify({ tone: "error", title: "设置加载失败", detail: friendlyError(e) })
  }
  loadingSettings.value = false
}

async function saveRegistrationEnabled() {
  savingSettings.value = true
  try {
    settings.value = await api.patch("/admin/settings", {
      registration_enabled: settings.value.registration_enabled,
    })
    notify({
      tone: "ok",
      title: settings.value.registration_enabled
        ? t("admin.registrationEnabledOn")
        : t("admin.registrationEnabledOff"),
      timeout: 2400,
    })
  } catch (e) {
    notify({ tone: "error", title: t("admin.error"), detail: friendlyError(e) })
    await loadSettings()
  } finally {
    savingSettings.value = false
  }
}

async function resetDb() {
  const ok = await ask({
    title: t("admin.resetDb"),
    message: t("admin.resetDbWarn"),
    consequences: [
      "所有学生、班级、考试、成绩、跟进记录都会消失。",
      "账号也会一并清空，你需要重新登录或初始化演示环境。",
    ],
    confirmLabel: t("admin.resetDb"),
    confirmWord: "重置数据库",
  })
  if (!ok) return
  resetting.value = true
  try {
    await api.post("/admin/db/reset")
    notify({ tone: "ok", title: t("admin.resetDbDone"), timeout: 4000 })
  } catch (e) {
    notify({ tone: "error", title: t("admin.error"), detail: friendlyError(e) })
  } finally {
    resetting.value = false
  }
}

onMounted(loadSettings)
</script>

<template>
  <PageHeader :title="t('admin.sectionSettings')" :subtitle="t('admin.subtitleSettings')" />

  <div class="card">
    <div class="card__head">
      <h2 class="card__title"><Icon name="sliders" :size="16" /> {{ t("admin.sectionSettingsGeneral") }}</h2>
    </div>
    <div class="card__body">
      <div v-if="loadingSettings" class="skeleton skeleton--row" />
      <label v-else class="check admin-setting-row">
        <input
          v-model="settings.registration_enabled"
          type="checkbox"
          :disabled="savingSettings"
          @change="saveRegistrationEnabled"
        />
        <span>
          <strong>{{ t("admin.registrationEnabled") }}</strong>
          <span class="muted admin-setting-row__desc">{{ t("admin.registrationEnabledDesc") }}</span>
        </span>
      </label>
    </div>
  </div>

  <div class="card card--danger">
    <div class="card__head">
      <div>
        <h2 class="card__title"><Icon name="alert" :size="16" /> {{ t("admin.sectionDanger") }}</h2>
        <p class="card__desc">{{ t("admin.dangerZoneDesc") }}</p>
      </div>
    </div>
    <div class="card__body">
      <button class="btn btn--danger-solid" :disabled="resetting" @click="resetDb">
        <Icon name="alert" :size="15" /> {{ t("admin.resetDb") }}
      </button>
    </div>
  </div>
</template>
