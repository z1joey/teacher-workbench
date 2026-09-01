// 中文界面词典与领域文案助手：t() 查词典，subject/exatypeLabel/statusLabel 等
// 把后端存储的枚举代码（math、choice、open…）渲染成中文，subjectColor 与
// EVENT_TYPES 供图表和时间线取色/取图标。
const messages = {
  "app.title": "教师工作台",
  "nav.home": "首页",
  "nav.students": "学生",
  "nav.classes": "班级",
  "nav.exams": "考试",
  "auth.logout": "退出登录",

  "classes.title": "班级管理",
  "classes.subtitle": "全校班级与学生名单",
  "classes.homeroom": "班主任",
  "classes.noStudents": "暂无学生",
  "classes.create": "新建班级",
  "classes.creating": "创建中…",
  "classes.name": "班级名称",
  "classes.grade": "年级",
  "classes.year": "学年",
  "classes.viewDetail": "查看详情",
  "classes.delete": "删除班级",
  "classes.deleteConfirm": "确认删除该班级？此操作不可恢复。",
  "classes.nameRequired": "请填写班级名称",
  "classdetail.back": "返回班级列表",
  "classdetail.trendTitle": "班级平均分趋势",
  "classdetail.trendSub": "各科平均分随考试变化 · 悬停查看详情",
  "classdetail.averages": "平均成绩",
  "classdetail.roster": "学生名单",
  "classdetail.noScores": "暂无成绩数据",

  "login.tabLogin": "登录",
  "login.tabRegister": "注册",
  "login.name": "姓名",
  "login.phone": "手机号",
  "login.email": "邮箱（可选）",
  "login.password": "密码",
  "login.submit": "登录",
  "login.submitRegister": "注册并登录",
  "login.demoHint": "演示账号",
  "login.subtitle": "学校教学管理，从这里开始",

  "home.greeting": "你好，{name}",
  "home.today": "今天是 {date}",
  "home.statStudents": "在读学生",
  "home.statClasses": "班级",
  "home.statExams": "考试",
  "home.statVisits": "家访",
  "home.quickActions": "快捷操作",
  "home.addStudent": "添加学生",
  "home.viewExams": "查看考试",
  "home.viewStudents": "学生列表",
  "home.recentEvents": "最新动态",
  "home.followUps": "待跟进家访",
  "home.noFollowUps": "暂无待跟进家访",
  "home.followUpPrefix": "跟进",

  "new.title": "添加学生",
  "new.subtitle": "新学生将加入所选班级，并自动记录入学时间线",
  "new.sectionBasic": "基本信息",
  "new.sectionGuardian": "监护人信息",
  "new.sectionClass": "分配班级",
  "new.name": "学生姓名",
  "new.gender": "性别",
  "new.birthDate": "出生日期",
  "new.guardianName": "监护人姓名",
  "new.guardianPhone": "监护人电话",
  "new.address": "家庭住址",
  "new.class": "分配班级",
  "new.classPlaceholder": "请选择班级",
  "new.classRequired": "请选择班级",
  "new.submit": "保存并打开档案",
  "new.saving": "保存中…",

  "students.add": "添加学生",
  "gender.f": "女",
  "gender.m": "男",

  "profile.title": "个人中心",
  "profile.subtitle": "个人信息、班级与教学足迹",
  "profile.loginPhone": "登录手机号",
  "profile.email": "邮箱",
  "profile.subject": "任教学科",
  "profile.myClasses": "我的班级",
  "profile.noClasses": "暂未担任班主任",
  "profile.activity": "教学足迹",
  "profile.visitsRecorded": "记录家访",
  "profile.resultsEntered": "录入成绩",
  "profile.notesAdded": "添加备注",
  "profile.editInfo": "编辑资料",
  "profile.saved": "已保存",
  "profile.studentsCount": "{n} 人",

  "examnew.title": "新建考试",
  "examnew.subtitle": "创建后可在考试详情查看各班平均分",
  "examnew.name": "考试名称",
  "examnew.date": "考试日期",
  "examnew.term": "学期",
  "examnew.type": "考试类型",
  "examnew.year": "学年",
  "examnew.subjects": "考试科目",
  "examnew.fullScore": "满分",
  "examnew.submit": "创建考试",
  "examnew.saving": "创建中…",
  "examnew.subjectsRequired": "请至少选择一个科目",
  "examnew.dateInvalid": "考试日期无效（年份需在 2000–2100 之间）",

  "exatype.monthly": "月考",
  "exatype.midterm": "期中考试",
  "exatype.final": "期末考试",
  "exatype.quiz": "随堂测",
  "term.T1": "第一学期",
  "term.T2": "第二学期",

  "home.countdown": "考试倒计时",
  "home.noCountdown": "暂无即将到来的考试",
  "home.examToday": "今天",
  "home.examTomorrow": "明天",
  "home.inDays": "{n} 天后",

  "exams.create": "新建考试",

  "students.title": "学生",
  "students.subtitle": "共 {count} 名学生 · 点击行打开学生工作台",
  "students.search": "搜索姓名、学号或班级…",

  "th.admissionNo": "学号",
  "th.name": "姓名",
  "th.gender": "性别",
  "th.class": "班级",
  "th.status": "状态",
  "th.exam": "考试",
  "th.subject": "科目",
  "th.score": "分数",
  "th.qno": "题号",
  "th.topic": "知识点",
  "th.qtype": "题型",
  "th.earned": "得分",

  "common.loading": "加载中…",
  "common.noMatch": "没有符合条件的学生",
  "common.none": "—",

  "detail.back": "返回学生列表",
  "detail.born": "出生日期",
  "detail.guardian": "监护人",
  "detail.scores": "考试成绩",
  "detail.weaknesses": "知识点薄弱项",
  "detail.weaknessFailed": "答错 {failed}/{total} 题",
  "detail.drilldown": "错题明细",
  "detail.visits": "家访记录",
  "detail.timeline": "时间线",
  "detail.trendTitle": "成绩变化趋势",
  "detail.trendSub": "各科成绩随考试变化 · 悬停查看详情",
  "detail.editReason": "工作台内更正",

  "action.edit": "编辑",
  "action.save": "保存",
  "action.cancel": "取消",

  "visit.record": "+ 记录家访",
  "visit.close": "收起",
  "visit.teacher": "家访教师",
  "visit.purpose": "家访目的",
  "visit.summary": "家访摘要",
  "visit.summaryRequired": "请填写家访摘要",
  "visit.followUp": "需要跟进",
  "visit.followUpNote": "跟进备注",
  "visit.save": "保存家访",
  "visit.saving": "保存中…",

  "empty.scores": "暂无成绩",
  "empty.weaknesses": "暂无薄弱项记录，继续保持！",
  "empty.drilldown": "暂无错题记录",
  "empty.visits": "暂无家访记录",

  "exams.title": "考试列表",
  "exams.viewAverages": "查看平均分",
  "exams.fullScore": "满分",

  "exam.averages": "平均分",
  "exam.perClass": "各班平均分",
  "exam.trendTitle": "全校平均分趋势",
  "exam.trendSub": "虚线为当前考试 · 悬停查看各科平均分",
  "exam.avg": "平均分",
  "exam.outOf": "满分",
  "exam.min": "最低",
  "exam.max": "最高",
  "exam.students": "{count} 名学生",
  "exam.exams": "{count} 次考试",
  "exam.attributionNote": "各班人数按学生考试当日所在班级统计",

  "status.active": "在读",
  "status.entered": "已录入",
  "status.open": "待提升",
  "status.resolved": "已改善",

  "tl.enrolled": "入学",
  "tl.class_moved": "转班",
  "tl.exam_taken": "参加考试",
  "tl.result_changed": "成绩更正",
  "tl.weakness_flagged": "薄弱项标记",
  "tl.home_visited": "家访",
  "tl.note_added": "教师备注",
  "tl.joined": "加入 {class}",
}

