import { createRouter, createWebHistory } from "vue-router"
import { getToken, setToken } from "./api"
import { loadMe, me } from "./auth"
import HomeView from "./views/HomeView.vue"
import LoginView from "./views/LoginView.vue"
import SignupView from "./views/SignupView.vue"
import ProfileView from "./views/ProfileView.vue"
import HomeVisitsView from "./views/HomeVisitsView.vue"
import CommentNewView from "./views/CommentNewView.vue"
import GuardianDetailView from "./views/GuardianDetailView.vue"
import ClassesView from "./views/ClassesView.vue"
import ClassDetailView from "./views/ClassDetailView.vue"
import StudentsView from "./views/StudentsView.vue"
import StudentNewView from "./views/StudentNewView.vue"
import StudentDetailView from "./views/StudentDetailView.vue"
import ScoreNewView from "./views/ScoreNewView.vue"
import StudentSummariesView from "./views/StudentSummariesView.vue"
import ForgotPasswordView from "./views/ForgotPasswordView.vue"
import ExamsView from "./views/ExamsView.vue"
import ExamNewView from "./views/ExamNewView.vue"
import ExamDetailView from "./views/ExamDetailView.vue"
import EventDetailView from "./views/EventDetailView.vue"
import AdminOverviewView from "./views/admin/AdminOverviewView.vue"
import AdminAccountsView from "./views/admin/AdminAccountsView.vue"
import AdminFeedbackView from "./views/admin/AdminFeedbackView.vue"
import AdminSessionsView from "./views/admin/AdminSessionsView.vue"
import AdminInspectView from "./views/admin/AdminInspectView.vue"
import AdminSettingsView from "./views/admin/AdminSettingsView.vue"
import NotFoundView from "./views/NotFoundView.vue"

// Routes that only teachers (non-admin) may enter. Admin accounts get
// redirected away — they are developers, not classroom teachers.
const TEACHER_ROUTE_PREFIXES = [
  "/", "/profile", "/classes", "/students", "/exams", "/visits", "/comments", "/guardians",
]

function isTeacherRoute(path) {
  if (path === "/") return true
  return TEACHER_ROUTE_PREFIXES.slice(1).some((p) => path.startsWith(p))
}

