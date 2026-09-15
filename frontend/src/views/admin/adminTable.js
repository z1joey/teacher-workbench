import { ref } from "vue"

export const ADMIN_PREVIEW_MAX = 32

export function cellFullText(cell) {
  if (cell === null || cell === undefined) return ""
  if (typeof cell === "object") return JSON.stringify(cell, null, 2)
  return String(cell)
}

export function cellPreview(cell, maxLen = ADMIN_PREVIEW_MAX) {
  if (cell === null || cell === undefined) {
    return { preview: null, expandable: false, full: "" }
  }
  const display = typeof cell === "object" ? JSON.stringify(cell) : String(cell)
  if (!display) {
    return { preview: "—", expandable: false, full: "" }
  }
  const full = cellFullText(cell)
  if (display.length <= maxLen) {
    return { preview: display, expandable: false, full }
  }
  return {
    preview: `${display.slice(0, maxLen)}…`,
    expandable: true,
    full,
  }
}

export function useAdminCellDetail() {
  const cellDetail = ref(null)

  function openCellDetail(detail) {
    cellDetail.value = detail
  }

  function closeCellDetail() {
    cellDetail.value = null
  }

  return { cellDetail, openCellDetail, closeCellDetail }
}
