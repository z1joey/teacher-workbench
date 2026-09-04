// 全局反馈中心 —— 对应尼尔森原则：
//   #1 状态可见：每个异步动作都有明确结果
//   #3 可撤销：破坏性操作先给宽限期，再真正执行
//   #9 错误可恢复：失败原样保留现场，并提供「重试」
//
// 破坏性操作采用「延迟执行 + 撤销窗口」（Gmail 式 undo send）：
// 界面立即反映结果，但真正的 API 调用推迟到宽限期结束。用户点「撤销」
// 则什么都没发生；宽限期过后才落库。这样无需后端提供回收站也能真正撤销。
import { ref } from "vue"

export const toasts = ref([])

let seq = 0
const timers = new Map() // id -> timeout handle
let rafId = null

// ---------------------------------------------------------------- 基础提示

export function notify({ tone = "info", title, detail = "", timeout = 4000 }) {
  return push({ tone, title, detail, timeout })
}

function push(toast) {
  const id = ++seq
  const t = {
    id,
    tone: "info",
    title: "",
    detail: "",
    state: "idle", // idle | pending | running
    progress: 0,
    paused: false,
    total: 0,
    deadline: 0,
    remainingMs: 0,
    action: null,
    ...toast,
  }
  toasts.value = [...toasts.value, t]
  if (t.timeout > 0) armTimer(t, t.timeout, () => dismiss(id))
  return id
}

export function dismiss(id) {
  clearTimer(id)
  toasts.value = toasts.value.filter((t) => t.id !== id)
  stopTicker()
}

export function clearAll() {
  for (const id of [...timers.keys()]) clearTimeout(timers.get(id))
  timers.clear()
  toasts.value = []
  stopTicker()
}

// 鼠标悬停时暂停倒计时：撤销窗口不会因为用户还在读提示而溜走
export function pauseToast(id) {
  const t = find(id)
  if (!t || t.paused || !timers.has(id)) return
  clearTimer(id)
  t.remainingMs = Math.max(0, t.deadline - Date.now())
  t.paused = true
}

export function resumeToast(id) {
  const t = find(id)
  if (!t || !t.paused) return
  t.paused = false
  armTimer(t, t.remainingMs, t.onExpire ?? (() => dismiss(id)))
}

// ------------------------------------------------------------ 可撤销动作

/**
 * 安排一个可撤销的破坏性操作。
 *
 * @param {string} title        进行时的提示标题，如「已移除标签「走读」」
 * @param {string} detail       补充说明
 * @param {number} seconds      撤销窗口（秒）
 * @param {Function} run        真正执行的异步函数（宽限期结束后调用）
 * @param {Function} onDone     执行成功后的副作用（如跳转路由）
 * @param {string} successTitle 成功后的标题，默认沿用 title
 * @param {string} successDetail
 * @param {string} undoneTitle  撤销后的标题
 */
export function runUndoable({
  title,
  detail = "",
  seconds = 6,
  run,
  onDone,
  onUndo,
  successTitle,
  successDetail = "",
  undoneTitle = "已撤销，没有做任何改动",
}) {
  const total = seconds * 1000
  const id = ++seq
  const toast = {
    id,
    tone: "pending",
    title,
    detail: detail || `${seconds} 秒内可以撤销`,
    state: "pending",
    progress: 1,
    paused: false,
    total,
    deadline: Date.now() + total,
    remainingMs: total,
    timeout: 0,
  }

  const settle = (patch) => {
    const t = find(id)
    if (!t) return
    Object.assign(t, patch)
  }

  toast.action = {
    label: "撤销",
    run: () => {
      clearTimer(id)
      dismiss(id)
      // 把界面恢复到操作前的样子 —— 撤销必须是真的回到原样
      if (onUndo) onUndo()
      notify({ tone: "ok", title: undoneTitle, timeout: 2600 })
    },
  }

  toast.onExpire = async () => {
    settle({ state: "running", detail: "正在保存…", action: null, progress: 0 })
    try {
      const result = await run()
      settle({
        state: "idle",
        tone: "ok",
        title: successTitle || title,
        detail: successDetail,
      })
      armTimer(find(id), 2600, () => dismiss(id))
      if (onDone) onDone(result)
    } catch (e) {
      // 失败不销毁现场：保留提示，并把「重试」交给用户
      settle({
        state: "idle",
        tone: "error",
        title: "操作失败",
        detail: e?.message || "请稍后再试",
        action: {
          label: "重试",
          run: () => {
            settle({ state: "running", detail: "正在保存…", action: null })
            retry()
          },
        },
      })
      armTimer(find(id), 10000, () => dismiss(id))
    }
  }

  async function retry() {
    try {
      const result = await run()
      settle({ state: "idle", tone: "ok", title: successTitle || title, detail: successDetail })
      armTimer(find(id), 2600, () => dismiss(id))
      if (onDone) onDone(result)
    } catch (e) {
      settle({
        state: "idle",
        tone: "error",
        title: "操作失败",
        detail: e?.message || "请稍后再试",
        action: { label: "重试", run: () => { settle({ state: "running", action: null }); retry() } },
      })
      armTimer(find(id), 10000, () => dismiss(id))
    }
  }

  toasts.value = [...toasts.value, toast]
  armTimer(toast, total, toast.onExpire)
  startTicker()
  return id
}

// ------------------------------------------------------------------ 内部

function find(id) {
  return toasts.value.find((t) => t.id === id)
}

function armTimer(t, ms, onExpire) {
  if (!t) return
  clearTimer(t.id)
  t.onExpire = onExpire
  t.deadline = Date.now() + ms
  t.remainingMs = ms
  timers.set(t.id, setTimeout(onExpire, ms))
}

function clearTimer(id) {
  if (timers.has(id)) {
    clearTimeout(timers.get(id))
    timers.delete(id)
  }
}

function startTicker() {
  if (rafId != null || typeof requestAnimationFrame !== "function") return
  const loop = () => {
    let active = false
    for (const t of toasts.value) {
      if (t.state === "pending" && !t.paused) {
        t.progress = Math.max(0, Math.min(1, (t.deadline - Date.now()) / t.total))
        if (t.progress > 0) active = true
      }
    }
    rafId = active ? requestAnimationFrame(loop) : null
  }
  rafId = requestAnimationFrame(loop)
}

function stopTicker() {
  if (rafId != null) {
    cancelAnimationFrame(rafId)
    rafId = null
  }
}
