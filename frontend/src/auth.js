import { ref } from "vue"
import api, { getToken } from "./api"

// Shared current-teacher state: the nav bar and the profile page stay in sync.
export const me = ref(null)

export async function loadMe() {
  if (!getToken()) return
  try {
    me.value = await api.get("/auth/me")
  } catch {
    me.value = null
  }
}

export function clearMe() {
  me.value = null
}
