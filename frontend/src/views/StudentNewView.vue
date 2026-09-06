<script setup>
// 添加学生：必填项标星并在提交时就地报错；没有班级时给出可执行的下一步，
// 而不是让用户卡在一个空下拉框上。
import { computed, onMounted, ref } from "vue"
import { useRouter } from "vue-router"
import Icon from "../components/Icon.vue"
import PageHeader from "../components/PageHeader.vue"
import FormField from "../components/FormField.vue"
import AsyncState from "../components/AsyncState.vue"
import api from "../api"
import { friendlyError, GENDER_OPTIONS, t } from "../strings"

const router = useRouter()
const classes = ref([])
const loading = ref(true)
const loadError = ref("")

const form = ref({
  name: "",
  gender: "",
  birth_date: "",
  guardian_name: "",
  guardian_phone: "",
  address: "",
  class_id: null,
})
const busy = ref(false)
const error = ref("")
const errors = ref({})
const guardianOpen = ref(false)

const hasClasses = computed(() => classes.value.length > 0)

async function loadClasses() {
  loading.value = true
  loadError.value = ""
  try {
    classes.value = await api.get("/classes")
  } catch (e) {
    loadError.value = friendlyError(e)
  } finally {
    loading.value = false
  }
}
onMounted(loadClasses)

function validate() {
  const e = {}
  if (!form.value.name.trim()) e.name = t("new.nameRequired")
  if (!form.value.class_id) e.class_id = t("new.classRequired")
  errors.value = e
  return !Object.keys(e).length
}

async function submit() {
  error.value = ""
  if (!validate()) return
  busy.value = true
  try {
    const res = await api.post("/students", {
      name: form.value.name.trim(),
      gender: form.value.gender || null,
      birth_date: form.value.birth_date || null,
      guardian_name: form.value.guardian_name || null,
      guardian_phone: form.value.guardian_phone || null,
      address: form.value.address || null,
      class_id: Number(form.value.class_id),
    })
    router.push(`/students/${res.id}`)
  } catch (e) {
    error.value = friendlyError(e)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <PageHeader :title="t('new.title')" :subtitle="t('new.subtitle')" />

  <AsyncState :loading="loading" :error="loadError" :rows="4" @retry="loadClasses">
    <div class="card" style="max-width: 620px">
      <form class="card__body" @submit.prevent="submit" novalidate>
        <h2 class="section-title" style="margin-bottom: 14px">{{ t("new.sectionBasic") }}</h2>

        <FormField :label="t('new.name')" required :error="errors.name || ''">
          <input
            v-model="form.name"
            class="input"
            type="text"
            maxlength="100"
            :aria-invalid="!!errors.name"
          />
        </FormField>

        <div class="form-grid">
          <FormField :label="t('new.gender')" optional>
            <select v-model="form.gender" class="select">
              <option v-for="g in GENDER_OPTIONS" :key="g.value" :value="g.value">{{ g.label }}</option>
            </select>
          </FormField>

          <FormField :label="t('new.birthDate')" optional>
            <input v-model="form.birth_date" class="input" type="date" />
          </FormField>
        </div>

        <!-- 监护人信息默认收起：不是每个学生入学时都能拿到 -->
        <div class="disclosure" :class="{ open: guardianOpen }">
          <button
            class="disclosure__head"
            type="button"
            :aria-expanded="guardianOpen"
            aria-controls="guardian-body"
            @click="guardianOpen = !guardianOpen"
          >
            <span class="section-title">
              {{ t("new.sectionGuardian") }}
              <span class="disclosure__hint">（{{ guardianOpen ? t("action.collapse") : "可选，点击展开" }}）</span>
            </span>
            <Icon :name="guardianOpen ? 'chevron-up' : 'chevron-down'" :size="16" />
          </button>
          <div v-show="guardianOpen" id="guardian-body" class="disclosure__body">
            <div class="form-grid">
              <FormField :label="t('new.guardianName')" optional>
                <input v-model="form.guardian_name" class="input" type="text" />
              </FormField>
              <FormField
                :label="t('new.guardianPhone')"
                optional
                hint="用于家访和家长沟通时联系"
              >
                <input v-model="form.guardian_phone" class="input" type="tel" maxlength="40" />
              </FormField>
            </div>
            <FormField :label="t('new.address')" optional>
              <input v-model="form.address" class="input" type="text" />
            </FormField>
          </div>
        </div>

        <h2 class="section-title" style="margin: 20px 0 14px">{{ t("new.sectionClass") }}</h2>

        <FormField
          :label="t('new.class')"
          required
          :error="errors.class_id || ''"
          :hint="hasClasses ? '' : t('new.noClassYet')"
        >
          <select v-model="form.class_id" class="select" :aria-invalid="!!errors.class_id">
            <option :value="null" disabled>{{ t("new.classPlaceholder") }}</option>
            <option v-for="c in classes" :key="c.id" :value="c.id">
              {{ c.name }} · {{ c.academic_year }}（{{ t("profile.studentsCount", { n: c.student_count } ) }}）
            </option>
          </select>
        </FormField>

        <p v-if="error" class="field__error" style="margin-bottom: 12px">
          <Icon name="alert-circle" :size="13" /> {{ error }}
        </p>

        <div class="form-actions">
          <button type="submit" class="btn btn--primary" :disabled="busy || !hasClasses">
            <span v-if="busy" class="spinner" />
            {{ busy ? t("new.saving") : t("new.submit") }}
          </button>
          <router-link to="/students" class="btn btn--ghost">{{ t("action.cancel") }}</router-link>
          <span v-if="!hasClasses" class="form-actions__spacer" />
          <router-link
            v-if="!hasClasses"
            to="/classes?create=1"
            class="btn btn--primary"
          >{{ t("classes.create") }}</router-link>
        </div>
      </form>
    </div>
  </AsyncState>
</template>
