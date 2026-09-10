<script setup>
// 班级首页：一个下拉框选班，选中班直接显示详情（含座位表）。
// 只有一个班时只显示班级名称；没有班时保留建班入口。
import { computed, onMounted, ref, watch } from "vue"
import { useRoute, useRouter } from "vue-router"
import Icon from "../components/Icon.vue"
import PageHeader from "../components/PageHeader.vue"
import AsyncState from "../components/AsyncState.vue"
import FormField from "../components/FormField.vue"
import ClassDetailContent from "../components/ClassDetailContent.vue"
import api from "../api"
import { notify } from "../feedback"
import { friendlyError, t } from "../strings"

const route = useRoute()
const router = useRouter()

const classes = ref([])
const loading = ref(true)
const error = ref("")

const showCreate = ref(false)
const creating = ref(false)
const createError = ref("")
const createForm = ref(emptyForm())

function emptyForm() {
  return { name: "", academic_year: defaultYear() }
}

function defaultYear() {
  const now = new Date()
  const start = now.getMonth() + 1 >= 8 ? now.getFullYear() : now.getFullYear() - 1
  return `${start}/${start + 1}`
}

async function load() {
  loading.value = true
  error.value = ""
  try {
    // 归档班级也取回：仅用于选中校验与深链接；默认展示由 ClassDetailContent 控制
    classes.value = await api.get("/classes?include_archived=1")
  } catch (e) {
    error.value = friendlyError(e)
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await load()
  if (route.query.create === "1") showCreate.value = true
})
watch(() => route.query.create, (v) => {
  if (v === "1") showCreate.value = true
})

// 选中班：URL ?class= 优先（须仍存在），否则第一个班
const selectedId = computed(() => {
  const raw = route.query.class
  const wanted = Array.isArray(raw) ? raw[0] : raw
  if (wanted && classes.value.some((c) => c.id === wanted)) return wanted
  return classes.value[0]?.id
})

function switchClass(id) {
  router.replace({ query: { ...route.query, class: id } })
}

function onClassChanged() {
  load()
}

async function createClass() {
  createError.value = ""
  if (!createForm.value.name.trim()) {
    createError.value = t("classes.nameRequired")
    return
  }
  creating.value = true
  try {
    const created = await api.post("/classes", {
      name: createForm.value.name.trim(),
      academic_year: createForm.value.academic_year.trim(),
    })
    createForm.value = emptyForm()
    showCreate.value = false
    notify({ tone: "ok", title: "班级已创建", timeout: 2600 })
    await load()
    if (created?.id) switchClass(created.id)
  } catch (e) {
    createError.value = friendlyError(e)
  } finally {
    creating.value = false
  }
}
</script>

<template>
  <!-- 没有班级时保留页头与建班入口；有班级时页头由班级内容自己提供 -->
  <PageHeader
    v-if="!loading && !error && !classes.length"
    :title="t('classes.title')"
  >
    <template #actions>
      <button class="btn btn--primary" @click="showCreate = !showCreate">
        <Icon :name="showCreate ? 'close' : 'plus'" :size="15" />
        {{ showCreate ? t("action.cancel") : t("classes.create") }}
      </button>
    </template>
  </PageHeader>

  <!-- 创建表单放在状态容器之外：空列表时也要能随页头按钮展开 -->
  <div v-if="showCreate" class="card" style="max-width: 620px; margin-bottom: var(--sp-5)">
    <div class="card__head">
      <h2 class="card__title"><Icon name="building" :size="16" /> {{ t("classes.create") }}</h2>
    </div>
    <form class="card__body" @submit.prevent="createClass">
      <div class="form-grid">
        <FormField :label="t('classes.name')" required>
          <input v-model="createForm.name" class="input" type="text" maxlength="60" />
        </FormField>
        <FormField :label="t('classes.year')" hint="跨年的学年，比如 2025/2026">
          <input v-model="createForm.academic_year" class="input" type="text" />
        </FormField>
      </div>

      <p v-if="createError" class="field__error" style="margin-bottom: 12px">
        <Icon name="alert-circle" :size="13" /> {{ createError }}
      </p>

      <div class="form-actions">
        <button type="submit" class="btn btn--primary" :disabled="creating">
          <span v-if="creating" class="spinner" />
          {{ creating ? t("classes.creating") : t("classes.create") }}
        </button>
        <button type="button" class="btn btn--ghost" @click="showCreate = false">
          {{ t("action.cancel") }}
        </button>
      </div>
    </form>
  </div>

  <AsyncState
    :loading="loading"
    :error="error"
    :empty="!loading && !error && !classes.length"
    :empty-title="t('classes.emptyTitle')"
    :empty-desc="t('classes.emptyDesc')"
    empty-icon="building"
    @retry="load"
  >
    <ClassDetailContent
      v-if="selectedId"
      :class-id="selectedId"
      @switch="switchClass"
      @create="showCreate = true"
      @changed="onClassChanged"
    />
  </AsyncState>
</template>
