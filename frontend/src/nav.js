// 导航配置 —— 侧栏、底部标签栏、命令面板共用同一份来源，避免各处口径不一
export const TEACHER_NAV = [
  { key: "home", label: "首页", to: "/", icon: "home", hint: "日历 · 待跟进 · 倒计时", g: "h" },
  { key: "students", label: "学生", to: "/students", icon: "users", hint: "档案 · 成绩 · 时间线", g: "s" },
  { key: "classes", label: "班级", to: "/classes", icon: "building", hint: "名单 · 班均", g: "c" },
  { key: "exams", label: "考试", to: "/exams", icon: "clipboard", hint: "科目 · 平均分", g: "e" },
  { key: "visits", label: "家访", to: "/visits", icon: "map-pin", hint: "记录 · 待跟进", g: "v" },
  { key: "events", label: "事件", to: "/events", icon: "checklist", hint: "比赛 · 活动", g: "r" },
]

export const ADMIN_NAV = [
  { key: "admin", label: "开发者后台", to: "/admin", icon: "sliders", hint: "概览 · 账号 · 会话" },
]

// 底部标签栏只放最高频的 4 个入口，其余在抽屉里
export const TABBAR_KEYS = ["home", "students", "classes", "exams"]

export function isNavActive(item, path) {
  if (item.to === "/") return path === "/"
  return path === item.to || path.startsWith(`${item.to}/`)
}
