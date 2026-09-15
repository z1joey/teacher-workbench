import { ref } from "vue"
import api from "./api"

export const unresolvedFeedbackCount = ref(0)

export async function refreshUnresolvedFeedbackCount() {
  try {
    const res = await api.get("/admin/feedback/unresolved-count")
    unresolvedFeedbackCount.value = res.count ?? 0
  } catch {
    unresolvedFeedbackCount.value = 0
  }
}
