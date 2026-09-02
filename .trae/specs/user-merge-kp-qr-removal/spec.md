# 规格说明书：Teacher/Student 合并为 User，删除 KnowledgePoint / Question / QuestionResponse

**Natural Language：** 中文（简体）
**规格版本：** v1.0（2026-09-02）
**状态：** \[Specify] 待用户审批

***

## 0. 问题陈述

当前数据库将「教师」与「学生」设计为两张独立表（Teacher / Student），学生无注册/登录能力；同时考试子系统包含 知识点（KnowledgePoint）/ 题目（Question）/ 逐题作答（QuestionResponse）三张表，外加薄弱项派生表 StudentWeakness。该架构存在以下痛点：

1. **Teacher/Student 分裂**：两者共享「姓名 / 联系方式 / 密码凭证」等用户字段，但分表导致鉴权、会话、管理后台必须双轨维护；学生无法通过手机号或邮箱自行注册登录。
2. **is\_admin 字段冗余**：Teacher 表用布尔 is\_admin 标记管理员，不符合 Role Base 设计，也无法扩展学生角色。
3. **KP/Q/QR 体系过重**：题目录入、逐题作答、薄弱点推导占用大量代码路由与前端界面，但实际核心业务可以只保留考试（Exam）+ 考试科目（ExamSubject）+ 科目成绩（ExamResult）。

## 1. 用户 / 利益相关方与目标

| 角色                | 目标                                        |
| ----------------- | ----------------------------------------- |
| 教师（teacher role）  | 用手机或邮箱注册/登录，管理班级、考试、学生档案与家访事件             |
| 学生（student role）  | 用手机或邮箱注册/登录，查看个人基础信息（最小可用态）               |
| 系统管理员（admin role） | 管理用户（停启用/重置密码/删用户）、会话、查看所有表统计、初始化 / 重置数据库 |
| 维护者（Developer）    | 代码体量更集中、表更少、文档与实际一致                       |

## 2. 非目标（Out of Scope）

- 不做细粒度角色权限（如年级主任、学科组长）。

- 不做 Access / Refresh Token 分离（沿用 AuthSession Bearer 会话）。

- 不做学生端新功能模块（如提交作业、在线做题）。

- 不做数据迁移工具（用 Alembic 仍是 TODO，沿用 seed 重跑模式即可）。

***

## 3. 功能需求（Functional Requirements）

### 3.1 用户合并（Teacher + Student → User）

- FR-USER-1：新增 ORM 类 `User`，表名 `user`（或 PostgreSQL 友好别名 `app_user`，避免关键字冲突）。

- FR-USER-2：User 列包含：`id`、`role`（String(20)，允许值 `"teacher"` / `"student"` / `"admin"`）、`name`、`phone`、`email`、`password_hash`、`is_active`、`created_at`、`updated_at`。

- FR-USER-3：**角色字段合法性**：数据库 CHECK 约束或应用层验证 `role ∈ {teacher, student, admin}`；`admin` 不是注册接口可选值，只允许 seed 或管理员 PATCH 设置（参见 FR-AUTH-6）。

- FR-USER-4：**凭证校验**：`phone` 和 `email` 至少其一非空（CHECK 约束 + 接口 400 防御）。两者可同时有值。

- FR-USER-5：**唯一约束**：`phone` 全局唯一（非空时）；`email` 全局唯一（非空时）。

- FR-USER-6：**删除旧布尔字段**：不再有 `is_admin` 列（FR-USER-3 用 role 替代）。

- FR-USER-7：**原 Student 专属字段合并**：`admission_no`（学籍号）、`gender`、`birth_date`、`guardian_name`、`guardian_phone`、`address`、`status`（"active" / "inactive"）作为 User 可空列，role=student 时可写；role=teacher 时可为空。

- FR-USER-8：**原 Teacher 专属字段合并**：`subject`（任教学科）可空，role=teacher 时可写。

- FR-USER-9：**所有外键重建**：原来指向 `teacher.id` 或 `student.id` 的 FK 都改为指向 `user.id`（Class.homeroom\_teacher\_id、Enrollment.student\_id、ExamResult.student\_id + entered\_by、HomeVisit.student\_id + teacher\_id、StudentEvent.student\_id + actor\_teacher\_id、AuthSession.teacher\_id → user\_id）。

- FR-USER-10：**删除旧表**：Teacher、Student ORM 类及对应表全部移除（`teacher`、`student` 表）。HomeVisit 继续按上次迁移后状态（仍保留 ORM 类但不读写）。

### 3.2 认证 / 鉴权

- FR-AUTH-1：`POST /api/auth/register` 请求体增加 `role`（允许值 `"teacher"` / `"student"`，默认 `"teacher"`）；禁止传 `"admin"`（400）。

- FR-AUTH-2：`RegisterIn` 字段中 `phone` 可空、`email` 可空，但二者至少填一项（否则 400）。

- FR-AUTH-3：`POST /api/auth/login` 接收 `identifier`（替代 `phone`，允许 phone 或 email 任一，后端分别匹配 User.phone 与 User.email）+ `password`。仅 `is_active=True` 的用户可登录。

