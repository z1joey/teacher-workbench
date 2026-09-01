const BASE = "/api"
const TOKEN_KEY = "tw-token"

export function getToken() {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token) {
  if (token) localStorage.setItem(TOKEN_KEY, token)
  else localStorage.removeItem(TOKEN_KEY)
}

async function request(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) }
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`

  const res = await fetch(BASE + path, { ...options, headers })

  // Expired/invalid session: drop the token and send the user to login.
  // Login/register 401s (wrong credentials) are shown inline instead.
  if (res.status === 401 && !path.startsWith("/auth/")) {
    setToken(null)
    if (!window.location.pathname.startsWith("/login")) {
      window.location.href = "/login"
    }
    throw new Error("登录已过期，请重新登录")
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    let detail = body.detail
    // FastAPI validation errors (422) return an array of {msg, ...}
    if (Array.isArray(detail)) {
      detail = detail.map((d) => (typeof d?.msg === "string" ? d.msg : "")).filter(Boolean).join("; ")
    }
    if (typeof detail !== "string" || !detail) detail = res.statusText
    throw new Error(detail)
  }
  return res.json()
}

export default {
  get: (path) => request(path),
  post: (path, body) => request(path, { method: "POST", body: JSON.stringify(body) }),
  patch: (path, body) => request(path, { method: "PATCH", body: JSON.stringify(body) }),
  delete: (path) => request(path, { method: "DELETE" }),
}
