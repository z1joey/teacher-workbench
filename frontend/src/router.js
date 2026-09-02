import { createRouter, createWebHistory } from "vue-router"
import { getToken } from "./api"
import { loadMe, me } from "./auth"
import HomeView from "./views/HomeView.vue"
import LoginView from "./views/LoginView.vue"
import ProfileView from "./views/ProfileView.vue"
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

// Routes that only teachers (non-admin) may enter. Admin accounts get
// redirected away — they are developers, not classroom teachers.
const TEACHER_ROUTE_PREFIXES = [
  "/", "/profile", "/classes", "/students", "/exams",
]

function isTeacherRoute(path) {
  // Match / or anything starting with the listed prefixes. Exact `/` is
  // special — it's always a teacher page.
  if (path === "/") return true
  return TEACHER_ROUTE_PREFIXES.slice(1).some((p) => path.startsWith(p))
}

export const router = createRouter({
  history: createWebHistory("/gao/"),
  routes: [
    { path: "/", component: HomeView },
    { path: "/login", component: LoginView },
    { path: "/profile", component: ProfileView },
    { path: "/classes", component: ClassesView },
    { path: "/classes/:id", component: ClassDetailView, props: true },
    { path: "/students", component: StudentsView },
    { path: "/students/new", component: StudentNewView },
    { path: "/students/:id", component: StudentDetailView, props: true },
    { path: "/students/:studentId/events/new", component: EventDetailView, props: (r) => ({ studentId: r.params.studentId, eventId: null }) },
    { path: "/students/:studentId/events/:eventId", component: EventDetailView, props: (r) => ({ studentId: r.params.studentId, eventId: r.params.eventId }) },
    { path: "/exams", component: ExamsView },
    { path: "/exams/new", component: ExamNewView },
    { path: "/exams/:id", component: ExamDetailView, props: true },
    { path: "/admin", component: AdminView },
  ],
})

router.beforeEach(async (to) => {
  const loggedIn = !!getToken()
  if (!loggedIn && to.path !== "/login") return "/login"
  if (loggedIn && to.path === "/login") {
    if (!me.value) await loadMe()
    return me.value?.is_admin ? "/admin" : "/"
  }
  if (!me.value) await loadMe()
  if (!me.value) return // auth failed, api layer will bounce to /login

  // Admin gate #1 — non-admins who guess /admin get bounced.
  if (to.path.startsWith("/admin") && !me.value.is_admin) return "/"

  // Admin gate #2 — admins are not teachers, so they get bounced away from
  // teacher workflow pages to their standalone dashboard.
  if (me.value.is_admin && isTeacherRoute(to.path)) return "/admin"
})
