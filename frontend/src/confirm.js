// 确认对话框 —— 对应尼尔森原则：
//   #2 语言真实：说出「删掉什么」「连带什么」，而不是「确定吗？」
//   #5 防错：破坏性操作必须显式确认；极端操作要求输入名称才能执行
import { ref } from "vue"

export const confirmDialog = ref(null)
let resolver = null

/**
 * 打开一个确认对话框。
 * @returns {Promise<boolean>} 用户是否确认
 */
export function ask({
  title,
  message = "",
  confirmLabel = "确认",
  cancelLabel = "取消",
  tone = "danger", // danger | warn
  consequences = [], // 会连带发生什么
  confirmWord = null, // 需要用户输入该文本才能确认（极端危险操作）
}) {
  closeConfirm(false)
  return new Promise((resolve) => {
    resolver = resolve
    confirmDialog.value = {
      title,
      message,
      confirmLabel,
      cancelLabel,
      tone,
      consequences,
      confirmWord,
      input: "",
    }
  })
}

export function closeConfirm(value) {
  const done = resolver
  resolver = null
  confirmDialog.value = null
  if (done) done(value)
}

export function confirmEnabled(d) {
  return !d?.confirmWord || d.input.trim() === d.confirmWord
}
