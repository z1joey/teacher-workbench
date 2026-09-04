import { createRouter, createWebHistory } from "vue-router"
import { getToken } from "./api"
import { loadMe, me } from "./auth"
import HomeView from "./views/HomeView.vue"
import LoginView from "./views/LoginView.vue"
import ProfileView from "./views/ProfileView.vue"
import RecordsView from "./views/RecordsView.vue"
import ClassesView from "./views/ClassesView.vue"
import ClassDetailView from "./views/ClassDetailView.vue"
import StudentsView from "./views/StudentsView.vue"
import StudentNewView from "./views/StudentNewView.vue"
import StudentDetailView from "./views/StudentDetailView.vue"
import ExamsView from "./views/ExamsView.vue"
import ExamNewView from "./views/ExamNewView.vue"
import ExamDetailView from "./views/ExamDetailView.vue"
import EventDetailView from "./views/EventDetailView.vue"
import AdminView from "./views/AdminView.vue"
import NotFoundView from "./views/NotFoundView.vue"

// Routes that only teachers (non-admin) may enter. Admin accounts get
// redirected away — they are developers, not classroom teachers.
const TEACHER_ROUTE_PREFIXES = [
  "/", "/profile", "/classes", "/students", "/exams", "/records",
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
    { path: "/profile", name: "profile", component: ProfileView, meta: { title: "个人中心" } },
    { path: "/records", name: "records", component: RecordsView, meta: { title: "跟进记录" } },
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
      meta: { title: "记录事件", parent: { label: "学生", to: "/students" } },
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
    { path: "/admin", name: "admin", component: AdminView, meta: { title: "开发者后台" } },
    { path: "/:pathMatch(.*)*", name: "notFound", component: NotFoundView, meta: { title: "页面不存在" } },
  ],
})

router.beforeEach(async (to) => {
  const loggedIn = !!getToken()
  if (!loggedIn && to.path !== "/login") return "/login"
  if (loggedIn && to.path === "/login") {
    if (!me.value) await loadMe()
    return me.value?.role === "admin" ? "/admin" : "/"
  }
  if (!me.value) await loadMe()
  if (!me.value) return // auth failed, api layer will bounce to /login

  // Admin gate #1 — teacher-role users who guess /admin get bounced.
  if (to.path.startsWith("/admin") && me.value.role !== "admin") return "/"

  // Admin gate #2 — admins are not teachers, so they get bounced away from
  // teacher workflow pages to their standalone dashboard.
  if (me.value.role === "admin" && isTeacherRoute(to.path)) return "/admin"
})
