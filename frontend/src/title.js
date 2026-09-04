// 面包屑的实时标题：详情页把真实名字（而不是「学生档案」）写进来，
// 用户随时知道自己在看谁，不必回退确认（识别优于回忆）。
import { ref } from "vue"

export const pageTitle = ref("")

export function setPageTitle(value) {
  pageTitle.value = value || ""
}
