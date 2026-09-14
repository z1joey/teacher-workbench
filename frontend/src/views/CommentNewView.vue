<script setup>
// 记录（原评语）新建 / 编辑：可 @ 其他学生；所有相关学生的时间线都会出现这条记录。
import { computed, onMounted, ref } from "vue"
import { useRouter } from "vue-router"
import Icon from "../components/Icon.vue"
import PageHeader from "../components/PageHeader.vue"
import FormField from "../components/FormField.vue"
import api from "../api"
import { ask } from "../confirm"
import { notify, runUndoable } from "../feedback"
import { friendlyError, t } from "../strings"

const props = defineProps({
  studentId: { type: String, default: null },
  eventId: { type: String, default: null },
})

const router = useRouter()
const isEdit = computed(() => !!props.eventId)
const resolvedStudentId = ref(props.studentId)

const today = new Date().toISOString().slice(0, 10)
const form = ref({ date: today, notes: "" })
const students = ref([])
const mentioned = ref(new Set())
const mentionQuery = ref("")
const mentionOpen = ref(false)
const loading = ref(true)
const busy = ref(false)
const error = ref("")
const errors = ref({})

onMounted(async () => {
  try {
    if (isEdit.value) {
      const comment = await api.get(`/comments/${props.eventId}`)
      resolvedStudentId.value = comment.student_id
      form.value.notes = comment.notes || ""
      form.value.date = comment.occurred_at ? comment.occurred_at.slice(0, 10) : today
      mentioned.value = new Set((comment.mentioned || []).map((m) => m.id))
    }
    const sid = resolvedStudentId.value
    if (!sid) {
      error.value = "找不到对应的学生"
      return
    }
    const [student, roster] = await Promise.all([
      api.get(`/students/${sid}`),
      api.get("/students"),
    ])
    students.value = roster.filter((s) => s.status === "active")
    if (!student?.id) error.value = "找不到对应的学生"
  } catch (e) {
    error.value = friendlyError(e)
  } finally {
    loading.value = false
  }
})

const primaryStudent = computed(() =>
  students.value.find((s) => s.id === resolvedStudentId.value) ?? null
)

const mentionCandidates = computed(() => {
  const q = mentionQuery.value.trim().toLowerCase()
  const sid = resolvedStudentId.value
  return students.value.filter((s) => {
    if (s.id === sid) return false
    if (!q) return true
    return (
      s.name.toLowerCase().includes(q) ||
      s.admission_no.toLowerCase().includes(q) ||
      (s.class?.name ?? "").toLowerCase().includes(q)
    )
  })
})

function toggleMention(id) {
  const next = new Set(mentioned.value)
  next.has(id) ? next.delete(id) : next.add(id)
  mentioned.value = next
}

function validate() {
  const e = {}
  if (!form.value.notes.trim()) e.notes = t("commentNew.notesRequired")
  errors.value = e
  return !Object.keys(e).length
}

async function submit() {
  error.value = ""
  if (!validate()) return
  busy.value = true
  try {
    const body = {
      notes: form.value.notes.trim(),
      mentioned_student_ids: [...mentioned.value],
      occurred_at: form.value.date ? `${form.value.date}T09:00:00` : null,
    }
    if (isEdit.value) {
      await api.patch(`/comments/${props.eventId}`, body)
      notify({ tone: "ok", title: t("common.saved"), timeout: 2400 })
    } else {
      await api.post("/comments", { student_id: resolvedStudentId.value, ...body })
      notify({ tone: "ok", title: "已保存记录", timeout: 2400 })
    }
    router.push(`/students/${resolvedStudentId.value}`)
  } catch (e) {
    error.value = friendlyError(e)
  } finally {
    busy.value = false
  }
}

async function remove() {
  const ok = await ask({
    title: "删除这条记录？",
    consequences: [t("event.deleteConfirm")],
    confirmLabel: t("action.delete"),
  })
  if (!ok) return
  const sid = resolvedStudentId.value
  const name = primaryStudent.value?.name || ""
  runUndoable({
    title: `已删除「${name}」的记录`,
    run: () => api.delete(`/comments/${props.eventId}`),
    onDone: () => router.replace(sid ? `/students/${sid}` : "/"),
  })
}

