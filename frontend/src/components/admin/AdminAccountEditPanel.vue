<script setup>
import { t } from "../../strings"

defineProps({
  user: { type: Object, required: true },
  form: { type: Object, required: true },
  password: { type: String, default: "" },
  saving: { type: Boolean, default: false },
  selfId: { type: String, default: "" },
})

const emit = defineEmits(["save", "cancel", "update:password"])
</script>

<template>
  <div class="admin-accounts-edit">
    <div class="admin-accounts-edit__who">
      <strong>{{ user.name }}</strong>
      <span class="muted tnum">{{ user.id }}</span>
    </div>
    <div class="form-grid">
      <div class="field" style="margin: 0">
        <span class="field__label">{{ t("admin.userRole") }}</span>
        <select v-model="form.role" class="select" :disabled="user.id === selfId">
          <option value="teacher">{{ t("admin.roleTeacher") }}</option>
          <option value="admin">{{ t("admin.roleAdmin") }}</option>
        </select>
        <span v-if="user.id === selfId" class="field__hint">不能修改自己的角色</span>
      </div>
      <div class="field" style="margin: 0">
        <span class="field__label">{{ t("admin.teacherResetPwd") }}</span>
        <input
          :value="password"
          class="input input--sm"
          type="password"
          :placeholder="t('admin.newPassword')"
          autocomplete="new-password"
          @input="emit('update:password', $event.target.value)"
        />
      </div>
    </div>
    <div class="row" style="margin-top: 12px">
      <button class="btn btn--sm btn--primary" :disabled="saving" @click="emit('save')">
        {{ t("admin.teacherSave") }}
      </button>
      <button class="btn btn--sm btn--ghost" @click="emit('cancel')">{{ t("action.cancel") }}</button>
    </div>
  </div>
</template>
