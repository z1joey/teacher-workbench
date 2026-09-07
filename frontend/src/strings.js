// 中文界面词典与领域文案助手：t() 查词典，subject/genderLabel/statusLabel 等
// 把后端存储的枚举代码（math、F、active…）渲染成人话。
// subjectColor 与 EVENT_TYPES 供图表和时间线取色/取图标。
const messages = {
  "app.title": "高老师工作台",
  "nav.home": "首页",
  "nav.students": "学生",
  "nav.classes": "班级",
  "nav.exams": "考试",
  "nav.admin": "管理",
  "nav.profile": "个人中心",
  "nav.help": "帮助与快捷键",
  "nav.menu": "导航菜单",
  "auth.logout": "退出登录",

  // --- 通用动作 ---
  "action.edit": "编辑",
  "action.save": "保存",
  "action.saving": "保存中…",
  "action.cancel": "取消",
  "action.delete": "删除",
  "action.remove": "移除",
  "action.retry": "重试",
  "action.undo": "撤销",
  "action.close": "关闭",
  "action.collapse": "收起",
  "action.back": "返回",
  "action.add": "添加",
  "action.more": "更多操作",

  // --- 通用状态 ---
  "common.loading": "加载中…",
  "common.noMatch": "没有符合条件的学生",
  "common.none": "—",
  "common.required": "必填",
  "common.optional": "选填",
  "common.loadFailed": "没能加载这部分内容",
  "common.undone": "已撤销，没有做任何改动",
  "common.saved": "已保存",

  // --- 管理后台 ---
  "admin.title": "开发者后台",
  "admin.subtitle": "系统概览、数据探查与账号管理",
  "admin.refresh": "刷新",
  "admin.sectionOverview": "数据库概览",
  "admin.sectionAccounts": "账号管理",
  "admin.sectionSessions": "活动会话",
  "admin.sectionInspect": "数据探查",
  "admin.sectionDanger": "危险操作",
  "admin.dbDriver": "数据库驱动",
  "admin.dbTables": "数据表行数",
  "admin.usersTotal": "账号总数",
  "admin.usersAdmins": "管理员",
  "admin.usersActive": "活跃账号",
  "admin.sessionsActive": "活动会话",
  "admin.table": "表名",
  "admin.rows": "行数",
  "admin.teacherId": "ID",
  "admin.teacherName": "姓名",
  "admin.teacherPhone": "手机号",
  "admin.teacherStatus": "状态",
  "admin.userRole": "角色",
  "admin.roleTeacher": "教师",
  "admin.roleAdmin": "管理员",
  "admin.teacherActions": "操作",
  "admin.teacherSave": "保存",
  "admin.teacherResetPwd": "重置密码",
  "admin.teacherDelete": "删除",
  "admin.userConfirmDelete": "删除账号后，该用户会立即失去访问权限。",
  "admin.userSelfDemote": "不能把自己的角色从管理员降为教师",
  "admin.userFilterAll": "全部",
  "admin.newPassword": "新密码（至少 6 位）",
  "admin.password": "密码",
  "admin.sessionToken": "Token",
  "admin.sessionTeacher": "用户",
  "admin.sessionCreated": "创建时间",
  "admin.sessionKill": "终止",
  "admin.sessionKillAll": "清空所有会话",
  "admin.inspectTable": "选择数据表",
  "admin.inspectLimit": "行数",
  "admin.inspectRun": "预览",
  "admin.inspectNoData": "暂无数据",
  "admin.resetDb": "重置数据库",
  "admin.resetDbWarn": "这会清空所有表里的全部数据，并重建空表。",
  "admin.resetDbDone": "数据库已重置。",
  "admin.loading": "加载中…",
  "admin.saved": "已保存",
  "admin.error": "操作失败",

  // --- 班级 ---
  "classes.title": "班级",
  "classes.subtitle": "班均与最近动态，点进班级查看完整名单",
  "classes.homeroom": "班主任",
  "classes.noStudents": "这个班级还没有学生",
  "classes.avgLabel": "最近一次班均",
  "classes.visitedYes": "已家访",
  "classes.visitedNo": "未家访",
  "classes.visitedSummary": "{n}/{total} 已家访",
  "classes.recentEvents": "最近事件",
  "classes.birthday": "生日",
  "classes.showAllStudents": "显示全部学生",
  "classes.showAllEvents": "显示全部事件",
  "classes.create": "新建班级",
  "classes.creating": "创建中…",
  "classes.name": "班级名称",
  "classes.grade": "年级",
  "classes.year": "学年",
  "classes.viewDetail": "查看详情",
  "classes.delete": "删除班级",
  "classes.deleteConfirm": "删除后，这个班级会从所有列表里消失。",
  "classes.nameRequired": "请填写班级名称",
  "classes.emptyTitle": "还没有班级",
  "classes.emptyDesc": "先建一个班级，再把学生分配进去。",
  "classes.unassignedHint": "尚未分配班级，可在学生档案里指定班级",
  "classes.viewUnassigned": "在学生列表查看",
  "classdetail.back": "返回班级列表",
  "classdetail.trendTitle": "班级平均得分率趋势",
  "classdetail.trendSub": "各科平均得分率（%）随考试变化，满分不同也可比较 · 悬停查看原始分 · 点击科目名显示/隐藏",
  "classdetail.averages": "各科平均成绩",
  "classdetail.roster": "学生名单",
  "classdetail.addStudent": "添加学生",
  "classdetail.addStudentTitle": "从待分配学生中选择",
  "classdetail.addStudentHint": "只能添加尚未分班的学生",
  "classdetail.addStudentEmpty": "没有待分配的学生",
  "classdetail.studentAdded": "已将 {name} 加入班级",
  "classdetail.noScores": "这个班级还没有成绩数据",

  // --- 登录 ---
  "login.name": "姓名",
  "login.phone": "手机号",
  "login.password": "密码",
  "login.submit": "登录",
  "login.submitting": "正在登录…",
  "login.subtitle": "学校教学管理，从这里开始",
  "login.needHelp": "忘记密码请联系管理员重置。",
  "login.noAccount": "还没有账号？",
  "login.goSignup": "注册",
  "login.emptyDb": "当前还没有任何教师账号。你可以注册新账号，或一键初始化演示环境。",
  "login.bootstrap": "初始化演示环境",

  // --- 注册 ---
  "signup.subtitle": "创建教师账号",
  "signup.nameRequired": "请填写姓名",
  "signup.password2": "确认密码",
  "signup.passwordMismatch": "两次输入的密码不一致",
  "signup.submit": "注册",
  "signup.submitting": "正在注册…",
  "signup.success": "注册成功，欢迎加入",
  "signup.hasAccount": "已有账号？",
  "signup.goLogin": "去登录",

  // --- 首页 ---
  "home.greeting": "你好，{name}",
  "home.today": "今天是 {date}",
  "home.recentEvents": "最新动态",
  "home.recentEventsSub": "全校最近发生的记录",
  "home.noRecentEvents": "最近还没有记录",
  "home.calendar": "日历",
  "home.calPrev": "上个月",
  "home.calNext": "下个月",
  "home.calToday": "回到今天",
  "home.calNothing": "这一天没有记录",
  "home.calAdd": "添加记录",
  "home.calStudent": "学生",
  "home.calStudentRequired": "请先选择学生",
  "home.calType": "类型",
  "home.calSummary": "内容",
  "home.calRecurrence": "重复",
  "home.calOnce": "不重复",
  "home.calYearly": "每年重复",
  "home.calSummaryRequired": "请填写内容",
  "home.calPurpose": "事由",
  "home.calReadOnly": "生日是每年自动生成的记录，不能编辑；不想要可以直接删除。",
  "home.calLegendExam": "考试",
  "home.calLegendRecord": "跟进记录",
  "home.calNotifyThisWeek": "本周",
  "home.calNotifyNextWeek": "下周",

  // --- 数据 ---
  "data.demoTitle": "演示数据",
  "data.demoSub": "用于本地试用或发布前验收：演示内容绑定当前教师账号，仅教师可操作。",
  "data.demoBody": "包含两个班级、完整成绩曲线、家访与跟进记录。加载或清空后都会保留你当前登录的教师账号，无需重新登录。",
  "data.demoSeed": "加载演示数据",
  "data.demoSeedWarn": "这会清空现有业务数据，并写入演示用的班级、学生、考试与跟进记录。",
  "data.demoSeedDone": "演示数据已加载",
  "data.demoSeedFail": "加载演示数据失败",
  "data.demoReset": "清空业务数据",
  "data.demoResetWarn": "这会删除全部学生、班级、考试、成绩和跟进记录，回到空白工作台。",
  "data.demoResetConfirm": "清空数据",
  "data.demoResetDone": "业务数据已清空",
  "data.demoResetFail": "清空失败",

  // --- 事件（普通事件） ---
  "events.title": "事件",
  "events.subtitle": "共 {count} 条普通事件 · 比赛、活动等",
  "events.emptyTitle": "还没有普通事件",
  "events.emptyDesc": "用「新建事件」记录比赛、活动等；考试和家访有各自的页面。",
  "events.create": "新建事件",

  // --- 新建普通事件 ---
  "eventNew.title": "新建事件",
  "eventNew.subtitle": "记录比赛、活动等普通事件，参与的学生会同步出现在他们的时间线里。",
  "eventNew.nameLabel": "事件名称",
  "eventNew.namePlaceholder": "如：市级数学竞赛",
  "eventNew.nameHint": "写清楚是什么比赛或活动，方便日后回看",
  "eventNew.titleRequired": "请填写事件名称",
  "eventNew.dateLabel": "日期",
  "eventNew.notesLabel": "说明",
  "eventNew.studentsLabel": "参与学生",
  "eventNew.studentsHint": "点班级名整班参加，或勾选单个学生；选中的学生会作为参与者出现在事件里",
  "eventNew.classChipTitle": "点击整班参加，再次点击取消全班",
  "eventNew.searchPlaceholder": "搜索姓名或学号",
  "eventNew.specifyStudents": "指定学生",
  "eventNew.hideStudentList": "收起学生列表",
  "eventNew.noStudentMatch": "没有匹配的学生",
  "eventNew.selectedCount": "已选 {n} 名学生",
  "eventNew.saving": "创建中…",
  "eventNew.submit": "创建事件",

  // --- 监护人 ---
  "guardian.subtitle": "联系方式与名下的被监护人",
  "guardian.phone": "电话",
  "guardian.address": "地址",
  "guardian.wardCount": "被监护学生",
  "guardian.wards": "被监护学生",
  "guardian.wardsSub": "同一监护人可能关联多名学生，点击姓名查看学生档案。",

  // --- 家访 ---
  "visits.title": "家访",
  "visits.subtitle": "共 {count} 次 · 覆盖 {students} 名学生",
  "visits.emptyTitle": "还没有家访记录",
  "visits.emptyDesc": "在学生档案里点「记录家访」即可添加。",
  "visits.done": "已完成",
  "visits.markDone": "标记完成",
  "visits.record": "记录家访",

  // --- 新建学生 ---
  "new.title": "添加学生",
  "new.subtitle": "可先录入学生，班级可以稍后再分配",
  "new.sectionBasic": "基本信息",
  "new.sectionGuardian": "监护人信息",
  "new.sectionClass": "分配班级",
  "new.name": "学生姓名",
  "new.nameRequired": "请填写学生姓名",
  "new.gender": "性别",
  "new.birthDate": "出生日期",
  "new.guardianName": "监护人姓名",
  "new.guardianPhone": "监护人电话",
  "new.address": "家庭住址",
  "new.class": "分配班级",
  "new.classPlaceholder": "暂不分配",
  "new.classHint": "可选；未分配的学生会出现在学生列表的「未分班」分组",
  "new.noClassYet": "还没有班级可选，请先去「班级」里新建一个。",
  "new.submit": "保存并打开档案",
  "new.saving": "保存中…",
  "students.add": "添加学生",
  "students.addComment": "写评语",

  // --- 个人中心 ---
  "profile.title": "个人中心",
  "profile.subtitle": "个人信息、班级与教学足迹",
  "profile.loginPhone": "登录手机号",
  "profile.email": "邮箱",
  "profile.myClasses": "我的班级",
  "profile.noClasses": "暂时没有班级",
  "profile.activity": "教学足迹",
  "profile.recordsLogged": "跟进记录",
  "profile.resultsEntered": "录入成绩",
  "profile.notesAdded": "添加备注",
  "profile.editInfo": "编辑资料",
  "profile.saved": "已保存",
  "profile.studentsCount": "{n} 人",
  "profile.settings": "偏好设置",
  "profile.autoTags": "家访完成后自动添加「已家访」标签",
  "profile.autoTagsHint": "关闭后，标记家访完成时不会自动给学生打标签",
  "profile.calendarBirthdays": "在日历中显示学生生日",
  "profile.calendarBirthdaysHint": "关闭后，首页月历不再显示根据出生日期推算的生日",
  "profile.nameDisplay": "首页称呼",
  "profile.nameDisplayHint": "控制在首页问候语和侧边栏中如何显示你的名字",
  "profile.nameDisplayFull": "全名（如「张毅」）",
  "profile.nameDisplayTeacher": "姓氏 + 老师（如「张老师」）",
  "profile.settingsSaved": "偏好已保存",

  // --- 考试 ---
  "examnew.title": "新建考试",
  "examnew.subtitle": "创建后可在考试详情里查看各班平均分",
  "examnew.name": "考试名称",
  "examnew.nameRequired": "请填写考试名称",
  "examnew.date": "考试日期",
  "examnew.term": "学期",
  "examnew.type": "考试类型",
  "examnew.year": "学年",
  "examnew.subjects": "考试科目",
  "examnew.fullScore": "满分",
  "examnew.subjectsHint": "点常用科目加入，每科可改名称、满分和颜色；也可以自行添加。",
  "examnew.selectAllSubjects": "全选",
  "examnew.addSubject": "添加科目",
  "examnew.customSubject": "自定义科目",
  "examnew.subjectName": "科目名称",
  "examnew.subjectColor": "颜色",
  "examnew.subjectDup": "科目名称不能重复",
  "examnew.subjectNameRequired": "请填写科目名称",
  "examnew.fullScoreInvalid": "每科满分须大于 0",
  "examnew.submit": "创建考试",
  "examnew.saving": "创建中…",
  "examnew.subjectsRequired": "请至少选择一个科目",
  "examnew.dateInvalid": "请选择一个 2000–2100 年之间的考试日期",
  "examnew.endDate": "结束日期",
  "examnew.endDateHint": "多天考试（如中考、高考）可填写结束日期",
  "examnew.endDateInvalid": "结束日期不能早于考试日期",

  "exatype.monthly": "月考",
  "exatype.midterm": "期中考试",
  "exatype.final": "期末考试",
  "exatype.quiz": "随堂测",
  "term.T1": "第一学期",
  "term.T2": "第二学期",

  "exams.create": "新建考试",
  "exams.title": "考试",
  "exams.subtitle": "共 {count} 次考试 · 点开可查看平均分",
  "exams.viewAverages": "查看平均分",
  "exams.fullScore": "满分",
  "exams.emptyTitle": "还没有考试",
  "exams.emptyDesc": "新建一次考试并选好科目，之后就能在学生档案里录入成绩。",

  "exam.averages": "平均分",
  "exam.perClass": "各班平均分",
  "exam.trendTitle": "全校平均分趋势",
  "exam.trendSub": "虚线标出当前这次考试 · 悬停查看各科平均分",
  "exam.avg": "平均分",
  "exam.outOf": "满分",
  "exam.min": "最低",
  "exam.max": "最高",
  "exam.students": "{count} 人",
  "exam.exams": "{count} 次考试",
  "exam.attributionNote": "各班人数按学生考试当日所在班级统计",
  "exam.deleteConfirm": "删除后，这次考试的所有科目成绩都会被清掉。",
  "exam.subjectLockNote": "已经有成绩录入时，科目结构不能修改。要改科目请先删除这次考试。",

  // --- 学生 ---
  "students.title": "学生",
  "students.subtitle": "共 {count} 名学生 · 点击任意一行打开档案",
  "students.search": "搜索姓名、学号或班级",
  "students.ungrouped": "未分班",
  "students.emptyTitle": "还没有学生",
  "students.emptyDesc": "先把学生加进班级，才能开始记成绩和跟进。",
  "students.groupCollapsed": "已折叠",

  // --- 评语 ---
  "commentNew.title": "写评语",
  "commentNew.subtitle": "记录关于学生的评语；若涉及其他学生，他们也会在自己的时间线里看到",
  "commentNew.studentLabel": "学生",
  "commentNew.studentHint": "这条评语主要关于哪位学生",
  "commentNew.studentPlaceholder": "请选择学生",
  "commentNew.studentRequired": "请选择一名学生",
  "commentNew.notesLabel": "评语内容",
  "commentNew.notesHint": "例如课堂表现、同学矛盾、需要跟进的情况",
  "commentNew.notesPlaceholder": "写下你的观察或记录…",
  "commentNew.notesRequired": "请填写评语内容",
  "commentNew.dateLabel": "日期",
  "commentNew.mentionLabel": "涉及的其他学生",
  "commentNew.mentionHint": "可选；被提到的学生时间线也会显示这条评语",
  "commentNew.showMentions": "选择涉及的学生",
  "commentNew.hideMentions": "收起学生列表",
  "commentNew.mentionCount": "已选 {n} 人",
  "commentNew.submit": "保存评语",
  "commentNew.saving": "保存中…",

  "th.admissionNo": "学号",
  "th.name": "姓名",
  "th.gender": "性别",
  "th.class": "班级",
  "th.status": "状态",
  "th.exam": "考试",
  "th.tags": "标签",
  "th.lastEvent": "最近事件",
  "th.subject": "科目",
  "th.score": "分数",

  "detail.back": "返回学生列表",
  "detail.born": "出生日期",
  "detail.guardian": "监护人",
  "detail.scores": "考试成绩",
  "detail.scoresHint": "点任意一个分数即可就地更正，每次修改都会留下痕迹",
  "detail.events": "事件记录",
  "detail.timeline": "时间线",
  "detail.timelineSub": "由你添加的记录可以点开编辑；系统自动生成的不可编辑",
  "detail.timelineToday": "今天",
  "detail.trendTitle": "成绩变化趋势",
  "detail.trendSub": "各科成绩随考试变化",
  "detail.addGuardian": "添加监护人",
  "detail.addTag": "添加标签",
  "detail.tagName": "标签名称",
  "detail.tagNameRequired": "请填写标签名称",
  "detail.tagInUse": "点一下就能复用",
  "detail.scoresExpand": "展开更早的 {n} 条成绩",
  "detail.scoresCollapse": "收起更早的成绩",
  "detail.editReason": "工作台内更正",
  "detail.recordEvent": "记录家访",
  "detail.nameRequired": "请填写学生姓名",
  "detail.admissionNoRequired": "请填写学号",
  "detail.deleteConfirm": "如果他已有成绩或跟进记录，只会停用账号并保留数据；没有记录才会彻底删除。",
  "detail.profileEditTitle": "编辑资料",
  "detail.status": "状态",
  "detail.noScores": "还没有成绩",
  "detail.noScoresDesc": "参加考试后，成绩会显示在这里。",
  "detail.noEvents": "还没有事件记录",

  // --- 事件 ---
  "event.close": "收起",
  "event.type": "事件类型",
  "event.purpose": "事件目的",
  "event.homeVisitPurpose": "家访目的",
  "event.purposeHint": "写清楚为什么做这件事，半年后回看才想得起来",
  "event.purposeRequired": "请填写事件目的",
  "event.defaultPurpose": "例行家访",
  "event.summary": "事件摘要",
  "event.description": "说明",
  "event.summaryRequired": "请填写事件摘要",
  "event.homeVisitDone": "家访已完成",
  "event.homeVisitDoneHint": "完成后可自动给学生添加「已家访」标签（可在个人中心关闭）",
  "event.occurredAt": "事件时间",
  "event.occurredAtHint": "留空则记为当前时间",
  "event.save": "保存事件",
  "event.saving": "保存中…",
  "event.deleteConfirm": "删除后，这条记录会从时间线上消失。",
  "event.systemReadOnly": "这条记录由系统自动生成，只能查看，不能修改或删除。",

  "empty.scores": "还没有成绩",
  "empty.events": "还没有事件记录",

  // --- 状态枚举 ---
  "status.active": "在读",
  "status.inactive": "已停用",
  "status.entered": "已录入",
  "status.absent": "缺考",

  "gender.F": "女",
  "gender.M": "男",
  "gender.O": "其他",

  // --- 时间线事件 ---
  "tl.enrolled": "入学",
  "tl.class_moved": "转班",
  "tl.class_joined": "加入班级",
  "tl.exam": "考试",
  "tl.score": "成绩",
  "tl.exam_taken": "参加考试",
  "tl.result_changed": "成绩更正",
  "tl.birthday": "生日",
  "tl.home_visited": "家访",
  "tl.parent_call": "家长沟通",
  "tl.activity": "活动",
  "tl.talk": "谈心",
  "tl.tutoring": "辅导",
  "tl.note_added": "教师备注",
  "tl.comment": "评语",
  "tl.joined": "加入 {class}",

  // --- 404 ---
  "nf.title": "这一页被黑板擦擦掉了",
  "nf.sub": "你要找的页面不存在，或者已经被移除。",
  "nf.backHome": "返回首页",
  "nf.backStudents": "去看看学生",
  "nf.eventGone": "这条记录不存在了",
  "nf.eventGoneSub": "它可能已经被删除。回到学生的时间线看看其他的记录。",
  "nf.guardianGone": "这位监护人不存在了",
  "nf.guardianGoneSub": "可能已经从学生档案里移除。",
  "nf.backTimeline": "返回学生时间线",
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

// 日期区间文案：单日返回完整日期；跨天（多日考试）返回 "6月7日 – 6月9日"
export function formatDateRange(d1, d2) {
  const fmtFull = (d) =>
    new Date(d).toLocaleDateString("zh-CN", { year: "numeric", month: "short", day: "numeric" })
  if (!d2 || d1 === d2) return fmtFull(d1)
  const start = new Date(d1)
  const end = new Date(d2)
  const endText = end.toLocaleDateString(
    "zh-CN",
    start.getFullYear() === end.getFullYear()
      ? { month: "short", day: "numeric" }
      : { year: "numeric", month: "short", day: "numeric" }
  )
  return `${fmtFull(d1)} – ${endText}`
}

// ------------------------------------------------------------------ 学科

// 常用科目目录：key 是存进考试 payload 的稳定标识（与 seed 一致），
// label / fullScore / color 是新建考试时的预填值，也可被当场改掉。
export const COMMON_SUBJECTS = [
  { key: "chinese", label: "语文", fullScore: 120, color: "#b98a2e" },
  { key: "math", label: "数学", fullScore: 120, color: "#2e6ba8" },
  { key: "english", label: "英语", fullScore: 120, color: "#2f7d4f" },
  { key: "politics", label: "道德与法治", fullScore: 100, color: "#c2608f" },
  { key: "history", label: "历史", fullScore: 100, color: "#8c564b" },
  { key: "geography", label: "地理", fullScore: 100, color: "#2b8a8a" },
  { key: "biology", label: "生物", fullScore: 100, color: "#5a8f29" },
  { key: "physics", label: "物理", fullScore: 100, color: "#6d5bb8" },
  { key: "chemistry", label: "化学", fullScore: 100, color: "#b42318" },
]
export const COMMON_SUBJECT_KEYS = COMMON_SUBJECTS.map((s) => s.key)

const SUBJECTS = Object.fromEntries(COMMON_SUBJECTS.map((s) => [s.key, s.label]))
export function subject(s) {
  return SUBJECTS[s] ?? (s ?? "")
}

const SUBJECT_COLORS = Object.fromEntries(COMMON_SUBJECTS.map((s) => [s.key, s.color]))
export function subjectColor(s, override) {
  if (override) return override
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

// ------------------------------------------------------------------ 性别

// 后端存的是 F / M（见 seed.py），O 表示其他，空值表示未填写
export const GENDER_OPTIONS = [
  { value: "", label: "未填写" },
  { value: "F", label: "女" },
  { value: "M", label: "男" },
  { value: "O", label: "其他" },
]

export function tagStyle(color) {
  return color ? { "--tag-color": color } : {}
}

export function genderLabel(g) {
  if (!g) return "—"
  return t(`gender.${g}`) === `gender.${g}` ? g : t(`gender.${g}`)
}

// ------------------------------------------------------------------ 状态

const STUDENT_STATUS = { active: "在读", inactive: "已停用" }
export function studentStatusLabel(s) {
  return (s && STUDENT_STATUS[s]) || s || "—"
}
export function studentStatusTone(s) {
  return s === "active" ? "ok" : "muted"
}

const RESULT_STATUS = { entered: "已录入", absent: "缺考" }
export function resultStatusLabel(s) {
  return (s && RESULT_STATUS[s]) || s || "—"
}

// ------------------------------------------------------------ 事件类型元数据

// icon 对应 components/Icon.vue
const EVENT_TYPES = {
  enrolled: { icon: "enroll", color: "#6B7A72" },
  class_moved: { icon: "swap", color: "#6D5BB8" },
  exam_taken: { icon: "clipboard", color: "#2E6BA8" },
  result_changed: { icon: "pencil", color: "#B45309" },
  home_visited: { icon: "home", color: "#2F7D4F" },
  parent_call: { icon: "phone", color: "#367C6B" },
  talk: { icon: "note", color: "#4F6EAD" },
  tutoring: { icon: "board", color: "#854D0E" },
  note_added: { icon: "note", color: "#5C6B63" },
  comment: { icon: "note", color: "#7C5BA8" },
  birthday: { icon: "cake", color: "#9A5B07" },
  activity: { icon: "flag", color: "#0E7490" },
  exam: { icon: "clipboard", color: "#2E6BA8" },
  score: { icon: "clipboard", color: "#1D4ED8" },
}

export function eventTypeIcon(type) {
  return (EVENT_TYPES[type] || { icon: "note" }).icon
}

export function eventTypeColor(type) {
  return (EVENT_TYPES[type] || { color: "#94a3b8" }).color
}

export function isClassJoinEvent(type, payload = {}) {
  return type === "class_moved" && !payload?.from_class && !payload?.from
}

export function eventTypeLabel(type, payload = null) {
  if (isClassJoinEvent(type, payload || {})) return t("tl.class_joined")
  const key = `tl.${type}`
  return messages[key] ?? type
}

export function describeEvent(type, p = {}) {
  switch (type) {
    case "enrolled":
      if (p.notes) return p.notes
      return t("tl.joined", { class: p.class_name ?? p.class ?? "" })
    case "class_moved":
      if (p.notes) return p.notes
      if (!p.from_class && !p.from) {
        const to = p.to_class ?? p.to ?? ""
        return to ? t("tl.joined", { class: to }) : ""
      }
      return `${p.from_class ?? p.from ?? ""} → ${p.to_class ?? p.to ?? ""}${p.reason ? " · " + p.reason : ""}`
    case "exam_taken": {
      if (p.notes) return p.notes
      const scores = p.scores
        ? Object.entries(p.scores).map(([s, v]) => `${subject(s)} ${v}`).join(", ")
        : ""
      return `${p.exam ?? ""}${scores ? " — " + scores : ""}`
    }
    case "result_changed":
      if (p.notes) return p.notes
      return `${p.exam ?? ""} · ${subject(p.subject)}: ${p.old} → ${p.new}${p.reason ? " · " + p.reason : ""}`
    case "birthday": {
      const [y, m, d] = (p.birth_date ?? "").split("-")
      return y ? `出生于 ${y}年${parseInt(m)}月${parseInt(d)}日` : "生日"
    }
    case "activity":
      return p.notes ?? ""
    case "home_visited":
    case "parent_call":
      return `${p.guardian ? `与${p.guardian} · ` : ""}${p.purpose ? p.purpose + " — " : ""}${p.summary || ""}`
    case "talk":
    case "tutoring":
    case "note_added":
    case "comment": {
      const base = p.notes ?? p.summary ?? p.note ?? ""
      const names = (p.mentioned || []).map((m) => m.name).filter(Boolean)
      if (!names.length) return base
      return `${base}${base ? " · " : ""}涉及：${names.join("、")}`
    }
    case "exam": {
      const subjects = p.full_scores ? Object.keys(p.full_scores).map(subject).join("、") : ""
      return [p.term ? `${p.term}考试` : "", subjects].filter(Boolean).join(" · ") || "考试"
    }
    case "score":
      return `${subject(p.subject)}：${p.absent ? "缺考" : `${p.score ?? "-"}/${p.max_score ?? "-"}`}`
    default:
      return p.summary ?? JSON.stringify(p)
  }
}

// 可手动记录的事件类型（供下拉选择，而不是让用户背代码）
export const RECORDABLE_EVENT_TYPES = [
  { value: "home_visited", label: "tl.home_visited" },
]
// 手动记录暂时只开放家访；其余类型（家长沟通/谈心/辅导/教师备注）的历史
// 记录仍可编辑。录入成绩走考试详情页和学生档案的成绩卡，不在这个表单里。
export function recordableEventOptions() {
  return RECORDABLE_EVENT_TYPES.map((o) => ({ value: o.value, label: t(o.label) }))
}

// ------------------------------------------------------------------ 错误处理

// 把后端/网络错误翻译成能指导下一步动作的话（错误可识别、可诊断、可恢复）
const ERROR_HINTS = [
  [/登录已过期|not authenticated|未登录/i, "登录已过期，请重新登录"],
  [/failed to fetch|networkerror|网络/i, "连接不上服务器，请检查网络后重试"],
  [/not found/i, "找不到这条数据，它可能已经被删除"],
  [/已存在|already|duplicate|unique/i, "已经有重复的内容了，请换个名称"],
  [/仍有学生|still has/i, "这个班级里还有学生，请先给他们换个班级"],
  [/权限|forbidden|无权/i, "你没有执行这个操作的权限"],
]

export function friendlyError(e) {
  const raw = (e?.message || "").trim()
  if (!raw) return "出了点问题，请重试"
  for (const [re, hint] of ERROR_HINTS) {
    if (re.test(raw)) return hint
  }
  // 后端返回的英文技术信息不该直接丢给老师看
  if (/^[a-z0-9_\s:.'"()\-]+$/i.test(raw) && !/[一-龥]/.test(raw)) {
    return "操作没有成功，请稍后重试"
  }
  return raw
}
