// 导航配置 —— 侧栏与命令面板共用同一份来源，避免各处口径不一
export const TEACHER_NAV = [
  { key: "home", label: "首页", to: "/", icon: "home", hint: "日历 · 最新动态", g: "h" },
  { key: "students", label: "学生", to: "/students", icon: "users", hint: "档案 · 成绩 · 时间线", g: "s" },
  { key: "classes", label: "班级", to: "/classes", icon: "building", hint: "名单 · 班均", g: "c" },
  { key: "exams", label: "考试", to: "/exams", icon: "clipboard", hint: "科目 · 平均分", g: "e" },
  { key: "visits", label: "家访", to: "/visits", icon: "map-pin", hint: "家访记录", g: "v" },
]

export const ADMIN_NAV = [
  { key: "admin", label: "概览", to: "/admin", icon: "chart", hint: "统计 · 数据表" },
  { key: "adminAccounts", label: "账号管理", to: "/admin/accounts", icon: "users", hint: "教师 · 管理员" },
  { key: "adminFeedback", label: "用户反馈", to: "/admin/feedback", icon: "flag", hint: "意见 · 建议" },
  { key: "adminSessions", label: "活动会话", to: "/admin/sessions", icon: "clock", hint: "登录 · 终止" },
  { key: "adminInspect", label: "数据探查", to: "/admin/inspect", icon: "search", hint: "原始表预览" },
  { key: "adminDanger", label: "危险操作", to: "/admin/danger", icon: "alert", hint: "重置数据库" },
]

export function isNavActive(item, path) {
  if (item.to === "/") return path === "/"
  if (item.to === "/admin") return path === "/admin"
  return path === item.to || path.startsWith(`${item.to}/`)
}
