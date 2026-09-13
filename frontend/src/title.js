// 面包屑的实时标题：详情页把真实名字（而不是「学生档案」）写进来，
// 用户随时知道自己在看谁，不必回退确认（识别优于回忆）。
import { ref } from "vue"

export const pageTitle = ref("")

// 中间层级面包屑：挂在「学生」和当前页之间的可点击层级，
// 例如学生总结页插入「陈佳怡 → /students/:id」，随时能回到学生档案。
export const pageCrumbs = ref([])

export function setPageTitle(value) {
  pageTitle.value = value || ""
}

export function setPageCrumbs(list) {
  pageCrumbs.value = Array.isArray(list) ? list.filter((c) => c && c.label) : []
}
