<script setup>
// 班级详情路由（/classes/:id 深链接）：直接渲染班级内容，切换班级替换路径。
import { useRouter } from "vue-router"
import ClassDetailContent from "../components/ClassDetailContent.vue"

const props = defineProps({ id: { type: String, required: true } })
const router = useRouter()

function switchClass(id) {
  router.replace(`/classes/${id}`)
}
</script>

<template>
  <ClassDetailContent :class-id="props.id" @switch="switchClass" @create="router.push('/classes?create=1')" />
</template>
