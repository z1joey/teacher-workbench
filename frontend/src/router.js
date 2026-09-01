import { createRouter, createWebHistory } from "vue-router"
import { getToken } from "./api"
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

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", component: HomeView },
    { path: "/login", component: LoginView },
    { path: "/profile", component: ProfileView },
    { path: "/classes", component: ClassesView },
    { path: "/classes/:id", component: ClassDetailView, props: true },
    { path: "/students", component: StudentsView },
    { path: "/students/new", component: StudentNewView },
    { path: "/students/:id", component: StudentDetailView, props: true },
    { path: "/exams", component: ExamsView },
    { path: "/exams/new", component: ExamNewView },
    { path: "/exams/:id", component: ExamDetailView, props: true },
  ],
})

router.beforeEach((to) => {
  const loggedIn = !!getToken()
  if (!loggedIn && to.path !== "/login") return "/login"
  if (loggedIn && to.path === "/login") return "/"
})