- FR-AUTH-4：`get_current_user`（原名 `get_current_teacher`）依赖：通过 AuthSession → user.id 加载 User 对象。Teacher / admin 专用接口在此基础上加守卫。

- FR-AUTH-5：`get_current_teacher` 守卫：当前用户 `role ∈ {"teacher", "admin"}`，否则 403。原所有教师工作流（class/exam/student/事件编辑）使用此守卫。

- FR-AUTH-6：`get_admin_user` 守卫：当前用户 `role == "admin"`，否则 403。仅 `/admin/*` 路由使用。

- FR-AUTH-7：`AuthSession.teacher_id` 列改名 `user_id`（FK → `user.id`），所有读写同步改动。

- FR-AUTH-8：`/auth/me` 响应包含 `id / name / phone / email / role / subject / is_active`；删除 `is_admin` 字段。前端通过 `role==="admin"` 判断管理员身份。

### 3.3 删除 KP / Question / QuestionResponse

- FR-DROP-1：移除 ORM 类 `KnowledgePoint`、`Question`、`QuestionResponse`、`StudentWeakness`。

- FR-DROP-2：后端删除依赖这些模型的 API：`GET /students/{id}/weaknesses`、`GET /students/{id}/failed-questions`、Exams 路由中所有题目录入/逐题批改接口（若存在）。

- FR-DROP-3：`students.py` 删除学生时的"证据检查"只保留 `has_results` + `has_home_visits`（移除 `has_responses`、`has_weaknesses`）。

- FR-DROP-4：`admin.ALL_MODELS` 列表移除 KP/Q/QR/StudentWeakness；教师计数改为 `db.query(User).filter(User.role=="teacher").count()`，管理员计数改为 `filter(User.role=="admin").count()`。

- FR-DROP-5：Exam 与 ExamSubject 完全保留；ExamResult 完全保留（科目级分数）；ExamsView / ExamDetailView 的"录入成绩" UI 保持在科目级。

### 3.4 前端 UI 同步

- FR-UI-1：LoginView — 登录表单将"手机号"输入改为"账号（手机号/邮箱）"，`identifier` 替代原 `phone`。

- FR-UI-2：RegisterView（LoginView 内 Tab 或切换）— 增加 **role 单选**（教师/学生，默认教师；admin 不显示）；Phone / Email 输入均显示，并在表单层面校验"至少填一项"；错误提示 409（该手机或邮箱已注册）。

- FR-UI-3：auth.js `me` 状态改用 `role` 判断（`role==="admin"` 为管理员；`role==="teacher"` 为教师），替换 `is_admin` / 教师身份判定位置（router.js、App.vue 导航）。

- FR-UI-4：StudentDetailView — 删除"薄弱项汇总"卡片与"错题明细"卡片（对应后端接口已下线）。

- FR-UI-5：ClassesView / HomeView / ProfileView / strings.js — 移除薄弱项/错题文案引用，空态文案回退为"无考试成绩/事件"级别。

- FR-UI-6：AdminView — 用户列表由"教师列表"改成"所有用户列表（分页？可先全部）"，列含：name / role / phone / email / subject（教师）/ admission\_no（学生）/ is\_active；编辑面板 PATCH 字段：`is_active / role / password`（role 允许 admin，防止锁死）；新增用户按钮（管理员批量开户）。

- FR-UI-7：导航栏根据 role 显示菜单——学生登录只显示"个人资料"与"退出登录"，教师显示完整菜单，管理员跳转到后台。

### 3.5 Seed / 管理后台

- FR-SEED-1：`seed()` 用 User 批量创建 3 位老师 + 1 位管理员（`role="admin"`）+ 24 位学生；保留原班级/考试/成绩数据。

- FR-SEED-2：学生用户必须设置 `password_hash`（学生登录可用）；默认密码沿用教师规则或 `123456`（同 seed 中其他用户）。

- FR-SEED-3：`/admin/db/reset` 功能不变；drop\_all/create\_all 基于新 metadata。

***

## 4. 非功能需求

- NFR-1：向后兼容优先——现有教师账号登录手机号匹配到 phone 字段依旧可用（登录 identifier 逻辑要做双向 match：phone == identifier OR email == identifier）。

- NFR-2：后端所有路由 **import 不遗留** Teacher / Student / KP / Q / QR 类。

- NFR-3：前端 `pnpm/npm build` 不报错。

- NFR-4：pytest 现有 4 个 homevisit 迁移测试改造成新 User 模型后继续通过；新增 6+ 个 User 合并相关测试用例，通过率 100%。

- NFR-5：变更需 TDD（见 TRs）。

- NFR-6：启动 uvicorn + vite 预览后等待用户人工验收。

## 5. 约束、依赖、假设、开放问题

- **假设 A**：删除 KP/Q/QR 后，不重建错题/薄弱模块。若以后需要，再以科目级分析补充。

- **假设 B**：Student.updated\_at 保留在 User.updated\_at 上；teacher role 的 updated\_at 也会同步更新。