function goBack() {
  const sid = resolvedStudentId.value
  router.push(sid ? `/students/${sid}` : "/")
}
</script>

<template>
  <PageHeader
    :title="isEdit ? t('tl.comment') : t('commentNew.title')"
    :subtitle="primaryStudent ? primaryStudent.name : t('commentNew.subtitle')"
  />

  <div class="card" style="max-width: 640px">
    <div class="card__body">
      <form v-if="!loading && resolvedStudentId" @submit.prevent="submit">
        <FormField
          :label="t('commentNew.notesLabel')"
          required
          :error="errors.notes || ''"
          :hint="t('commentNew.notesHint')"
        >
          <textarea
            v-model="form.notes"
            class="input"
            rows="4"
            maxlength="2000"
            :placeholder="t('commentNew.notesPlaceholder')"
            :aria-invalid="!!errors.notes"
          />
        </FormField>

        <div class="form-grid">
          <FormField :label="t('commentNew.dateLabel')" optional>
            <input v-model="form.date" class="input" type="date" />
          </FormField>
        </div>

        <div class="field">
          <div class="field__label">
            {{ t("commentNew.mentionLabel") }}
            <span class="field__opt">{{ t("common.optional") }}</span>
          </div>
          <p class="field__hint mention-picker__intro">{{ t("commentNew.mentionHint") }}</p>
          <div class="mention-picker">
            <button
              type="button"
              class="chip"
              :class="{ 'chip--active': mentionOpen }"
              @click="mentionOpen = !mentionOpen"
            >
              {{ mentionOpen ? t("commentNew.hideMentions") : t("commentNew.showMentions") }}
            </button>

            <template v-if="mentionOpen">
              <input
                v-model="mentionQuery"
                class="input"
                type="search"
                :placeholder="t('eventNew.searchPlaceholder')"
              />
              <div class="mention-picker__list card card--nested">
                <div class="card__body card__body--tight">
                  <label
                    v-for="s in mentionCandidates"
                    :key="s.id"
                    class="mention-picker__row"
                  >
                    <input
                      type="checkbox"
                      :checked="mentioned.has(s.id)"
                      @change="toggleMention(s.id)"
                    />
                    <span class="mention-picker__name">
                      {{ s.name }}
                      <span class="muted tnum">{{ s.admission_no }}</span>
                      <span v-if="s.class" class="muted">{{ s.class.name }}</span>
                    </span>
                  </label>
                  <p v-if="!mentionCandidates.length" class="mention-picker__empty">
                    {{ t("eventNew.noStudentMatch") }}
                  </p>
                </div>
              </div>
            </template>

            <p class="mention-picker__meta">
              {{ t("commentNew.mentionCount", { n: mentioned.size }) }}
            </p>
          </div>
        </div>

        <p v-if="error" class="field__error" style="margin-bottom: 12px">
          <Icon name="alert-circle" :size="13" /> {{ error }}
        </p>

        <div class="form-actions">
          <button type="submit" class="btn btn--primary" :disabled="busy">
            <span v-if="busy" class="spinner" />
            {{ busy ? t("commentNew.saving") : isEdit ? t("action.save") : t("commentNew.submit") }}
          </button>
          <button type="button" class="btn btn--ghost" @click="goBack">{{ t("action.cancel") }}</button>
          <span v-if="isEdit" class="form-actions__spacer" />
          <button v-if="isEdit" type="button" class="btn btn--danger" :disabled="busy" @click="remove">
            <Icon name="trash" :size="14" /> {{ t("action.delete") }}
          </button>
        </div>
      </form>
      <p v-else-if="!loading && error" class="field__error">
        <Icon name="alert-circle" :size="13" /> {{ error }}
      </p>
    </div>
  </div>
</template>
