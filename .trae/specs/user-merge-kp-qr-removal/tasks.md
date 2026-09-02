# 任务队列：Teacher/Student → User 合并 + KP/Q/QR/StudentWeakness 删除

**状态：** [Plan] 待审批  
**关联规格：** ./spec.md

---

## 总览映射

每条任务的完成条件都至少覆盖一条 AC。任务按依赖顺序编号，可串行推进。

| Task # | 标题 | 优先级 | 覆盖 AC |
|---|---|---|---|
| T1 | 🏗️ 后端 models.py：新建 `User` 表（`app_user`），删除 Teacher/Student/KP/Q/QR/StudentWeakness，重连所有 FK | high | AC-R1, AC-R5, AC-R6 |
| T2 | 🔒 后端 auth.py + deps.py：register/login 改双字段，守卫改 role 判定，AuthSession→user_id | high | AC-R2, AC-R3, AC-R4, AC-R7 |
| T3 | 🔀 后端路由迁移：students.py / classes.py / exams.py / dashboard.py / profile.py / admin.py / events.py 全部改 User FK，删除 weaknesses / failed-questions 路由 | high | AC-R5, AC-R6, AC-R8, AC-R9, AC-R10 |
| T4 | 🌱 seed.py：User 批量创建（3 教师 + 1 admin + 24 学生 + 密码），删除对 KP/Q/QR/weakness 的写入与推导 | high | AC-R14 |
| T5 | 🧪 TDD 测试：新建 10 个 pytest 用例覆盖 AC-R2/R3/R4/R7/R8/R9/R10 + /auth/me role 字段，确保 RED→GREEN | high | AC-R2…13（间接） |
| T6 | 🎨 前端 Login/Register & auth.js/router.js：identifier 输入 + role 选择 + role 守卫替换 is_admin | high | AC-U1, AC-R13 |
| T7 | 🧹 前端 StudentDetail / strings.js / ClassDetail / HomeView / ProfileView：移除 weaknesses + failed-questions 消费 | high | AC-U2, AC-U3 |
| T8 | 👩‍🏫 前端 AdminView：User 列表（role 列）+ PATCH 字段改 role / is_active / password | high | AC-R11 |
| T9 | 🚀 构建 + 启动验收：后端 pytest + vite build，uvicorn+vite 双开供用户验收 | high | AC-R12, AC-R13（UI 冒烟） |
| T10 | 📄 文档更新：CODE_WIKI.md + README.md 新 ER 图、新表集合、角色体系说明、已上线数据迁移提示 | medium | AC-U3（文档端） |

---

## Task 1: 🏗️ models.py 新建 User 并删除旧表 + FK 重连

