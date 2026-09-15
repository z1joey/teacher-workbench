// 中文界面词典与领域文案助手：t() 查词典，subject/genderLabel/statusLabel 等
// 把后端存储的枚举代码（math、F、active…）渲染成人话。
// subjectColor 与 EVENT_TYPES 供图表和时间线取色/取图标。
const messages = {
  "app.title": "高素质工作台",
  "nav.home": "首页",
  "nav.students": "学生",
  "nav.classes": "班级",
  "nav.exams": "考试",
  "nav.admin": "管理",
  "nav.profile": "个人中心",
  "nav.menu": "导航菜单",
  "nav.commandPalette": "命令面板",
  "nav.help": "帮助与快捷键",
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
  "common.edit": "编辑",

  // --- 管理后台 ---
  "admin.title": "开发者后台",
  "admin.navOverview": "概览",
  "admin.subtitleOverview": "数据库统计与各表行数",
  "admin.subtitleAccounts": "启停用账号、调整角色与重置密码",
  "admin.subtitleFeedback": "查看教师提交的意见与建议",
  "admin.subtitleSessions": "查看并终止活动登录会话",
  "admin.subtitleInspect": "按表预览原始数据，用于排查问题",
  "admin.subtitleSettings": "注册开关与系统维护",
  "admin.subtitleDanger": "不可撤销的系统级操作",
  "admin.refresh": "刷新",
  "admin.sectionOverview": "数据库概览",
  "admin.sectionSettings": "站点设置",
  "admin.sectionSettingsGeneral": "常规",
  "admin.dangerZoneDesc": "这一区的操作不可撤销，执行前会要求你再次确认。",
  "admin.registrationEnabled": "开放用户注册",
  "admin.registrationEnabledDesc": "关闭后，新用户无法自行注册教师账号，已有账号不受影响。",
  "admin.registrationEnabledOn": "已开放注册",
  "admin.registrationEnabledOff": "已关闭注册",
  "admin.sectionAccounts": "账号管理",
  "admin.sectionSessions": "活动会话",
  "admin.sectionInspect": "数据探查",
  "admin.sectionDanger": "危险操作",
  "admin.sectionFeedback": "用户反馈",
  "admin.feedbackEmpty": "还没有收到反馈",
  "admin.feedbackOpenLabel": "待处理",
  "admin.feedbackResolvedLabel": "已解决",
  "admin.feedbackResolve": "标记已解决",
  "admin.feedbackResolved": "已标记为解决",
  "admin.feedbackReopened": "已重新打开",
  "admin.feedbackDeleted": "反馈已删除",
  "admin.feedbackDeleteTitle": "删除这条反馈？",
  "admin.feedbackDeleteConfirm": "删除后无法恢复。",
  "admin.dbDriver": "数据库驱动",
  "admin.dbTables": "数据表行数",
  "admin.personsTotal": "身份总数",
  "admin.accountsTotal": "可登录账号",
  "admin.usersAdmins": "管理员",
  "admin.accountsActive": "活跃账号",
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
  "admin.roleStudent": "学生",
  "admin.roleGuardian": "监护人",
  "admin.accountEmail": "邮箱",
  "admin.manageOnStudents": "在学生档案管理",
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
  "admin.inspectPrev": "上一页",
  "admin.inspectNext": "下一页",
  "admin.inspectPage": "第 {page} / {total} 页",
  "admin.inspectTotal": "共 {total} 行",
  "admin.inspectNoData": "暂无数据",
  "admin.inspectViewFull": "查看完整内容",
  "admin.resetDb": "重置数据库",
  "admin.resetDbWarn": "这会清空所有表里的全部数据，并重建空表。",
  "admin.resetDbDone": "数据库已重置。",
  "admin.loading": "加载中…",
  "admin.saved": "已保存",
  "admin.error": "操作失败",

  // --- 班级 ---
  "classes.title": "班级",
  "classes.subtitle": "班均与最近动态，点进班级查看完整名单",
  "classes.seating": "座位表",
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
  "classdetail.batchSelect": "批量操作",
  "classdetail.batchExit": "退出多选",
  "classdetail.batchAll": "全选",
  "classdetail.batchNone": "清空",
  "classdetail.batchSelected": "已选 {n} 人",
  "classdetail.batchTarget": "转入",
  "classdetail.batchConfirm": "确认分配",
  "classdetail.batchConfirmTitle": "将 {n} 名学生转入「{class}」？",
  "classdetail.batchConfirmHint": "转班记录会写入每个学生的时间线。",
  "classdetail.batchDone": "已转入 {n} 人",
  "classdetail.batchDoneSkipped": "已转入 {moved} 人，{skipped} 人已在目标班级，已跳过",
  "classdetail.noScores": "这个班级还没有成绩数据",

  // --- 登录 ---
  "login.name": "姓名",
  "login.email": "邮箱",
  "login.password": "密码",
  "login.submit": "登录",
  "login.submitting": "正在登录…",
  "login.needHelp": "忘记密码？",
  "login.noAccount": "还没有账号？",
  "login.goSignup": "注册",

  // --- 忘记密码 ---
  "forgot.title": "忘记密码",
  "forgot.subtitle": "输入注册邮箱，我们会发送验证码帮你重置密码",
  "forgot.emailLabel": "注册邮箱",
  "forgot.sendCode": "发送验证码",
  "forgot.sending": "发送中…",
  "forgot.resendIn": "{n} 秒后可重新发送",
  "forgot.sentHint": "若该邮箱已注册，验证码邮件已发出，请查收（注意垃圾箱）",
  "forgot.codeLabel": "验证码",
  "forgot.codePlaceholder": "6 位数字验证码",
  "forgot.newPasswordLabel": "新密码",
  "forgot.newPasswordHint": "至少 6 位",
  "forgot.confirmLabel": "确认新密码",
  "forgot.confirmMismatch": "两次输入的密码不一致",
  "forgot.codeRequired": "请输入验证码",
  "forgot.passwordRequired": "请填写新密码",
  "forgot.submit": "重置密码",
  "forgot.submitting": "正在重置…",
  "forgot.success": "密码已重置，请用新密码登录",
  "forgot.backToLogin": "返回登录",

  // --- 注册 ---
  "signup.emailRequired": "请输入邮箱",
  "signup.emailInvalid": "邮箱格式不正确",
  "signup.passwordShort": "密码至少 6 位",
  "signup.password2": "确认密码",
  "signup.passwordMismatch": "两次输入的密码不一致",
  "signup.submit": "注册",
  "signup.submitting": "正在注册…",
  "signup.success": "注册成功，欢迎加入",
  "signup.hasAccount": "已有账号？",
  "signup.goLogin": "去登录",
  "signup.closed": "当前未开放注册",
  "signup.closedHint": "如需开通账号，请联系管理员。",

  // --- 用户反馈 ---
  "feedback.entry": "用户反馈",
  "feedback.title": "用户反馈",
  "feedback.feature": "反馈的功能模块",
  "feedback.content": "具体内容",
  "feedback.contentPlaceholder": "说说你遇到的问题或想提的建议…",
  "feedback.required": "请填写反馈内容，或点「取消」",
  "feedback.remaining": "还可输入 {n} 字",
  "feedback.submit": "提交反馈",
  "feedback.submitting": "正在提交…",
  "feedback.sent": "反馈已提交，感谢你的意见！",
  "feedback.featureHome": "首页",
  "feedback.featureStudents": "学生",
  "feedback.featureClasses": "班级",
  "feedback.featureExams": "考试",
  "feedback.featureVisits": "家访",
  "feedback.featureSettings": "个人",
  "feedback.featureOther": "其他",

  // --- 首页 ---
  "home.greeting": "你好，{name}",
  "home.today": "今天是 {date}",
  "home.recentEvents": "最新动态",
  "home.recentEventsSub": "全校最近发生的记录",
  "home.noRecentEvents": "最近还没有记录",
  "home.statStudents": "学生",
  "home.statClasses": "班级",
  "home.statExams": "考试",
  "home.statInteractions": "跟进记录",
  "home.upcoming": "即将考试",
  "home.upcomingSub": "按考试时间排序，点击进入考试详情",
  "home.upcomingEmpty": "近期没有考试安排",
  "home.upcomingToday": "今日",
  "home.upcomingSoon": "3天内",
  "home.loadEmptyTitle": "首页内容没能加载",
  "home.loadEmptyDesc": "请检查网络连接后重试。",
  "detail.loadEmptyTitle": "学生档案没能加载",
  "exam.loadEmptyTitle": "考试详情没能加载",
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
  "home.calSummaryRequired": "请填写内容",
  "home.calPurpose": "事由",
  "home.calReadOnly": "生日由系统根据学生出生日期每年自动生成，不能编辑或删除。学生离校后会自动移除。",
  "home.calNotifyThisWeek": "本周",
  "home.calNotifyNextWeek": "下周",

  // --- 数据 ---
  "data.ioTitle": "数据转移",
  "data.importTitle": "数据导入",
  "data.importNote": "目前仅支持花名册（Excel）导入。",
  "data.importDesc": "表头需含学号、姓名、性别，可含出生日期与监护人信息。只导入学生，不创建班级。",
  "data.importClassHint": "默认进入未分班；已有学生仅更新资料",
  "data.importTemplate": "下载模板",
  "data.importRoster": "导入花名册",
  "data.exportTitle": "数据导出",
  "data.exportDesc": "按当前班级名单导出花名册、家访记录或成绩。成绩为一个工作簿，每场考试单独一个 Sheet，格式与考试详情页成绩模板一致。",
  "data.exportClass": "班级",
  "data.exportClassPlaceholder": "选择班级",
  "data.exportRoster": "导出花名册",
  "data.exportVisits": "导出家访记录",
  "data.exportScores": "导出成绩",
  "data.exportSelectClass": "请选择要导出的班级",
  "data.exportFail": "导出失败",
  "data.demoTitle": "演示数据",
  "data.demoSub": "用于本地试用或发布前验收：演示内容绑定当前教师账号，仅教师可操作。",
  "data.demoBody": "包含两个班级、全年成绩曲线、座位表、家访、谈心、辅导、家长沟通、评语、学生总结、比赛活动等真实场景。加载或清空后都会保留你当前登录的教师账号，无需重新登录。",
  "data.demoSeed": "加载演示数据",
  "data.demoSeedWarn": "这会清空现有业务数据，并写入演示用的班级、学生、考试与跟进记录。",
  "data.demoSeedDone": "演示数据已加载",
  "data.demoSeedFail": "加载演示数据失败",
  "data.demoSeedBlocked": "已有业务数据，无法直接加载",
  "data.demoSeedMustClearFirst":
    "当前工作台已有数据（真实数据或演示数据均可）。加载新的演示数据前，必须先「清空业务数据」。",
  "data.demoSeedMustClearHint": "清空会删除全部学生、班级、考试、成绩与跟进记录，且无法恢复。",
  "data.demoReset": "清空业务数据",
  "data.demoResetHint": "注意：已有业务数据时，要先「清空业务数据」才能加载演示数据。清空会删除所有真实数据（学生、班级、考试、成绩、跟进记录），且无法恢复。",
  "data.demoResetWarn": "这会删除全部数据——不只是演示数据：你真实录入的所有学生、班级、考试、成绩和跟进记录都会被永久删除，回到空白工作台。",
  "data.demoResetConfirm": "清空数据",
  "data.demoResetDone": "业务数据已清空",
  "data.demoResetFail": "清空失败",

  // --- 事件（普通事件） ---
  "events.title": "事件",
  "events.subtitle": "共 {count} 条普通事件 · 比赛、活动等",
  "feed.participants": "参与人：",
  "feed.participantClasses": "参与班级：",
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
  "visits.emptyDesc": "在学生档案里点「家访」即可添加。",
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
  "students.addComment": "记录",

  // --- 个人中心 ---
  "profile.title": "个人中心",
  "profile.subtitle": "个人信息、班级与教学足迹",
  "profile.loginEmail": "登录邮箱",
  "profile.phone": "手机号",
  "profile.phoneEmpty": "未填写",
  "profile.phoneHint": "6-15 位数字，可用空格或短横线分隔",
  "profile.phoneInvalid": "手机号格式不正确，请输入 6-15 位数字",
  "profile.nameHint": "选填；留空时将显示邮箱前缀",
  "profile.activity": "教学足迹",
  "profile.recordsLogged": "跟进记录",
  "profile.resultsEntered": "录入成绩",
  "profile.commentsWritten": "记录事件",
  "profile.editInfo": "编辑资料",
  "profile.saved": "已保存",
  "profile.studentsCount": "{n} 人",
  "profile.settings": "偏好设置",
  "profile.autoTags": "家访完成后自动添加「已家访」标签",
  "profile.autoTagsHint": "关闭后，标记家访完成时不会自动给学生打标签",
  "profile.clearHomeVisitTags": "清除所有「已家访」标签",
  "profile.clearHomeVisitTagsHint": "只清除你工作区内学生身上的该标签，不影响家访记录",
  "profile.clearHomeVisitTagsConfirm": "确定清除所有学生身上的「已家访」标签？家访记录不会删除。",
  "profile.clearHomeVisitTagsDone": "已清除 {n} 个「已家访」标签",
  "profile.clearHomeVisitTagsEmpty": "当前没有可清除的「已家访」标签",
  "profile.calendarBirthdays": "在日历中显示学生生日",
  "profile.calendarBirthdaysHint": "关闭后，首页月历不再显示根据出生日期推算的生日",
  "profile.settingsSaved": "偏好已保存",

  // --- 首登称呼弹窗 ---
  "namePrompt.title": "怎么称呼您？",
  "namePrompt.placeholder": "您的称呼",
  "namePrompt.hint": "可以先跳过，稍后在「个人中心」设置称呼",
  "namePrompt.required": "请输入称呼，或点「跳过」",
  "namePrompt.skip": "跳过",
  "namePrompt.save": "保存",
  "namePrompt.saving": "正在保存…",
  "namePrompt.saved": "称呼已保存",

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
  "examnew.classes": "参加班级",
  "examnew.classesSelected": "已选 {n} 班",
  "examnew.classesHint": "以班级为单位选择参加考试的学生，选中的班级学生会带上这次考试；不选则全校在读学生参加。",
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
  "exams.pastSection": "已结束的考试",

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
  "exam.perClassEmpty": "还没有成绩录入，录入后这里会按班级显示平均分。",
  "exam.deleteConfirm": "删除后，这次考试的所有科目成绩都会被清掉。",
  "exam.subjectLockNote": "已经有成绩录入时，科目结构不能修改。要改科目请先删除这次考试。",
  "exam.scoreImportTitle": "成绩导入（Excel）",
  "exam.scoreImportDesc": "下载模板后按学号填入各科成绩（可写「缺考」），再上传导入。按学号匹配学生，重复导入会覆盖旧成绩；成功后学生会生成「参加考试」时间线记录。",
  "exam.scoreTemplate": "下载模板",
  "exam.scoreImport": "导入成绩",
  "exam.scoreImportPick": "选择成绩文件（.xlsx）",
  "exam.scoreImportDone": "成绩导入成功",
  "exam.scoreImportFail": "成绩导入失败",
  "exam.scoreImportOk": "导入成功",
  "exam.scoreImportPartial": "部分成功",
  "exam.scoreImportError": "失败",

  // --- 学生 ---
  "students.title": "学生",
  "students.subtitle": "共 {count} 名学生 · 点击任意一行打开档案",
  "students.search": "搜索姓名、学号、班级或监护人",
  "students.ungrouped": "未分班",
  "students.noRecentEvent": "这位同学最近很低调，暂无动态",
  "students.emptyTitle": "还没有学生",
  "students.emptyDesc": "先把学生加进班级，才能开始记成绩和跟进。",
  "students.groupCollapsed": "已折叠",

  // --- 评语 ---
  "commentNew.title": "添加记录",
  "commentNew.subtitle": "记录关于学生的情况；若涉及其他学生，他们也会在自己的时间线里看到",
  "commentNew.studentLabel": "学生",
  "commentNew.studentHint": "这条记录主要关于哪位学生",
  "commentNew.studentPlaceholder": "请选择学生",
  "commentNew.studentRequired": "请选择一名学生",
  "commentNew.notesLabel": "记录内容",
  "commentNew.notesHint": "例如课堂表现、同学矛盾、需要跟进的情况",
  "commentNew.notesPlaceholder": "写下你的观察或记录…",
  "commentNew.notesRequired": "请填写记录内容",
  "commentNew.dateLabel": "日期",
  "commentNew.mentionLabel": "涉及的其他学生",
  "commentNew.mentionHint": "可选；被提到的学生时间线也会显示这条记录",
  "commentNew.showMentions": "选择涉及的学生",
  "commentNew.hideMentions": "收起学生列表",
  "commentNew.mentionCount": "已选 {n} 人",
  "commentNew.submit": "保存记录",
  "commentNew.saving": "保存中…",

  // --- 学生总结 ---
  "summary.title": "学生总结",
  "summary.open": "总结",
  "summary.subtitle": "根据学生的事件记录，用 AI 生成阶段性总结；总结只出现在你自己的动态里，学生时间线看不到",
  "summary.rangeLabel": "时间段",
  "summary.rangeAll": "全部",
  "summary.range90d": "近90天",
  "summary.rangeHalfYear": "近半年",
  "summary.rangeCustom": "自定义",
  "summary.rangeFrom": "开始日期",
  "summary.rangeTo": "结束日期",
  "summary.rangeInvalid": "开始日期不能晚于结束日期",
  "summary.lengthLabel": "字数",
  "summary.lengthBrief": "简短（约50字）",
  "summary.lengthStandard": "标准（约100字）",
  "summary.lengthDetailed": "详细（约150字）",
  "summary.styleLabel": "风格",
  "summary.styleFormal": "客观正式",
  "summary.styleWarm": "亲切温暖",
  "summary.styleMotivational": "鼓励向上",
  "summary.generate": "生成总结",
  "summary.generating": "生成中…",
  "summary.regenerate": "重新生成",
  "summary.previewLabel": "总结内容（可修改后保存）",
  "summary.emptyRange": "所选时间段内没有学生记录，换个时间段试试",
  "summary.save": "保存总结",
  "summary.saved": "总结已保存",
  "summary.historyTitle": "历史总结",
  "summary.historyEmpty": "还没有保存过总结；生成并保存后会显示在这里",
  "summary.edited": "已编辑",
  "summary.count": "{n} 条总结",
  "summary.deleteTitle": "删除这条总结？",
  "summary.deleteConsequences": "删除后无法恢复（可在 {n} 秒内撤销）",
  "summary.deleted": "总结已删除",

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
  "detail.scoresHint": "折线图展示历次考试，下方默认列出全部成绩，可收起只看选中的那一场（点选图中场次或用 ← → 切换）。点分数可就地更正，↑↓ 为较上一场，更正显示调整幅度",
  "detail.addScore": "添加成绩",
  "detail.scoreAdded": "成绩已添加",
  "scoreNew.groupUnentered": "未录入",
  "scoreNew.groupEntered": "已录入",
  "scoreNew.badgeUnentered": "未录入",
  "scoreNew.badgeEntered": "已录 {n} 科",
  "scoreNew.scoreNaN": "{subject} 的成绩要填数字",
  "scoreNew.scoreRange": "{subject} 的成绩需在 0 到 {max} 之间",
  "scoreNew.needScore": "至少填写一科成绩，或勾选缺考",
  "scoreNew.pickExam": "请先选择考试",
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
  "detail.recordEvent": "家访",
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
  "status.graduated": "已毕业",
  "status.entered": "已录入",
  "status.absent": "缺考",
  "classes.archived": "已归档",
  "classdetail.unarchive": "取消归档",
  "classdetail.unarchiveDone": "已取消归档",
  "profile.graduatedArchive": "毕业归档",
  "profile.graduatedArchiveHint": "将整个班级标记为毕业：学生带上「已毕业」标签并从默认列表隐藏，数据不会删除。",
  "profile.graduatedSuffix": "已毕业",
  "profile.viewRoster": "查看名单",
  "profile.hideRoster": "收起名单",
  "profile.noArchivedClasses": "暂无归档班级。",
  "profile.graduateAction": "标记毕业",
  "profile.graduateConfirmTitle": "将「{class}」的 {n} 名在读学生标记为已毕业？",
  "profile.graduateConfirmHint": "数据不会删除：学生会带上「已毕业」标签并从默认列表隐藏，班级转为已归档，之后仍可查看或手动删除。",
  "profile.graduateConfirm": "确认毕业",
  "profile.graduateDone": "已毕业 {n} 人，班级已归档",

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
  "tl.seat_changed": "换座位",
  "tl.birthday": "生日",
  "tl.home_visited": "家访",
  "tl.comment": "记录",
  "tl.joined": "加入 {class}",
  "tl.graduated": "毕业",
  "tl.graduatedFrom": "从 {class} 毕业",

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

// 本地时区的今天，YYYY-MM-DD（与 <input type="date"> 的值格式一致，可直接字符串比较）
export function todayStr() {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`
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

/** exam_taken / 时间线副标题：只展示各科成绩，不含考试名前缀。 */
export function formatExamScoreSummary(scores) {
  if (!scores || typeof scores !== "object") return ""
  const order = (s) => {
    const i = COMMON_SUBJECT_KEYS.indexOf(s)
    return i === -1 ? 99 : i
  }
  return Object.entries(scores)
    .sort(([a], [b]) => order(a) - order(b))
    .map(([s, v]) => {
      const n = Number(v)
      const text = Number.isFinite(n) && n % 1 !== 0 ? n.toFixed(1) : String(v)
      return `${subject(s)} ${text}`
    })
    .join(" · ")
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

/** 班级页顶栏面包屑：七年级 1 班 • 2025/2026 */
export function classBreadcrumbLabel(name, academicYear) {
  const spaced = String(name || "")
    .replace(/(\D)(\d)/g, "$1 $2")
    .replace(/(\d)(?=\D)/g, "$1 ")
    .replace(/\s+/g, " ")
    .trim()
  const year = String(academicYear || "").trim()
  return year ? `${spaced} • ${year}` : spaced
}

// ------------------------------------------------------------------ 状态

const STUDENT_STATUS = { active: "在读", inactive: "已停用", graduated: "已毕业" }
export function studentStatusLabel(s) {
  return (s && STUDENT_STATUS[s]) || s || "—"
}
export function studentStatusTone(s) {
  if (s === "active") return "ok"
  if (s === "graduated") return "warn"
  return "muted"
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
  home_visited: { icon: "home", color: "#2F7D4F" },
  comment: { icon: "note", color: "#7C5BA8" },
  birthday: { icon: "cake", color: "#9A5B07" },
  seat_changed: { icon: "swap", color: "#2B8A8A" },
  exam: { icon: "clipboard", color: "#2E6BA8" },
  score: { icon: "clipboard", color: "#1D4ED8" },
  summary: { icon: "clipboard", color: "#5B6FB8" },
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

// 事件展示标题（卡片、时间线、动态流等标题位全局复用）。
// 注意与 eventTypeLabel 区分——后者还用于
// 「删除这条生日记录？」这类句子拼接。
export function eventTitle(type, payload = null) {
  return eventTypeLabel(type, payload)
}

// 时间线/卡片展示名：优先 Event.title，再回退类型标签。
export function eventDisplayName(event) {
  const type = event.event_type
  const payload = event.payload || {}
  const name = (event.title || "").trim()

  if (type === "birthday") return eventTitle(type, payload)
  if (name) return name
  return eventTitle(type, payload)
}

/** Feed / timeline subtitle — drop text already shown in the title row. */
export function feedEventDesc(event) {
  const desc = describeEvent(event.event_type, event.payload || {})
  if (!desc) return ""
  const title = eventDisplayName(event)
  if (desc === title) return ""
  if (title && desc.startsWith(title)) {
    const rest = desc.slice(title.length).replace(/^\s*·\s*/, "").trim()
    return rest
  }
  return desc
}

export function describeEvent(type, p = {}) {
  switch (type) {
    case "enrolled":
      if (p.notes) return p.notes
      return t("tl.joined", { class: p.class_name ?? p.class ?? "" })
    case "graduated":
      if (p.notes) return p.notes
      return p.class_name ? t("tl.graduatedFrom", { class: p.class_name }) : t("tl.graduated")
    case "class_moved":
      if (p.notes) return p.notes
      if (!p.from_class && !p.from) {
        const to = p.to_class ?? p.to ?? ""
        return to ? t("tl.joined", { class: to }) : ""
      }
      return `${p.from_class ?? p.from ?? ""} → ${p.to_class ?? p.to ?? ""}${p.reason ? " · " + p.reason : ""}`
    case "exam_taken": {
      if (p.notes) return p.notes
      return formatExamScoreSummary(p.scores)
    }
    case "seat_changed":
      // from/to 是「第X排第Y列」或空：空 to = 移出座位表，空 from = 首次安排
      if (p.notes) return p.notes
      if (p.from && p.to) return `${p.from} → ${p.to}`
      if (p.to) return `安排座位：${p.to}`
      return "移出座位表"
    case "birthday":
      // 全局约定：生日只显示标题（见 eventTitle），不渲染描述
      return ""
    case "home_visited": {
      const head = [p.guardian ? `与${p.guardian}` : "", p.purpose || ""].filter(Boolean).join(" · ")
      if (p.summary) return head ? `${head} — ${p.summary}` : p.summary
      return head
    }
    case "comment": {
      const base = p.notes ?? p.summary ?? p.note ?? ""
      const names = (p.mentioned || []).map((m) => m.name).filter(Boolean)
      if (!names.length) return base
      return `${base}${base ? " · " : ""}涉及：${names.join("、")}`
    }
    case "exam": {
      // 没有科目/学期信息时返回空（标题行已有类型标注，"考试" 二字是噪音）
      const subjects = p.full_scores ? Object.keys(p.full_scores).map(subject).join("、") : ""
      return [p.term ? `${p.term}考试` : "", subjects].filter(Boolean).join(" · ")
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
// 手动记录暂时只开放家访；评语走独立入口。录入成绩走考试详情页和学生档案的成绩卡。
export function recordableEventOptions() {
  return RECORDABLE_EVENT_TYPES.map((o) => ({ value: o.value, label: t(o.label) }))
}

// ------------------------------------------------------------------ 错误处理

// 把后端/网络错误翻译成能指导下一步动作的话（错误可识别、可诊断、可恢复）
const ERROR_HINTS = [
  [/邮箱已(注册|存在)/i, "该邮箱已注册，可直接登录，或联系管理员重置密码"],
  [/手机号已(注册|存在)|already registered/i, "该手机号已被使用，请换一个号码"],
  [/at least 6 characters/i, "密码至少 6 位"],
  [/internal server error|proxy|bad gateway|service unavailable/i, "服务器暂时出了问题，请稍后重试"],
  [/登录已过期|not authenticated|未登录/i, "登录已过期，请重新登录"],
  [/failed to fetch|networkerror|网络/i, "连接不上服务器，请检查网络后重试"],
  [/not found/i, "找不到这条数据，它可能已经被删除"],
  [/已存在|already|duplicate|unique/i, "已经有重复的内容了，请换个名称"],
  [/仍有学生|still has/i, "这个班级里还有学生，请先给他们换个班级"],
  [/权限|forbidden|无权/i, "你没有执行这个操作的权限"],
  [/当前已关闭注册/i, "当前未开放注册，请联系管理员开通账号"],
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