export function t(key, params) {
  let s = messages[key] ?? key
  if (params) {
    for (const [k, v] of Object.entries(params)) s = s.replaceAll(`{${k}}`, String(v))
  }
  return s
}

export function dateLocale() {
  return "zh-CN"
}

const SUBJECTS = {
  math: "数学",
  english: "英语",
  chinese: "语文",
  physics: "物理",
  chemistry: "化学",
}
export function subject(s) {
  return SUBJECTS[s] ?? (s ?? "")
}

const SUBJECT_COLORS = {
  math: "#2e6ba8",
  english: "#2f7d4f",
  chinese: "#b98a2e",
  physics: "#6d5bb8",
  chemistry: "#b42318",
}
export function subjectColor(s) {
  return SUBJECT_COLORS[s] || "#64748b"
}

const EXAM_TYPES = ["monthly", "midterm", "final", "quiz"]
export function exatypeLabel(ty) {
  return EXAM_TYPES.includes(ty) ? t(`exatype.${ty}`) : (ty ?? "")
}

export function termLabel(v) {
  if (v === "T1" || v === "T2") return t(`term.${v}`)
  return v ?? ""
}

const QUESTION_TYPES = {
  choice: "选择题",
  "fill-in": "填空题",
  calculation: "计算题",
  word_problem: "应用题",
  geometry: "几何题",
}
export function qtype(ty) {
  return QUESTION_TYPES[ty] ?? (ty ?? "")
}

