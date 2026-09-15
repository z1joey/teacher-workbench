<script setup>
// 个人中心：资料、偏好设置、教学足迹。退出登录需要确认，避免误触。
import { computed, onMounted, ref } from "vue"
import { useRouter } from "vue-router"
import Icon from "../components/Icon.vue"
import SelectMenu from "../components/SelectMenu.vue"
import DataView from "./DataView.vue"
import PageHeader from "../components/PageHeader.vue"
import AsyncState from "../components/AsyncState.vue"
import FormField from "../components/FormField.vue"
import PasswordInput from "../components/PasswordInput.vue"
import api, { setToken } from "../api"
import { clearMe, me } from "../auth"
import { ask } from "../confirm"
import { notify } from "../feedback"
import { clearAll } from "../feedback"
import { clearSearch } from "../search"
import { formatEnrollmentMonth, friendlyError, t } from "../strings"

const router = useRouter()

const profile = ref(null)
const error = ref("")
const loading = ref(true)
const editing = ref(false)
const saving = ref(false)
const editForm = ref({ name: "", phone: "" })
const errors = ref({})
const settingsSaving = ref(false)
const clearingHomeVisitTags = ref(false)

// 修改密码：验证当前密码；成功后其他设备自动下线，当前设备不受影响
const pwdEditing = ref(false)
const pwdForm = ref({ current: "", next: "", confirm: "" })
const pwdSaving = ref(false)
const pwdErrors = ref({})

function startPwdEdit() {
  editing.value = false
  pwdForm.value = { current: "", next: "", confirm: "" }
  pwdErrors.value = {}
  pwdEditing.value = true
}

function cancelPwdEdit() {
  pwdEditing.value = false
  pwdForm.value = { current: "", next: "", confirm: "" }
  pwdErrors.value = {}
}

async function changePassword() {
  pwdErrors.value = {}
  if (!pwdForm.value.current) {
    pwdErrors.value.current = "请输入当前密码"
    return
  }
  if (pwdForm.value.next.length < 6) {
    pwdErrors.value.next = "新密码至少 6 位"
    return
  }
  if (pwdForm.value.next !== pwdForm.value.confirm) {
    pwdErrors.value.confirm = "两次输入的新密码不一致"
    return
  }
  pwdSaving.value = true
  try {
    await api.post("/auth/password/change", {
      current_password: pwdForm.value.current,
      new_password: pwdForm.value.next,
    })
    notify({ tone: "ok", title: "密码已修改", detail: "其他设备已退出登录", timeout: 3600 })
    pwdEditing.value = false
    pwdForm.value = { current: "", next: "", confirm: "" }
  } catch (e) {
    notify({ tone: "error", title: "修改失败", detail: friendlyError(e) })
  } finally {
    pwdSaving.value = false
  }
}

function normalizePhone(phone) {
  return phone.replace(/[\s-]/g, "")
}

async function clearHomeVisitTags() {
  const ok = await ask({
    title: t("profile.clearHomeVisitTags"),
    message: t("profile.clearHomeVisitTagsConfirm"),
    confirmLabel: t("profile.clearHomeVisitTags"),
    tone: "warn",
  })
  if (!ok) return
  clearingHomeVisitTags.value = true
  error.value = ""
  try {
    const { removed } = await api.post("/profile/clear-home-visit-tags")
    notify({
      tone: removed ? "ok" : "info",
      title: removed
        ? t("profile.clearHomeVisitTagsDone", { n: removed })
        : t("profile.clearHomeVisitTagsEmpty"),
      timeout: 2800,
    })
  } catch (e) {
    error.value = friendlyError(e)
  } finally {
    clearingHomeVisitTags.value = false
  }
}

async function saveSettings() {
  if (!profile.value) return
  settingsSaving.value = true
  error.value = ""
  try {
    const updated = await api.patch("/profile", {
      name: profile.value.user.name,
      phone: profile.value.user.phone || null,
      auto_tags: profile.value.settings.auto_tags,
      calendar_birthdays: profile.value.settings.calendar_birthdays,
    })
    profile.value.settings = updated.settings
    profile.value.user = { ...profile.value.user, ...updated }
    if (me.value) {
      me.value = {
        ...me.value,
        name: updated.name,
        display_name: updated.display_name,
      }
    }
    notify({ tone: "ok", title: t("profile.settingsSaved"), timeout: 2400 })
  } catch (e) {
    error.value = friendlyError(e)
  } finally {
    settingsSaving.value = false
  }
}

