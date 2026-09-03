import { ref } from "vue"
import api, { getToken } from "./api"

// Shared global student-search state: the nav search box and the students
// page filter read the same query; the nav dropdown reuses a cached directory.
export const searchQuery = ref("")
export const searchStudents = ref([])

export async function ensureSearchStudents() {
  if (!getToken() || searchStudents.value.length) return
  try {
    searchStudents.value = await api.get("/students")
  } catch {
    searchStudents.value = []
  }
}

export function clearSearch() {
  searchQuery.value = ""
  searchStudents.value = []
}