**Scope**：仅修改 [models.py](file:///Users/joey/Projects/teacher-workbench/backend/app/models.py) 单一文件。  
**Status**：pending

### 本地 Test Requirements（可由 T5 pytest 间接覆盖，此处做结构性校验）

- **TR-R1**（Rule）：`app_user` 表 columns 包含 `role` 且不包含 `is_admin`。证据：`python -c "print([c.name for c in Base.metadata.tables['app_user'].columns])"` 输出。
- **TR-R2**（Rule）：`Base.metadata.tables` 中键 `teacher` / `student` / `knowledge_point` / `question` / `question_response` / `student_weakness` 均不存在。证据：同样 print。
- **TR-R3**（Rule）：所有原指向 teacher/student 的外键列（homeroom_teacher_id、Enrollment.student_id、ExamResult.student_id/entered_by、StudentEvent.actor_teacher_id/student_id、HomeVisit.teacher_id/student_id、AuthSession.teacher_id → 改 user_id）都 `foreign_keys` 指向 `app_user.id`。证据：打印各模型列 `ForeignKey`。

### 实现提示

- User 用 `__tablename__ = "app_user"`（Postgres 兼容）。
- role 字段使用 `CheckConstraint("role IN ('teacher','student','admin')")`（跨 DB 以 text 方式）。
- 凭证 CHECK：`CheckConstraint("phone IS NOT NULL OR email IS NOT NULL")`。
- 唯一性：`UniqueConstraint("phone", name="uq_user_phone")`（非 NULL 才会判冲突，符合 SQLite / PG 语义）；email 同理。

### 依赖

无（最先改模型，路由随后才能通过 import 编译）。

---

## Task 2: 🔒 auth.py + deps.py 改造

**Scope**：修改 [routers/auth.py](file:///Users/joey/Projects/teacher-workbench/backend/app/routers/auth.py)、[deps.py](file:///Users/joey/Projects/teacher-workbench/backend/app/deps.py)。  
**Status**：pending

### 本地 TRs

- **TR-R1**（Rule）：`POST /api/auth/register` 当 role="admin" 返回 400。
- **TR-R2**（Rule）：`POST /api/auth/register` 当 phone="" 且 email="" 返回 400 "至少必填一项"。
- **TR-R3**（Rule）：`POST /api/auth/login` 支持 `identifier` 为注册过的 email → 登录成功；错误密码 → 401。
- **TR-R4**（Rule）：`get_admin_user` 对 role="teacher" 返回 403；对 role="admin" 返回 User。

### 实现提示

- `user_out(u)` 响应 schema 删除 `is_admin`，新增 `role`。
- `create_session(db, user_id)` 重命名参数。
- `get_current_teacher` 守卫逻辑：在 `get_current_user` 之上检查 `role not in ("teacher","admin") → 403`。

### 依赖

T1 完成。

---

## Task 3: 🔀 所有路由迁移（students / classes / exams / dashboard / profile / admin / events / misc）

**Scope**：7 个路由文件 + [events.py](file:///Users/joey/Projects/teacher-workbench/backend/app/events.py)。  
**Status**：pending

### 本地 TRs

- **TR-R1**（Rule）：grep 所有 `routers/*.py` 的非注释 import：`Teacher / Student / KnowledgePoint / Question / QuestionResponse / StudentWeakness` → 0 处。
- **TR-R2**（Rule）：`GET /students/{id}/weaknesses` 实际响应 404（路由定义删除）。
- **TR-R3**（Rule）：`GET /students/{id}/failed-questions` 404。
- **TR-R4**（Rule）：teacher role 用户 `POST /classes` 201；student role 同请求 → 403（由 deps 守卫保证）。
- **TR-R5**（Rule）：`/admin/stats` 返回 `users_total`、`users_role_counts` 等新统计键，不再有 teachers_total/admins 旧键。

### 依赖

T1、T2。

---

## Task 4: 🌱 seed.py 改造

**Scope**：[seed.py](file:///Users/joey/Projects/teacher-workbench/backend/app/seed.py) 全部重写用户生成段；删除 KP/Q/QR/weakness 部分。  
**Status**：pending

### 本地 TRs

- **TR-R1**（Rule）：运行 `seed()` 后 `User.role` 统计：admin=1、teacher=3、student=24。
- **TR-R2**（Rule）：每个 role=student 都有 `password_hash`（学生登录可用）。
- **TR-R3**（Rule）：Enrollment 行 student_id FK 实际存在于 User.role=student 的 id 中（无参照不一致）。
- **TR-R4**（Rule）：无 `question_response` 相关写入（grep seed.py → 0 处）。

### 依赖

T1、T3。

---

## Task 5: 🧪 TDD pytest 套件（10 个+用例）

**Scope**：新建 `backend/tests/test_user_merge.py`；修改 `test_homevisit_migration.py` 适配新 User 模型。  
**Status**：pending

### 用例清单

1. `test_register_requires_phone_or_email → 400`
2. `test_register_role_admin_rejected → 400`
3. `test_register_student_role_ok → 201, role=student`
4. `test_login_with_phone → 200, me.role`
5. `test_login_with_email → 200`
6. `test_login_wrong_password_401`
7. `test_me_response_has_role_no_is_admin`
8. `test_admin_guard_blocks_teacher → /admin/stats 403`
9. `test_admin_student_route_forbidden → student token POST /classes 403`
10. `test_weaknesses_and_failed_questions_routes_removed → 404 × 2`
11. *（修改旧用例）* test_homevisit_migration 全部改用 role=teacher 用户登录。

### 本地 TRs

- **TR-R1**（Rule）：RED 阶段（代码未实现时）用例按预期失败（assert failure 为"缺少对应属性"或 405/404/响应字段缺失等精准原因）。记录 RED 原因后实现。
- **TR-R2**（Rule）：GREEN 阶段 `pytest backend/tests -q` 全部通过 ≥ 14/14（旧 4 + 新 10），exit 0，无 runtime error。

### 依赖

T1–T4（可与 T3/T4 迭代推进：RED 先写好 → 修 T3/T4 → 达到 GREEN）。

---

## Task 6: 🎨 前端登录 / 注册 + 鉴权状态

**Scope**：`LoginView.vue`、`auth.js`、`router.js`、`App.vue`（导航）。  
**Status**：pending

### 本地 TRs

- **TR-R1**（Rule）：登录表单 `<input>` 改为 placeholder `手机号 / 邮箱`；提交字段 `identifier`（不再是 `phone`）。
- **TR-R2**（Rule）：注册 Tab 有 radio role 选择（教师 / 学生），admin 不出现。
- **TR-R3**（Rule）：注册表单提交前置校验"至少填一个 phone 或 email"，否则禁用按钮 + 红字提示。
- **TR-R4**（Rule）：auth.js `me.value.is_admin` 所有引用替换成 `me.value.role === 'admin'`；教师工作流判定 `role in ['teacher','admin']`。
- **TR-U1**（Rubric）：表单可用性 0-2，阈值 ≥1（AC-U1 同款）。证据：运行截图。

### 依赖

后端 T2–T3 完成后前端才能发请求成功。

---

## Task 7: 🧹 前端移除 weaknesses / failed-questions 卡片

**Scope**：`StudentDetailView.vue`、`strings.js`、`style.css`、`ClassDetailView.vue` / `HomeView.vue` / `ProfileView.vue`。  
**Status**：pending

### 本地 TRs

- **TR-R1**（Rule）：StudentDetailView 不再发起 GET `…/weaknesses` 和 GET `…/failed-questions`。
- **TR-R2**（Rule）：视图 DOM 无 weaknesses / drilldown（错题）卡片元素。
- **TR-R3**（Rule）：strings.js / style.css 删除对应条目（或留空不报错）。
- **TR-U2**（Rubric）：StudentDetail 布局完整性 0-2，阈值 ≥1。

### 依赖

T3（后端路由下线）。

---

## Task 8: 👩‍🏫 AdminView 用户管理重构

**Scope**：`AdminView.vue`（管理后台用户列表）。  
**Status**：pending

### 本地 TRs

- **TR-R1**（Rule）：调用 `GET /admin/users`（或后端新 `/admin/users` 替代 `/admin/teachers`）返回含 `role` 字段列表。
- **TR-R2**（Rule）：PATCH 用户表单支持 `role` 下拉/切换（teacher/student/admin，**管理员可设 admin**）。
- **TR-R3**（Rule）：PATCH 删除用户时不可删自己（同旧逻辑）。
- **TR-R4**（Rule）：重置密码后用新密码能登录（手动冒烟验证）。

### 依赖

T3（新 `/admin/users` 接口）。

---

## Task 9: 🚀 构建 & 启动验收环境

**Scope**：命令行工具调用（不写文件）。  
**Status**：pending

### 本地 TRs

- **TR-R1**（Rule）：`cd backend; ./.venv/bin/python -m pytest tests -q` → all pass。
- **TR-R2**（Rule）：`cd frontend; npm run build`（或 pnpm / 项目默认）→ exit 0。
- **TR-R3**（Rule）：uvicorn 启动 + 前端 dev server 启动；`/login`、`/students/:id`、`/admin` 页面均 200 可打开。
- **TR-U3**（Rubric）：清理彻底度 0-2，阈值 ≥1。

### 依赖

T1–T8 全部 completed。

---

## Task 10: 📄 文档更新

**Scope**：`CODE_WIKI.md` + `README.md`。  
**Status**：pending

### 本地 TRs

- **TR-R1**（Rule）：ER 图中 `Teacher/Student/HomeVisit/KnowledgePoint/Question/QuestionResponse/StudentWeakness` 不出现独立实体。
- **TR-R2**（Rule）：表列表以 `User (app_user)` 开头，role 字段说明，删除 is_admin 描述。
- **TR-R3**（Rule）：API 表格移除 weaknesses / failed-questions / 逐题作答条目，Auth 段新增 role/identifier 说明。
- **TR-R4**（Rule）：运行说明 / Demo 账号列表改为新 seed role 分布（1 管理员 + 3 教师 + 24 学生默认密码）。

### 依赖

T1–T9。