async function load() {
  loading.value = true
  error.value = ""
  try {
    profile.value = await api.get("/profile")
  } catch (e) {
    profile.value = null
    error.value = friendlyError(e)
  } finally {
    loading.value = false
  }
}
onMounted(load)

function startEdit() {
  pwdEditing.value = false
  const user = profile.value.user
  editForm.value = { name: user.name || "", phone: user.phone || "" }
  errors.value = {}
  editing.value = true
}
function cancelEdit() {
  editing.value = false
  errors.value = {}
}

function validate() {
  const e = {}
  const phone = normalizePhone(editForm.value.phone.trim())
  if (editForm.value.phone.trim() && !/^\d{6,15}$/.test(phone)) {
    e.phone = t("profile.phoneInvalid")
  }
  errors.value = e
  return !Object.keys(e).length
}

async function saveProfile() {
  if (!validate()) return
  saving.value = true
  error.value = ""
  try {
    const phoneRaw = editForm.value.phone.trim()
    const updated = await api.patch("/profile", {
      name: editForm.value.name.trim(),
      phone: phoneRaw ? normalizePhone(phoneRaw) : null,
    })
    profile.value.user = { ...profile.value.user, ...updated }
    if (me.value) {
      me.value = {
        ...me.value,
        name: updated.name,
        display_name: updated.display_name,
      }
    }
    editing.value = false
    notify({ tone: "ok", title: t("profile.saved"), timeout: 2400 })
  } catch (e) {
    error.value = friendlyError(e)
  } finally {
    saving.value = false
  }
}

// 毕业操作：个人中心集中入口。毕业不会删除数据，班级转为已归档。
const graduatingClassId = ref("")
const graduating = ref(false)
// 归档班级名单默认收起，点「查看名单」展开
const expandedClasses = ref(new Set())