- **约束 C**：`user` 表名在 PostgreSQL 是关键字——若用 Postgres 需改 `__tablename__ = "app_user"`；SQLite 下 "user" 可接受。实现时统一用 `app_user` 以免部署报错。

- **开放问题（用户可审批默认）**：\
  ① 学生登录后默认跳转到哪个页面？→ **默认 /profile**（个人资料、基础信息、最近自己的事件时间线）。\
  ② 注册成功后默认是否生成 session（沿用现状）并登录？→ **是**（现行为：register → 201 返回 token）。\
  ③ 管理后台是否允许管理员直接"设置 role=admin"？→ **是**（防止锁死；但 get\_admin\_user 守卫仍存在）。

***

## 6. 验收标准（Acceptance Criteria）

### 6.1 Rule 类（可客观验证，通过 / 不通过）

| ID     | 规则                                                                                                                                                                                               | 证据来源                                                                                           |
| ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------- |
| AC-R1  | User 表列集合正确：含 id/role/name/phone/email/password\_hash/is\_active/created\_at/updated\_at/admission\_no/gender/birth\_date/guardian\_name/guardian\_phone/address/status/subject；**不含** is\_admin | models.py 代码审查 + `Base.metadata.tables["app_user"].columns` 运行时列打印                             |
| AC-R2  | role 合法值仅 {teacher, student, admin}；注册接口传 admin → 400；传 teacher/student → 201                                                                                                                    | pytest test\_register\_role\_admin\_rejected / test\_register\_student\_role\_ok               |
| AC-R3  | 注册请求 phone 空且 email 空 → 400 "手机号或邮箱至少必填一项"                                                                                                                                                       | pytest test\_register\_requires\_phone\_or\_email                                              |
| AC-R4  | 登录可接受 phone 也可接受 email；错误密码 → 401                                                                                                                                                                | pytest test\_login\_with\_phone / test\_login\_with\_email / test\_login\_wrong\_password\_401 |
| AC-R5  | 旧 Teacher 表与 Student 表 ORM 类删除；项目 grep 仅在文档/注释中出现                                                                                                                                                | grep 统计（非注释 0 处）                                                                               |
| AC-R6  | KP/Q/QR/StudentWeakness ORM 类与对应路由函数 0 处引用                                                                                                                                                       | grep 统计 + routers import 审查                                                                    |
| AC-R7  | 路由守卫：`/admin/stats` 用 teacher role 用户访问 → 403；admin 访问 → 200                                                                                                                                     | pytest test\_admin\_guard\_blocks\_teacher                                                     |
| AC-R8  | 教师工作流：创建班级/学生/考试均正常（teacher role token）；学生 role 尝试 POST /classes → 403                                                                                                                           | pytest test\_teacher\_workflow\_vs\_student\_role\_forbidden                                   |
| AC-R9  | `GET /students/{id}/weaknesses` 返回 404（路由已移除）                                                                                                                                                    | pytest 或 curl                                                                                  |
| AC-R10 | `GET /students/{id}/failed-questions` 返回 404                                                                                                                                                     | 同上                                                                                             |
| AC-R11 | AdminView 用户列表前端可打开，可切换 is\_active、可重置密码、可直接删除非自己用户                                                                                                                                              | UI 冒烟（uvicorn 启动后页面交互）                                                                         |
| AC-R12 | 前端 `vite build`（或项目默认 build）exit 0                                                                                                                                                               | CLI exit code                                                                                  |
| AC-R13 | 后端 uvicorn 启动无异常，`GET /api/auth/me` 返回含 role 字段无 is\_admin                                                                                                                                       | curl                                                                                           |
| AC-R14 | Seed 可重跑：seed 后至少有 1 admin、3 teacher、24 student                                                                                                                                                  | 查库 count(User.role)                                                                            |

### 6.2 Rubric 类（评分制，必须达到阈值）

| ID    | 维度                                    | 0 分            | 1 分（阈值）                                    | 2 分（优秀）                 | 阈值 | 证据来源                |
| ----- | ------------------------------------- | -------------- | ------------------------------------------ | ----------------------- | -- | ------------------- |
| AC-U1 | 前端登录/注册表单可用性（错误提示 + role 切换 + 最少一项校验） | 缺少校验或报错不友好     | 可用但文案略糙                                    | 手机/邮箱提示明显、409 冲突正确绑定到输入 | ≥1 | UI 验收截图 + 前端 vue 代码 |
| AC-U2 | StudentDetail 界面精简一致性（移除薄弱/错题后布局不失调）  | 大面积空白 / 错位     | 功能正常但空态文案缺                                 | 空态文案合理、信息密度与改版前相当       | ≥1 | UI 验收截图             |
| AC-U3 | 代码清理彻底度（import、路由、seed、常量）            | 仍有 dead import | 基本干净，但 strings.js 或 style.css 留 1\~2 处无用条目 | 全栈 grep 0 dead 代码残留     | ≥1 | grep 报告 + 代码审查      |

