// 导航配置 —— 侧栏与命令面板共用同一份来源，避免各处口径不一
export const TEACHER_NAV = [
  { key: "home", label: "首页", to: "/", icon: "home", hint: "日历 · 最新动态", g: "h" },
  { key: "students", label: "学生", to: "/students", icon: "users", hint: "档案 · 成绩 · 时间线", g: "s" },
  { key: "classes", label: "班级", to: "/classes", icon: "building", hint: "名单 · 班均", g: "c" },
  { key: "exams", label: "考试", to: "/exams", icon: "clipboard", hint: "科目 · 平均分", g: "e" },
  { key: "visits", label: "家访", to: "/visits", icon: "map-pin", hint: "家访记录", g: "v" },
  { key: "events", label: "事件", to: "/events", icon: "checklist", hint: "比赛 · 活动", g: "r" },
  { key: "data", label: "数据", to: "/data", icon: "database", hint: "花名册导入导出", g: "d" },
]

export const ADMIN_NAV = [
  { key: "admin", label: "开发者后台", to: "/admin", icon: "sliders", hint: "概览 · 账号 · 会话" },
]

export function isNavActive(item, path) {
  if (item.to === "/") return path === "/"
  return path === item.to || path.startsWith(`${item.to}/`)
}