function toggleRoster(id) {
  const next = new Set(expandedClasses.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  expandedClasses.value = next
}

async function graduateClass() {
  const cls = profile.value.classes.find((c) => c.id === graduatingClassId.value)
  if (!cls) return
  const ok = await ask({
    title: t("profile.graduateConfirmTitle", { n: cls.students.length, class: cls.name }),
    message: t("profile.graduateConfirmHint"),
    confirmLabel: t("profile.graduateConfirm"),
    tone: "warn",
  })
  if (!ok) return
  graduating.value = true
  error.value = ""
  try {
    const res = await api.post(`/classes/${cls.id}/graduate`)
    notify({ tone: "ok", title: t("profile.graduateDone", { n: res.graduated }), timeout: 3200 })
    graduatingClassId.value = ""
    await load()
  } catch (e) {
    error.value = friendlyError(e)
  } finally {
    graduating.value = false
  }
}

async function logout() {
  const ok = await ask({
    title: "退出登录？",
    message: "退出后需要重新输入邮箱和密码。",
    confirmLabel: t("auth.logout"),
    tone: "warn",
  })
  if (!ok) return
  try {
    await api.post("/auth/logout")
  } catch {
    // token already invalid — clearing locally is enough
  }
  setToken(null)
  clearMe()
  clearSearch()
  clearAll()
  await router.replace("/login")
}

const activity = computed(() => {
  if (!profile.value) return []
  const s = profile.value.stats
  return [
    { label: t("profile.recordsLogged"), value: s.interactions, icon: "checklist" },
    { label: t("profile.resultsEntered"), value: s.results_entered, icon: "clipboard" },
    { label: t("profile.commentsWritten"), value: s.comments_written, icon: "note" },
  ]
})
</script>

<template>
  <PageHeader :title="t('profile.title')" :subtitle="t('profile.subtitle')" />

  <AsyncState
    :loading="loading"
    :error="error"
    :empty="!loading && !error && !profile"
    empty-title="个人资料没能加载"
    empty-desc="请检查网络连接后重试。"
    :rows="4"
    @retry="load"
  >
    <div>
      <!-- 资料 -->
        <div class="card">
          <div class="card__head">
            <h2 class="card__title"><Icon name="user" :size="16" /> 基本资料</h2>
            <div v-if="!editing && !pwdEditing" class="row" style="gap: 8px">
              <button type="button" class="btn btn--sm" @click="startPwdEdit">
                <Icon name="lock" :size="13" /> 修改密码
              </button>
              <button type="button" class="btn btn--sm" @click="startEdit">
                <Icon name="pencil" :size="13" /> {{ t("profile.editInfo") }}
              </button>
            </div>
          </div>

          <div v-if="!editing && !pwdEditing" class="card__body">
            <div class="row" style="gap: 14px; align-items: flex-start">
              <span class="avatar avatar--lg">{{ (profile.user.display_name || profile.user.name || "?").charAt(0) }}</span>
              <div class="grow">
                <p style="font-size: 17px; font-weight: 600">{{ profile.user.display_name || profile.user.name }}</p>
                <div class="row-wrap" style="margin-top: 6px">
                  <span class="pill pill--outline">
                    {{ t("profile.loginEmail") }}：{{ profile.user.email }}
                  </span>
                  <span v-if="profile.user.phone" class="pill pill--outline">
                    {{ t("profile.phone") }}：{{ profile.user.phone }}
                  </span>
                </div>
              </div>
            </div>
          </div>

          <form v-else-if="editing" class="card__body" @submit.prevent="saveProfile">
            <div class="form-grid">
              <FormField
                :label="t('login.name')"
                optional
                :hint="t('profile.nameHint')"
                :error="errors.name || ''"
              >
                <input v-model="editForm.name" class="input" type="text" maxlength="100" :aria-invalid="!!errors.name" />
              </FormField>
              <FormField
                :label="t('profile.phone')"
                optional
                :error="errors.phone || ''"
                :hint="t('profile.phoneHint')"
              >
                <input
                  v-model="editForm.phone"
                  class="input"
                  type="tel"
                  inputmode="numeric"
                  :aria-invalid="!!errors.phone"
                />
              </FormField>
            </div>
            <div class="form-actions">
              <button type="submit" class="btn btn--primary" :disabled="saving">
                <span v-if="saving" class="spinner" />
                {{ saving ? t("action.saving") : t("action.save") }}
              </button>
              <button type="button" class="btn btn--ghost" @click="cancelEdit">
                {{ t("action.cancel") }}
              </button>
            </div>
          </form>

          <form v-else-if="pwdEditing" class="card__body" @submit.prevent="changePassword">
            <div class="form-grid">
              <FormField label="当前密码" required :error="pwdErrors.current || ''">
                <PasswordInput
                  v-model="pwdForm.current"
                  autocomplete="current-password"
                  :invalid="!!pwdErrors.current"
                />
              </FormField>
              <FormField label="新密码" required :error="pwdErrors.next || ''" hint="至少 6 位">
                <PasswordInput
                  v-model="pwdForm.next"
                  autocomplete="new-password"
                  :invalid="!!pwdErrors.next"
                  :minlength="6"
                />
              </FormField>
              <FormField label="确认新密码" required :error="pwdErrors.confirm || ''">
                <PasswordInput
                  v-model="pwdForm.confirm"
                  autocomplete="new-password"
                  :invalid="!!pwdErrors.confirm"
                />
              </FormField>
            </div>
            <div class="form-actions">
              <button type="submit" class="btn btn--primary" :disabled="pwdSaving">
                <span v-if="pwdSaving" class="spinner" />
                {{ pwdSaving ? t("action.saving") : "修改密码" }}
              </button>
              <button type="button" class="btn btn--ghost" @click="cancelPwdEdit">
                {{ t("action.cancel") }}
              </button>
            </div>
          </form>

          <!-- 教学足迹：1 行 3 列 -->
          <div class="profile-stats">
            <div v-for="a in activity" :key="a.label" class="profile-stat">
              <div class="profile-stat__value">{{ a.value }}</div>
              <div class="profile-stat__label">{{ a.label }}</div>
            </div>
          </div>
        </div>

        <!-- 偏好设置 -->
        <div class="card">
          <div class="card__head">
            <h2 class="card__title"><Icon name="sliders" :size="16" /> {{ t("profile.settings") }}</h2>
          </div>
          <div class="card__body profile-panel">
            <div class="profile-section">
              <label class="check">
                <input
                  v-model="profile.settings.auto_tags"
                  type="checkbox"
                  :disabled="settingsSaving"
                  @change="saveSettings"
                />
                <span>{{ t("profile.autoTags") }}</span>
              </label>
              <p class="field__hint" style="margin-top: 8px">{{ t("profile.autoTagsHint") }}</p>
            </div>
            <div class="profile-section">
              <label class="check">
                <input
                  v-model="profile.settings.calendar_birthdays"
                  type="checkbox"
                  :disabled="settingsSaving"
                  @change="saveSettings"
                />
                <span>{{ t("profile.calendarBirthdays") }}</span>
              </label>
              <p class="field__hint" style="margin-top: 8px">{{ t("profile.calendarBirthdaysHint") }}</p>
            </div>
            <div class="profile-section">
              <p style="font-weight: 600; margin: 0">{{ t("profile.clearHomeVisitTags") }}</p>
              <p class="field__hint" style="margin-top: 8px">{{ t("profile.clearHomeVisitTagsHint") }}</p>
              <button
                type="button"
                class="btn btn--sm"
                style="margin-top: 12px"
                :disabled="clearingHomeVisitTags || settingsSaving"
                @click="clearHomeVisitTags"
              >
                <span v-if="clearingHomeVisitTags" class="spinner" />
                {{ t("profile.clearHomeVisitTags") }}
              </button>
            </div>
          </div>
        </div>

        <!-- 毕业归档：标记毕业 + 查看归档班级与毕业生（名单默认收起） -->
        <div class="card">
          <div class="card__head">
            <div>
              <h2 class="card__title"><Icon name="flag" :size="16" /> {{ t("profile.graduatedArchive") }}</h2>
              <p class="card__desc">{{ t("profile.graduatedArchiveHint") }}</p>
            </div>
          </div>
          <div class="card__body">
            <div v-if="profile.classes.length" class="row" style="gap: 10px; flex-wrap: wrap; align-items: center; margin-bottom: 16px">
              <SelectMenu
                v-model="graduatingClassId"
                :options="profile.classes.map((c) => ({ value: c.id, label: `${c.name}（${c.students.length} 人）` }))"
                placeholder="选择班级"
                aria-label="选择要毕业的班级"
                :disabled="graduating"
                trigger-class="input input--sm"
              />
              <button
                type="button"
                class="btn btn--sm"
                :disabled="graduating || !graduatingClassId"
                @click="graduateClass"
              >
                <span v-if="graduating" class="spinner" />
                {{ t("profile.graduateAction") }}
              </button>
            </div>

            <p v-if="error" class="field__error" style="margin-bottom: 12px">
              <Icon name="alert-circle" :size="12" /> {{ error }}
            </p>

            <div v-if="profile.archived_classes.length" class="stack" style="gap: 12px">
              <div v-for="c in profile.archived_classes" :key="c.id" class="stack" style="gap: 8px">
                <div class="row" style="gap: 10px; flex-wrap: wrap; align-items: center; justify-content: space-between">
                  <div class="row-wrap" style="align-items: center">
                    <router-link :to="`/classes/${c.id}`" class="pill">
                      {{ c.name }} <span class="muted" style="font-weight: 400">{{ t("profile.graduatedSuffix") }}</span>
                    </router-link>
                    <span class="stat__sub">
                      {{ formatEnrollmentMonth(c.academic_year) }}
                      <template v-if="c.students.length"> · {{ t("profile.studentsCount", { n: c.students.length }) }}</template>
                    </span>
                  </div>
                  <button
                    v-if="c.students.length"
                    type="button"
                    class="btn btn--sm btn--ghost"
                    @click="toggleRoster(c.id)"
                  >
                    {{ expandedClasses.has(c.id) ? t("profile.hideRoster") : t("profile.viewRoster") }}
                  </button>
                </div>
                <div v-if="expandedClasses.has(c.id) && c.students.length" class="chips" style="padding-left: 4px">
                  <router-link
                    v-for="s in c.students"
                    :key="s.id"
                    :to="`/students/${s.id}`"
                    class="chip"
                  >
                    {{ s.name }}
                    <span class="muted" style="font-size: 12px">{{ s.admission_no }}</span>
                  </router-link>
                </div>
              </div>
            </div>
            <p v-else class="muted" style="margin: 0">{{ t("profile.noArchivedClasses") }}</p>
          </div>
        </div>
      </div>

      <!-- 数据管理：导入导出与演示数据（原「数据」页并入） -->
      <DataView />

      <div class="form-actions" style="justify-content: center">
        <button type="button" class="btn btn--danger" @click="logout">
          <Icon name="logout" :size="15" /> {{ t("auth.logout") }}
        </button>
      </div>
  </AsyncState>
</template>
