<script setup>
import { ref } from "vue"
import api from "../../api"
import Icon from "../../components/Icon.vue"
import PageHeader from "../../components/PageHeader.vue"
import { ask } from "../../confirm"
import { notify } from "../../feedback"
import { friendlyError, t } from "../../strings"

const resetting = ref(false)

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
</script>

<template>
  <PageHeader :title="t('admin.sectionDanger')" :subtitle="t('admin.subtitleDanger')" />

  <div class="card card--danger">
    <div class="card__head">
      <div>
        <h2 class="card__title"><Icon name="alert" :size="16" /> {{ t("admin.sectionDanger") }}</h2>
        <p class="card__desc">这一区的操作不可撤销，执行前会要求你再次确认。</p>
      </div>
    </div>
    <div class="card__body">
      <button class="btn btn--danger-solid" :disabled="resetting" @click="resetDb">
        <Icon name="alert" :size="15" /> {{ t("admin.resetDb") }}
      </button>
    </div>
  </div>
</template>
