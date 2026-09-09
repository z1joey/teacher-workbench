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
  if (res.status === 401 && (path === "/auth/me" || !path.startsWith("/auth/"))) {
    setToken(null)
    if (path !== "/auth/me") {
      const loginPath = `${import.meta.env.BASE_URL}login`
      if (!window.location.pathname.startsWith(loginPath)) {
        window.location.href = loginPath
      }
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
  if (res.status === 204 || res.status === 205) return null
  return res.json()
}

async function parseError(res) {
  const body = await res.json().catch(() => ({}))
  let detail = body.detail
  // FastAPI validation errors (422) return an array of {msg, ...}
  if (Array.isArray(detail)) {
    detail = detail.map((d) => (typeof d?.msg === "string" ? d.msg : "")).filter(Boolean).join("; ")
  }
  if (typeof detail !== "string" || !detail) detail = res.statusText
  throw new Error(detail)
}

function authHeaders(extra = {}) {
  const token = getToken()
  return token ? { Authorization: `Bearer ${token}`, ...extra } : { ...extra }
}

// 下载接口返回的文件（带 Authorization 的 fetch，浏览器不能直接用 <a href>）
export async function downloadFile(path) {
  const res = await fetch(BASE + path, { headers: authHeaders() })
  if (res.status === 401 && !path.startsWith("/auth/")) {
    setToken(null)
    window.location.href = `${import.meta.env.BASE_URL}login`
    throw new Error("登录已过期，请重新登录")
  }
  if (!res.ok) await parseError(res)
  const blob = await res.blob()
  // Content-Disposition: attachment; filename*=UTF-8''<encoded> 优先（中文文件名）
  const cd = res.headers.get("Content-Disposition") || ""
  const star = cd.match(/filename\*=UTF-8''([^;]+)/i)
  const plain = cd.match(/filename="?([^";]+)"?/i)
  let filename = "download"
  try {
    if (star) filename = decodeURIComponent(star[1])
    else if (plain) filename = plain[1]
  } catch {
    filename = "download"
  }
  return { blob, filename }
}

export function triggerDownload(blob, filename) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement("a")
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

// multipart 文件上传（不要手动设置 Content-Type，浏览器要带上 boundary）
export async function uploadFile(path, file, fields = {}) {
  const fd = new FormData()
  fd.append("file", file)
  for (const [k, v] of Object.entries(fields)) {
    if (v !== null && v !== undefined && v !== "") fd.append(k, v)
  }
  const res = await fetch(BASE + path, { method: "POST", headers: authHeaders(), body: fd })
  if (res.status === 401 && !path.startsWith("/auth/")) {
    setToken(null)
    window.location.href = `${import.meta.env.BASE_URL}login`
    throw new Error("登录已过期，请重新登录")
  }
  if (!res.ok) await parseError(res)
  return res.json()
}

export default {
  get: (path) => request(path),
  post: (path, body) => request(path, { method: "POST", body: JSON.stringify(body) }),
  put: (path, body) => request(path, { method: "PUT", body: JSON.stringify(body) }),
  patch: (path, body) => request(path, { method: "PATCH", body: JSON.stringify(body) }),
  delete: (path) => request(path, { method: "DELETE" }),
}