const STATUS_KEYS = new Set(["active", "entered", "open", "resolved"])
export function statusLabel(s) {
  return STATUS_KEYS.has(s) ? t(`status.${s}`) : (s ?? "")
}

const GENDERS = { F: "女", M: "男" }
export function genderLabel(g) {
  return (g && GENDERS[g]) || g || "—"
}

// --- 时间线事件元数据（Timeline 与首页共用）；icon 对应 components/Icon.vue ---
const EVENT_TYPES = {
  enrolled: { icon: "enroll", color: "#6B7A72" },
  class_moved: { icon: "swap", color: "#6D5BB8" },
  exam_taken: { icon: "clipboard", color: "#2E6BA8" },
  result_changed: { icon: "pencil", color: "#B45309" },
  weakness_flagged: { icon: "alert", color: "#B42318" },
  home_visited: { icon: "home", color: "#2F7D4F" },
  note_added: { icon: "note", color: "#5C6B63" },
}

export function eventTypeIcon(type) {
  return (EVENT_TYPES[type] || { icon: "note" }).icon
}

export function eventTypeColor(type) {
  return (EVENT_TYPES[type] || { color: "#94a3b8" }).color
}

export function eventTypeLabel(type) {
  return t(`tl.${type}`)
}

export function describeEvent(type, p = {}) {
  switch (type) {
    case "enrolled":
      return t("tl.joined", { class: p.class ?? "" })
    case "class_moved":
      return `${p.from ?? ""} → ${p.to ?? ""}${p.reason ? " · " + p.reason : ""}`
    case "exam_taken": {
      const scores = p.scores
        ? Object.entries(p.scores).map(([s, v]) => `${subject(s)} ${v}`).join(", ")
        : ""
      return `${p.exam ?? ""}${scores ? " — " + scores : ""}`
    }
    case "result_changed":
      return `${p.exam ?? ""} · ${subject(p.subject)}: ${p.old} → ${p.new}${p.reason ? " · " + p.reason : ""}`
    case "weakness_flagged":
      return (p.points || []).join(", ")
    case "home_visited":
      return `${p.purpose ? p.purpose + " — " : ""}${p.summary || ""}`
    case "note_added":
      return p.note ?? ""
    default:
      return JSON.stringify(p)
  }
}
