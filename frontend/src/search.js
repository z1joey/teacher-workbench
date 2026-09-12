import { ref } from "vue"
import api, { getToken } from "./api"
import { t } from "./strings"

// Shared global student-search state: the nav search box and the students
// page filter read the same query; the nav dropdown reuses a cached directory.
export const searchQuery = ref("")
export const searchStudents = ref([])

export async function ensureSearchStudents(force = false) {
  // 搜索目录用超集（含已毕业，带 status 标记），列表页默认数据不含已毕业
  if (!getToken() || (searchStudents.value.length && !force)) return
  try {
    searchStudents.value = await api.get("/students?include_graduated=1")
  } catch {
    searchStudents.value = []
  }
}

export function clearSearch() {
  searchQuery.value = ""
  searchStudents.value = []
}

// 命中该学生监护人（姓名或电话）的记录，供匹配判定与下拉标注「监护人：…」。
export function matchedGuardiansOf(s, q) {
  return (s.guardians ?? []).filter(
    (g) => g.name.toLowerCase().includes(q) || (g.phone && String(g.phone).includes(q))
  )
}

// 顶栏下拉与学生列表页共用的命中判定：姓名/学号/班级/未分班，外加监护人。
// 已毕业学生无在读班级，不算未分班。
export function studentMatchesQuery(s, q) {
  const ungrouped = t("students.ungrouped").toLowerCase()
  return (
    s.name.toLowerCase().includes(q) ||
    s.admission_no.toLowerCase().includes(q) ||
    (s.class && s.class.name.toLowerCase().includes(q)) ||
    (!s.class && s.status !== "graduated" && ungrouped.includes(q)) ||
    matchedGuardiansOf(s, q).length > 0
  )
}