// meta.title / meta.parent 驱动顶栏面包屑，保证每个页面位置可预期
export const router = createRouter({
  history: createWebHistory("/gao/"),
  routes: [
    { path: "/", name: "home", component: HomeView, meta: { title: "首页" } },
    { path: "/login", name: "login", component: LoginView, meta: { title: "登录" } },
    { path: "/signup", name: "signup", component: SignupView, meta: { title: "注册" } },
    { path: "/profile", name: "profile", component: ProfileView, meta: { title: "个人中心" } },
    // 数据管理并入个人中心；旧链接重定向
    { path: "/data", redirect: { name: "profile" } },
    {
      path: "/guardians/:id",
      name: "guardianDetail",
      component: GuardianDetailView,
      props: true,
      meta: { title: "监护人详情" },
    },
    // 旧链接直达新地址
    { path: "/records", redirect: { name: "events" } },
    { path: "/visits", name: "visits", component: HomeVisitsView, meta: { title: "家访" } },
    { path: "/classes", name: "classes", component: ClassesView, meta: { title: "班级" } },
    {
      path: "/classes/:id",
      name: "classDetail",
      component: ClassDetailView,
      props: true,
      meta: { title: "班级详情", parent: { label: "班级", to: "/classes" } },
    },
    { path: "/students", name: "students", component: StudentsView, meta: { title: "学生" } },
    {
      path: "/comments/:eventId",
      name: "commentEdit",
      component: CommentNewView,
      props: (r) => ({ eventId: r.params.eventId }),
      meta: { title: "记录" },
    },
    {
      path: "/students/:studentId/comments/new",
      name: "commentNew",
      component: CommentNewView,
      props: (r) => ({ studentId: r.params.studentId }),
      meta: { title: "添加记录", parent: { label: "学生", to: "/students" } },
    },
    {
      path: "/students/:studentId/scores/new",
      name: "scoreNew",
      component: ScoreNewView,
      props: (r) => ({ studentId: r.params.studentId }),
      meta: { title: "添加成绩", parent: { label: "学生", to: "/students" } },
    },
    {
      path: "/students/:studentId/comments/:eventId",
      name: "commentDetail",
      component: CommentNewView,
      props: (r) => ({ studentId: r.params.studentId, eventId: r.params.eventId }),
      meta: { title: "记录", parent: { label: "学生", to: "/students" } },
    },
    {
      path: "/students/:studentId/summaries",
      name: "studentSummaries",
      component: StudentSummariesView,
      props: (r) => ({ studentId: r.params.studentId }),
      meta: { title: "总结", parent: { label: "学生", to: "/students" } },
    },
    {
      path: "/students/new",
      name: "studentNew",
      component: StudentNewView,
      meta: { title: "添加学生", parent: { label: "学生", to: "/students" } },
    },
    {
      path: "/students/:id",
      name: "studentDetail",
      component: StudentDetailView,
      props: true,
      meta: { title: "学生档案", parent: { label: "学生", to: "/students" } },
    },
    {
      path: "/students/:studentId/events/new",
      name: "eventNew",
      component: EventDetailView,
      props: (r) => ({ studentId: r.params.studentId, eventId: null }),
      meta: { title: "记录家访", parent: { label: "学生", to: "/students" } },
    },
    {
      path: "/students/:studentId/events/:eventId",
      name: "eventDetail",
      component: EventDetailView,
      props: (r) => ({ studentId: r.params.studentId, eventId: r.params.eventId }),
      meta: { title: "编辑事件", parent: { label: "学生", to: "/students" } },
    },
    { path: "/exams", name: "exams", component: ExamsView, meta: { title: "考试" } },
    {
      path: "/exams/new",
      name: "examNew",
      component: ExamNewView,
      meta: { title: "新建考试", parent: { label: "考试", to: "/exams" } },
    },
    {
      path: "/exams/:id",
      name: "examDetail",
      component: ExamDetailView,
      props: true,
      meta: { title: "考试详情", parent: { label: "考试", to: "/exams" } },
    },
    { path: "/admin", name: "admin", component: AdminOverviewView, meta: { title: "概览" } },
    {
      path: "/admin/accounts",
      name: "adminAccounts",
      component: AdminAccountsView,
      meta: { title: "账号管理", parent: { label: "开发者后台", to: "/admin" } },
    },
    {
      path: "/admin/feedback",
      name: "adminFeedback",
      component: AdminFeedbackView,
      meta: { title: "用户反馈", parent: { label: "开发者后台", to: "/admin" } },
    },
    {
      path: "/admin/sessions",
      name: "adminSessions",
      component: AdminSessionsView,
      meta: { title: "活动会话", parent: { label: "开发者后台", to: "/admin" } },
    },
    {
      path: "/admin/inspect",
      name: "adminInspect",
      component: AdminInspectView,
      meta: { title: "数据探查", parent: { label: "开发者后台", to: "/admin" } },
    },
    {
      path: "/admin/settings",
      name: "adminSettings",
      component: AdminSettingsView,
      meta: { title: "站点设置", parent: { label: "开发者后台", to: "/admin" } },
    },
    { path: "/admin/danger", redirect: { name: "adminSettings" } },
    {
      path: "/forgot-password",
      name: "forgotPassword",
      component: ForgotPasswordView,
      meta: { title: "忘记密码" },
    },
    { path: "/:pathMatch(.*)*", name: "notFound", component: NotFoundView, meta: { title: "页面不存在" } },
  ],
})

// 免登录页 —— 路由守卫与 App 外壳（是否渲染导航）共用同一份口径
export const AUTH_PATHS = new Set(["/login", "/signup", "/forgot-password"])

router.beforeEach(async (to) => {
  const loggedIn = !!getToken()
  if (!loggedIn) {
    return AUTH_PATHS.has(to.path) ? true : "/login"
  }
  if (AUTH_PATHS.has(to.path)) {
    if (!me.value) await loadMe()
    if (!getToken()) return true
    // token 还在却拉不到账号（网络故障/会话失效）：清掉登录态留在登录页，
    // 否则会和下面的 return "/login" 互相重定向，页面白屏
    if (!me.value) {
      setToken(null)
      return true
    }
    return me.value.role === "admin" ? "/admin" : "/"
  }
  if (!me.value) await loadMe()
  if (!me.value) {
    setToken(null)
    return "/login"
  }

  // Admin gate #1 — teacher-role users who guess /admin get bounced.
  if (to.path.startsWith("/admin") && me.value.role !== "admin") return "/"

  // Admin gate #2 — admins are not teachers, so they get bounced away from
  // teacher workflow pages to their standalone dashboard.
  if (me.value.role === "admin" && isTeacherRoute(to.path)) return "/admin"
})
