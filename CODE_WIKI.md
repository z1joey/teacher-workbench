# Teacher Workbench — Code Wiki

> 本文档全面介绍 Teacher Workbench（高老师工作台）项目的**整体架构、模块职责、关键类与函数、依赖关系以及运行指南**，作为开发者快速上手与日常维护的参考手册。

***

## 目录

1. [项目概览](#1-项目概览)
2. [技术栈总览](#2-技术栈总览)
3. [项目目录结构](#3-项目目录结构)
4. [后端架构（FastAPI / SQLAlchemy）](#4-后端架构fastapi--sqlalchemy)

   - 4.1 [核心模块](#41-核心模块)

   - 4.2 [数据模型（14 张表）](#42-数据模型14-张表)

   - 4.3 [API 路由详解](#43-api-路由详解)

   - 4.4 [关键函数与类](#44-关键函数与类)
5. [前端架构（Vue 3 / Vite）](#5-前端架构vue-3--vite)

   - 5.1 [核心模块](#51-核心模块)

   - 5.2 [路由与守卫](#52-路由与守卫)

   - 5.3 [视图组件](#53-视图组件)

   - 5.4 [通用组件](#54-通用组件)

   - 5.5 [样式系统](#55-样式系统)
6. [依赖关系图](#6-依赖关系图)
7. [事件驱动与时间线机制](#7-事件驱动与时间线机制)
8. [安全与鉴权](#8-安全与鉴权)
9. [运行指南](#9-运行指南)

   - 9.1 [本地开发模式](#91-本地开发模式)

   - 9.2 [Docker 模式](#92-docker-模式)

   - 9.3 [演示账号](#93-演示账号)
10. [设计亮点与关键决策](#10-设计亮点与关键决策)
11. [已知限制与后续 TODO](#11-已知限制与后续-todo)

***

## 1. 项目概览

**Teacher Workbench** 是一套面向中小学教师的教学管理工作台 MVP 系统，核心能力包括：

| 功能模块            | 说明                                  |
| --------------- | ----------------------------------- |
| 👨‍🏫 **教师工作台** | 首页仪表盘（统计 / 考试倒计时 / 最新动态 / 待跟进）      |
| 🧑‍🎓 **学生档案**  | 基本信息、监护人、班级归属（带时间维度）、成绩趋势、薄弱项、错题明细  |
| 📝 **事件记录**     | 家访、谈心、辅导、家长沟通、教师备注等自定义事件，统一沉淀到右侧时间线 |
| 📊 **班级管理**     | 新建/编辑/删除班级，班级平均分趋势图，学生名单            |
| 🧪 **考试管理**     | 新建考试（含多科目）、全校平均分趋势、各班对比、按考试当日班级归属统计 |
| 🔧 **开发者后台**    | 仅管理员可见：数据库概览、教师账号管理、会话管理、数据探查、危险操作  |

项目采用 **前后端分离 + 管理员/教师双角色隔离** 架构。管理员不是教师——管理员登录后进入独立的 `/admin` 后台，不访问学生/班级/考试等教学工作流页面。

***

## 2. 技术栈总览

| 层级      | 技术选型                                                | 版本/说明                            |
| ------- | --------------------------------------------------- | -------------------------------- |
| **前端**  | Vue 3 + Vue Router 4 + Vite 6                       | 纯 CSS，零 UI 框架；所有图标为内联 SVG 手绘     |
| **后端**  | Python 3.14 + FastAPI + SQLAlchemy 2.0 + Pydantic 2 | 无额外 ORM 封装，直接使用 SQLAlchemy 查询构造器 |
| **数据库** | PostgreSQL 17（生产 Docker） / SQLite（本地开发回退）           | 半结构化数据落在 PostgreSQL `JSONB`      |
| **认证**  | PBKDF2-HMAC-SHA256（密码哈希） + Bearer Token（DB 会话）      | 20 万次迭代 + 每用户 16 字节盐值            |
| **部署**  | Docker Compose（3 容器：db / backend / frontend）        | Frontend 用 nginx 托管并反向代理 `/api`  |

***

## 3. 项目目录结构

```
teacher-workbench/
├── backend/                          # FastAPI 后端
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                   # FastAPI 应用入口：建表、CORS、路由装配
│   │   ├── database.py               # 引擎/Session/Base 声明；DATABASE_URL 驱动
│   │   ├── models.py                 # 14 张表 ORM 映射（SQLAlchemy 2.0 声明式）
│   │   ├── events.py                 # add_event() — 同事务写时间线
│   │   ├── security.py               # PBKDF2 密码 / 随机 Token 生成
│   │   ├── deps.py                   # FastAPI 依赖：get_current_teacher / get_admin_teacher
│   │   ├── seed.py                   # 演示数据脚本（DROP → CREATE → 灌数据）
│   │   └── routers/
│   │       ├── __init__.py           # 空
│   │       ├── auth.py               # 注册 / 登录 / 登出 / me
│   │       ├── students.py           # 学生 CRUD、时间线、薄弱项、错题、事件、成绩更正
│   │       ├── classes.py            # 班级 CRUD、班级平均分趋势
│   │       ├── exams.py              # 考试 CRUD、全校趋势、各科平均分
│   │       ├── dashboard.py          # 首页聚合接口
│   │       ├── profile.py            # 教师个人中心 / 教学足迹
│   │       ├── misc.py               # 教师列表（供下拉选择）
│   │       └── admin.py              # 管理员专用：统计、账号、会话、探查、重置
│   ├── Dockerfile                    # 多阶段 Python slim 构建
│   └── requirements.txt              # fastapi / uvicorn / sqlalchemy / pydantic / psycopg
│
├── frontend/                         # Vue 3 前端
│   ├── src/
│   │   ├── main.js                   # createApp + 挂载 router
│   │   ├── App.vue                   # 顶栏（管理员/教师双样式）+ router-view
│   │   ├── router.js                 # 路由表 + 双角色路由守卫
│   │   ├── api.js                    # fetch 封装：Token 注入、401 跳转、错误归一化
│   │   ├── auth.js                   # me ref 响应式状态 + loadMe()
│   │   ├── strings.js                # 中文词典 t() + 枚举映射/取色/事件描述
│   │   ├── style.css                 # 全局主题（黑板绿 + 粉笔 + 红笔）
│   │   ├── components/
│   │   │   ├── Icon.vue              # 内联 SVG 图标集（15 个手绘图标）
│   │   │   ├── LineChart.vue         # 纯 SVG 折线图（带 hover tooltip）
│   │   │   └── Timeline.vue          # 时间线列表（带颜色圆点 + 图标）
│   │   └── views/
│   │       ├── LoginView.vue         # 登录/注册 Tab
│   │       ├── HomeView.vue          # 教师首页仪表盘
│   │       ├── ProfileView.vue       # 个人中心
│   │       ├── ClassesView.vue       # 班级列表 + 新建弹窗
│   │       ├── ClassDetailView.vue   # 班级详情（趋势 + 名单 + 平均）
│   │       ├── StudentsView.vue      # 学生列表（搜索）
│   │       ├── StudentNewView.vue    # 添加学生
│   │       ├── StudentDetailView.vue # 学生工作台（成绩/薄弱/错题/事件/时间线）
│   │       ├── EventDetailView.vue   # 事件记录（新建 / 编辑弹窗）
│   │       ├── ExamsView.vue         # 考试列表
│   │       ├── ExamNewView.vue       # 新建考试
│   │       ├── ExamDetailView.vue    # 考试平均分（全校+各班）
│   │       └── AdminView.vue         # 开发者后台（5 个分区）
│   ├── Dockerfile                    # 多阶段：node 构建 → nginx 托管 + /api 代理
│   ├── vite.config.js                # base=/gao/ + 开发代理到 8000/8001
│   ├── index.html                    # 入口 HTML
│   ├── package.json                  # vue 3.5 / vue-router 4.5 / vite 6
│   └── package-lock.json
│
├── docker-compose.yml                # 3 服务编排（db/backend/frontend + 健康检查链）
├── .env.example                      # PostgreSQL 凭据模板
├── .gitignore / .dockerignore
└── README.md                         # 使用手册（中文）
```

***

## 4. 后端架构（FastAPI / SQLAlchemy）

### 4.1 核心模块

#### `main.py` — 应用装配

[main.py](file:///Users/joey/Projects/teacher-workbench/backend/app/main.py)

- `Base.metadata.create_all(bind=engine)`：启动时幂等建表

- `FastAPI(title="Teacher Workbench API", version="0.2.0")`

- CORS：允许所有来源（演示配置）

- 路由挂载策略：

  - `/api/auth/*` 与 `/api/admin/*` **独立挂载**（admin 路由自己内部再鉴权）

  - 其余业务路由统一注入 `Depends(get_current_teacher)`

#### `database.py` — 数据库连接

[database.py](file:///Users/joey/Projects/teacher-workbench/backend/app/database.py)

| 变量 / 函数        | 职责                                                                   |
| -------------- | -------------------------------------------------------------------- |
| `DATABASE_URL` | `os.environ.get("DATABASE_URL", "sqlite:///./teacher_workbench.db")` |
| `engine`       | `create_engine()`；SQLite 时加 `check_same_thread=False`                |
| `SessionLocal` | `sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)` |
| `Base`         | `DeclarativeBase` — 所有 ORM 模型的基类                                     |
| `get_db()`     | FastAPI generator 依赖：yield 一个 Session，finally 关闭                     |

> **PostgreSQL/SQLite 双兼容策略**：`models.py` 中通过 `JSONType = JSON().with_variant(JSONB(), "postgresql")` 声明 JSON 列，自动适配两种数据库。

#### `security.py` — 密码与令牌

[security.py](file:///Users/joey/Projects/teacher-workbench/backend/app/security.py)

```python
hash_password(password, salt=None) -> str   # PBKDF2 200k rounds; 格式 "{salt_hex}${digest_hex}"
verify_password(password, stored) -> bool   # 用 secrets.compare_digest 防时序攻击
new_token() -> str                          # secrets.token_hex(32) — 64 字符十六进制
```

#### `deps.py` — FastAPI 鉴权依赖

[deps.py](file:///Users/joey/Projects/teacher-workbench/backend/app/deps.py)

| 函数                                                 | 职责                                                                                        |
| -------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| `get_current_teacher(credentials, db)` → `Teacher` | 从 `Authorization: Bearer <token>` 查 `auth_session` → `teacher`；401 若未登录 / Token 过期 / 账号禁用 |
| `get_admin_teacher(teacher)` → `Teacher`           | 在 `get_current_teacher` 之上再校验 `is_admin == True`，否则 403                                   |

#### `events.py` — 时间线写入辅助

[events.py](file:///Users/joey/Projects/teacher-workbench/backend/app/events.py)

```python
add_event(db, student_id, event_type, occurred_at,
          actor_teacher_id=None, ref_table=None, ref_id=None, payload=None)
    -> StudentEvent
```

> **设计要点**：此函数只 `db.add(event)`，**不 commit**——让调用方在同一个业务事务里一起 commit，保证领域变更与时间线事件的原子性。

***

### 4.2 数据模型（10 张表）

所有模型位于 [models.py](file:///Users/joey/Projects/teacher-workbench/backend/app/models.py)，采用 SQLAlchemy 2.0 `Mapped[]` + `mapped_column` 声明式风格。

#### ER 关系概览

```
teacher ──< auth_session                      登录会话（无过期，服务端存储）
teacher ──< class (homeroom_teacher_id)       班主任关系
        └──< student_event (统一事件流，替代 HomeVisit)

class ═══< enrollment >═══ student
              └─ valid_from / valid_to 时间维度
              └─ 部分唯一索引：(student_id) WHERE valid_to IS NULL

exam ──< exam_subject（科目 + 满分）
              │
student ──< exam_result                       科目总分（科目级直接录入，无逐题明细）
student ──< student_event                     追加式时间线（一切变更的事件日志；已完全替代 HomeVisit 表的家访功能）
```

> 注：2026-09 起已移除逐题作答链路（`KnowledgePoint` / `Question` / `QuestionResponse`）和薄弱项预聚合表 `StudentWeakness`；成绩直接以"学生 × 科目"粒度落在 `exam_result` 上。

#### 详细表说明

> 左列为 Python ORM 类名（开发者 `from models import *` 实际使用的标识符），括号内为 SQL 物理表名。

| #  | ORM 类 / SQL 表                               | 主键          | 关键字段 / 约束                                                                                                                                                              | 用途                                                                                                       |
| -- | ------------------------------------------- | ----------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| 1  | **`Teacher`** (teacher)                     | `id`        | `phone`(唯一), `email`(唯一可空), `password_hash`, `is_active`, `is_admin`                                                                                                   | 教师/管理员账号                                                                                                 |
| 2  | **`Student`** (student)                     | `id`        | `admission_no`(唯一), `name`, `gender`, `birth_date`, `guardian_*`, `status`                                                                                             | 学生档案                                                                                                     |
| 3  | **`Class`** (class)                         | `id`        | `name`, `grade_level`, `academic_year`, `homeroom_teacher_id`; UQ(name, academic\_year)                                                                                | 班级                                                                                                       |
| 4  | **`Enrollment`** (enrollment)               | `id`        | `student_id`, `class_id`, `valid_from`, `valid_to`, `reason`; 部分 UQ(student\_id WHERE valid\_to IS NULL)                                                               | **带时间维度的班级归属**                                                                                           |
| 5  | **`Exam`** (exam)                           | `id`        | `name`, `exam_date`                                                                                                                                                    | 考试                                                                                                       |
| 6  | **`ExamSubject`** (exam\_subject)           | `id`        | `exam_id`, `subject`, `full_score`; UQ(exam\_id, subject)                                                                                                              | 考试科目                                                                                                     |
| 7  | **`ExamResult`** (exam\_result)             | `id`        | `student_id`, `exam_subject_id`, `score`, `status`, `entered_by`; UQ(student\_id, exam\_subject\_id)                                                                   | 学生某科成绩（科目级直接存储，无逐题明细）                                                                           |
| 8  | **`HomeVisit`** (home\_visit)               | `id`        | `student_id`, `teacher_id`, `visited_at`, `purpose`, `summary`, `follow_up_*`; IX(student\_id, visited\_at)                                                            | **仅保留的 legacy 表**：自 2026-09 起不再写入/读取（所有业务逻辑已迁移到 `StudentEvent.event_type="home_visited"`，参见 students.py） |
| 9  | **`StudentEvent`** (student\_event)         | `id`        | `student_id`, `event_type`, `occurred_at`, `actor_teacher_id`, `ref_table/ref_id`, `payload`(JSON/JSONB); IX(student\_id, occurred\_at); IX(event\_type, occurred\_at) | **追加式时间线核心表 / 家访记录真正存储地（event\_type="home\_visited"）**                                                   |
| 10 | **`AuthSession`** (auth\_session)           | `token`(PK) | `teacher_id`, `created_at`                                                                                                                                             | Bearer Token 存储                                                                                          |

#### 事件类型常量（students.py）

位于 [students.py L256-263](file:///Users/joey/Projects/teacher-workbench/backend/app/routers/students.py#L256-L263)：

```python
SYSTEM_EVENT_TYPES = {"enrolled", "class_moved", "exam_taken",
                      "result_changed", "weakness_flagged"}
MANUAL_EVENT_TYPES = {"home_visited", "talk", "tutoring",
                      "parent_call", "note_added"}
```

- **系统事件**：由后端逻辑自动写入，不可编辑/删除

- **人工事件**：教师在学生详情页手动创建；**此外的任何 event\_type 被视为自定义类型**

***

### 4.3 API 路由详解

所有路由挂载在 `/api` 前缀下。除 `/api/auth/*`、`/api/health`、`/api/admin/*`（内部再鉴权）外，均需要 `Authorization: Bearer <token>` 请求头。

> 提示：`routers/__init__.py` 为空文件，仅作为 Python 常规包标识存在，无代码。

#### 认证 `/api/auth/*` — [auth.py](file:///Users/joey/Projects/teacher-workbench/backend/app/routers/auth.py)

| 方法   | 路径               | 入参                                | 返回                 | 说明                    |
| ---- | ---------------- | --------------------------------- | ------------------ | --------------------- |
| POST | `/auth/register` | `{name, phone, password, email?}` | `{token, teacher}` | 手机号 6-15 位数字；创建后自动建会话 |
| POST | `/auth/login`    | `{phone, password}`               | `{token, teacher}` | 密码错返回 401             |
| POST | `/auth/logout`   | —                                 | `{ok}`             | 删除当前 Bearer 对应的会话行    |
| GET  | `/auth/me`       | —                                 | 教师信息               | 由依赖保证已登录              |

#### 学生 `/api/students/*` — [students.py](file:///Users/joey/Projects/teacher-workbench/backend/app/routers/students.py)

| 方法       | 路径                                         | 说明                                                |
| -------- | ------------------------------------------ | ------------------------------------------------- |
| GET      | `/students`                                | 学生列表（含当前班级）                                       |
| POST     | `/students`                                | 新建学生 + 自动生成学号 S递增 + 入班 + enrolled 事件              |
| GET      | `/students/{id}`                           | 档案 + 历次成绩 + 家访记录                                  |
| PATCH    | `/students/{id}`                           | 编辑资料；**转班走关旧开新 + class\_moved 事件**                |
| DELETE   | `/students/{id}`                           | 有历史数据时软删除（status=inactive + 关闭 enrollment），无数据时硬删 |
| GET      | `/students/{id}/timeline`                  | 右侧时间线（系统 + 人工 全部事件）                               |
| GET      | `/students/{id}/weaknesses`                | 知识点薄弱项（按 severity 降序）                             |
| GET      | `/students/{id}/failed-questions?subject=` | 错题明细（可按科目过滤）                                      |
| **POST** | **`/students/{id}/events`**                | 记录人工事件（家访/谈心/辅导/家长沟通/备注/自定义类型）                    |
| GET      | `/students/{id}/events`                    | 人工事件列表（不含系统事件，左侧列表用）                              |
| GET      | `/students/{id}/events/{eid}`              | 单事件详情                                             |
| PATCH    | `/students/{id}/events/{eid}`              | 编辑事件（系统事件不可改，他人事件不可改）                             |
| DELETE   | `/students/{id}/events/{eid}`              | 删除事件（同上限制）                                        |
| GET      | `/teachers/me/event-types`                 | 当前教师自定义的历史事件类型（去重）                                |
| PATCH    | `/results/{id}`                            | 更正成绩 + 写入 `result_changed` 系统事件                   |

#### 班级 `/api/classes/*` — [classes.py](file:///Users/joey/Projects/teacher-workbench/backend/app/routers/classes.py)

| 方法     | 路径              | 说明                                               |
| ------ | --------------- | ------------------------------------------------ |
| GET    | `/classes`      | 班级列表（含班主任 + 在读学生数 + 名单）                          |
| POST   | `/classes`      | 新建（UQ 名称×学年）                                     |
| GET    | `/classes/{id}` | 班级详情：基本信息 + 名单 + **按考试当日 enrollment 统计的各科平均分趋势** |
| PATCH  | `/classes/{id}` | 编辑                                               |
| DELETE | `/classes/{id}` | 仍有 enrollment（含历史）时 409 拒绝                       |

#### 考试 `/api/exams/*` — [exams.py](file:///Users/joey/Projects/teacher-workbench/backend/app/routers/exams.py)

| 方法     | 路径                     | 说明                                                               |
| ------ | ---------------------- | ---------------------------------------------------------------- |
| GET    | `/exams`               | 考试列表（含科目）                                                        |
| POST   | `/exams`               | 新建考试 + 多个科目（同名同日 409）                                            |
| GET    | `/exams/trend`         | 全校各科平均分趋势（供首页/考试页趋势图）                                            |
| GET    | `/exams/{id}`          | 考试基本信息 + 科目                                                      |
| GET    | `/exams/{id}/averages` | 全校统计（avg/min/max/count）+ **各班按考试当日 enrollment 归属** 的班级平均         |
| PATCH  | `/exams/{id}`          | 改名称/日期；改科目需此考试未录入成绩                                              |
| DELETE | `/exams/{id}`          | 级联删 question\_response / exam\_result / question / exam\_subject |

#### 仪表盘 `/api/dashboard` — [dashboard.py](file:///Users/joey/Projects/teacher-workbench/backend/app/routers/dashboard.py)

- `GET /dashboard`：聚合返回 counts（学生/班级/考试/家访）、upcoming\_exams（≤3 个）、follow\_ups（家访且需跟进，≤5 条）、recent\_events（最新 8 条动态）

#### 个人中心 `/api/profile` — [profile.py](file:///Users/joey/Projects/teacher-workbench/backend/app/routers/profile.py)

| 方法    | 路径         | 说明                              |
| ----- | ---------- | ------------------------------- |
| GET   | `/profile` | 教师信息 + 我的班级 + 统计（家访数/录入成绩数/备注数） |
| PATCH | `/profile` | 编辑姓名 / 邮箱 / 任教学科                |

#### 杂项 `/api/teachers` — [misc.py](file:///Users/joey/Projects/teacher-workbench/backend/app/routers/misc.py)

- `GET /teachers`：列出全部**非管理员**教师（供班级下拉选班主任）

#### 管理员 `/api/admin/*` — [admin.py](file:///Users/joey/Projects/teacher-workbench/backend/app/routers/admin.py)

全部走 `get_admin_teacher` 依赖。

| 方法     | 路径                         | 说明                                            |
| ------ | -------------------------- | --------------------------------------------- |
| GET    | `/admin/stats`             | 数据库驱动、14 张表行数、教师/管理员/活跃/会话数                   |
| GET    | `/admin/teachers`          | 教师全列表（含 is\_active / is\_admin / 创建时间）        |
| PATCH  | `/admin/teachers/{id}`     | 启停用、改管理员、重置密码（不能自降 admin）                     |
| DELETE | `/admin/teachers/{id}`     | 删除（不能删自己）                                     |
| GET    | `/admin/sessions`          | 活动会话（Token 只显前 8 位+…）                         |
| DELETE | `/admin/sessions/{prefix}` | 按前缀终止会话                                       |
| POST   | `/admin/sessions/kill-all` | 清空全部会话                                        |
| POST   | `/admin/inspect`           | `{table, limit=20}` — ORM 只读探查（白名单 14 表）      |
| POST   | `/admin/db/reset`          | `DROP ALL → CREATE ALL`，不清空不可恢复（仅 DB 重建，不灌种子） |

***

### 4.4 关键函数与类

| 函数 / 类                                         | 所在文件                                     | 职责                                                            |
| ---------------------------------------------- | ---------------------------------------- | ------------------------------------------------------------- |
| `utcnow()`                                     | `models.py`                              | 返回 **naive UTC datetime**（兼容 SQLite）                          |
| `JSONType`                                     | `models.py`                              | PostgreSQL JSONB + SQLite JSON 的跨方言别名                         |
| `normalize_phone()`                            | `routers/auth.py`                        | 移除空格/横杠统一手机号格式                                                |
| `teacher_out(t)`                               | `routers/auth.py` / `routers/profile.py` | 教师信息公共序列化函数（两处重复，可优化）                                         |
| `current_class(db, student_id)`                | `routers/students.py`                    | 通过 `enrollment.valid_to IS NULL` 查当前班级                        |
| `class_out(c, teacher, students)`              | `routers/classes.py`                     | 班级信息公共序列化                                                     |
| `current_students(db, class_id)`               | `routers/classes.py`                     | 班级当前在读学生（通过 enrollment 有效期）                                   |
| `_check_duplicate(db, name, year, exclude_id)` | `routers/classes.py`                     | 同学年同名班级校验                                                     |
| `add_event(...)`                               | `events.py`                              | 追加时间线事件（不 commit，调用方负责）                                       |
| `seed(db)`                                     | `seed.py`                                | 完整演示数据构造器：3 教师 / 2 班级 / 24 学生 / 2 考试 / 全量逐题作答 / 薄弱项 / 100+ 事件 |

***

## 5. 前端架构（Vue 3 / Vite）

### 5.1 核心模块

#### `main.js`

[main.js](file:///Users/joey/Projects/teacher-workbench/frontend/src/main.js) — 极简入口：`createApp(App).use(router).mount("#app")`

#### `App.vue` — 顶栏 + 路由出口

[App.vue](file:///Users/joey/Projects/teacher-workbench/frontend/src/App.vue)

- `onMounted` 时调用 `loadMe()`；路由切换时若有 Token 但 `me.value` 为空再补拉

- `logout()`：POST `/auth/logout`（忽略失败）→ 清本地 Token + 清 `me` → 返回 `/login`

- **双角色顶栏**：

  - 管理员：仅显示「管理」导航链接，头像标 A 红色徽章，管理员头像不可点击

  - 教师：显示「首页/学生/班级/考试」+ 头像链接至 `/profile`

#### `api.js` — HTTP 层

[api.js](file:///Users/joey/Projects/teacher-workbench/frontend/src/api.js)

```js
const BASE = "/api";
// localStorage 存 tw-token；登录/登出 setToken(null) 会移除
getToken() / setToken(token)

// 通用请求封装：
// 1) 注入 Content-Type + Bearer Token
// 2) 401（非 auth/ 路径）→ 清 token + 跳登录
// 3) 422 FastAPI 校验错误数组 → 拼接 msg 为分号分隔字符串
// 4) 非 2xx → throw Error(body.detail || statusText)
async request(path, options)

// 导出对象：
api.get(path) / api.post(path, body) / api.patch(path, body) / api.delete(path)
```

#### `auth.js` — 教师响应式状态

[auth.js](file:///Users/joey/Projects/teacher-workbench/frontend/src/auth.js)

- `me = ref(null)`：当前教师对象（含 `{id, name, phone, email, subject, is_admin}`）

- `loadMe()`：GET `/auth/me` 写入 `me.value`；无 Token 时不请求

- `clearMe()`：置空 `me`

#### `strings.js` — 中文词典 + 枚举渲染

[strings.js](file:///Users/joey/Projects/teacher-workbench/frontend/src/strings.js) — 零依赖 i18n + 领域映射

| 导出函数                                                                   | 作用                                                         |
| ---------------------------------------------------------------------- | ---------------------------------------------------------- |
| `t(key, params?)`                                                      | 查 100+ 条词典；支持 `{param}` 占位替换                               |
| `subject(s)`                                                           | math→数学, english→英语, chinese→语文…                           |
| `subjectColor(s)`                                                      | math→蓝, english→绿, chinese→金, physics→紫, chemistry→红       |
| `qtype(ty)`                                                            | choice→选择题, fill-in→填空题, calculation→计算题…                  |
| `statusLabel(s)` / `genderLabel(g)` / `exatypeLabel()` / `termLabel()` | 各类代码→中文                                                    |
| **事件元数据**                                                              | `EVENT_TYPES = {type: {icon, color}}` 映射 10 种内置类型          |
| `eventTypeIcon / Color / Label(type)`                                  | 从 EVENT\_TYPES 取元数据                                        |
| `describeEvent(type, payload)`                                         | 根据 event\_type + payload 生成人类可读描述（转班「A→B」、成绩更正「X: 60→65」等） |

***

### 5.2 路由与守卫

[router.js](file:///Users/joey/Projects/teacher-workbench/frontend/src/router.js)

#### 路由表

```js
/                       → HomeView           教师首页仪表盘
/login                  → LoginView          登录/注册
/profile                → ProfileView        个人中心
/classes                → ClassesView        班级列表
/classes/:id            → ClassDetailView    班级详情
/students               → StudentsView       学生列表
/students/new           → StudentNewView     新建学生
/students/:id           → StudentDetailView  学生工作台
/students/:sid/events/new         → EventDetailView  新建事件
/students/:sid/events/:eid        → EventDetailView  编辑事件
/exams                  → ExamsView          考试列表
/exams/new              → ExamNewView        新建考试
/exams/:id              → ExamDetailView     考试平均分
/admin                  → AdminView          开发者后台
```

- base URL: `/gao/`（Vite `base` + nginx 配置一致）

#### 守卫逻辑（`router.beforeEach`）

1. **未登录 → 跳转** **`/login`**（当前已是 `/login` 则放过）
2. **已登录再进** **`/login`** **→ 按角色重定向**：管理员→`/admin`，教师→`/`
3. **进入教师路由但** **`me`** **为空 → 先** **`await loadMe()`**
4. **非管理员访问** **`/admin*`** **→ 302 回** **`/`**
5. **管理员访问教师路由（`/`,** **`/profile`,** **`/classes*`,** **`/students*`,** **`/exams*`）→ 302 回** **`/admin`**

> 关键常量：`TEACHER_ROUTE_PREFIXES = ["/", "/profile", "/classes", "/students", "/exams"]`。`isTeacherRoute()` 函数用于守卫 #5 的精确前缀匹配。

***

### 5.3 视图组件

| 视图                    | 路径                            | 主要功能                                                                                                               | <br />                                               |
| --------------------- | ----------------------------- | ------------------------------------------------------------------------------------------------------------------ | :--------------------------------------------------- |
| **LoginView**         | `views/LoginView.vue`         | 左右 Tab 切换登录/注册；调用 \`api.post("/auth/register"                                                                      | "/login")`→`setToken(token)`→ 按角色`router.replace()\` |
| **HomeView**          | `views/HomeView.vue`          | 四卡片统计（学生/班级/考试/家访）、考试倒计时、快捷操作（加学生/看考试/学生列表）、待跟进家访、最新动态（mini timeline）                                              | <br />                                               |
| **ProfileView**       | `views/ProfileView.vue`       | 头像 + 基本资料编辑、我的班级卡片（含学生 chips 链接跳转）、教学足迹三统计                                                                         | <br />                                               |
| **ClassesView**       | `views/ClassesView.vue`       | 班级卡片网格、新建班级模态框（名称/年级/学年/班主任下拉）、编辑/删除（删除前确认）                                                                        | <br />                                               |
| **ClassDetailView**   | `views/ClassDetailView.vue`   | 基本信息 + 学生名单表格 + LineChart 趋势（按考试）+ 各科平均汇总表格                                                                        | <br />                                               |
| **StudentsView**      | `views/StudentsView.vue`      | 学生表格（学号/姓名/性别/班级/状态）、顶部搜索框（模糊匹配姓名/学号/班级）、添加学生按钮                                                                    | <br />                                               |
| **StudentNewView**    | `views/StudentNewView.vue`    | 三段表单（基本信息 / 监护人信息 / 分配班级）→ POST 后跳转学生详情                                                                            | <br />                                               |
| **StudentDetailView** | `views/StudentDetailView.vue` | **核心工作台**：左侧两栏（档案卡 + 成绩表格可 inline 编辑更正 / 薄弱项列表 / 错题表格）；右侧事件记录（可折叠新建/列表）+ 时间线 Timeline（点击人工事件进入编辑）；顶部成绩趋势 LineChart | <br />                                               |
| **EventDetailView**   | `views/EventDetailView.vue`   | 独立事件详情页（新建/edit 二合一）；`event_type` 使用 `<input list=type-preset>` datalist，含 5 个人工预设 + 教师自定义历史                       | <br />                                               |
| **ExamsView**         | `views/ExamsView.vue`         | 考试列表（名称/日期/科目 + 满分），新建考试按钮                                                                                         | <br />                                               |
| **ExamNewView**       | `views/ExamNewView.vue`       | 考试名称 + 日期 + 动态科目行（科目 + 满分可增删）                                                                                      | <br />                                               |
| **ExamDetailView**    | `views/ExamDetailView.vue`    | 全校统计卡片（min/max/avg 按科）+ 全校趋势折线图（虚线高亮当前考试）+ 各班平均分表格                                                                 | <br />                                               |
| **AdminView**         | `views/AdminView.vue`         | 5 个分区：①数据库概览（驱动/表行数/统计）②教师账号（启停用、升降级、重置密码、删除）③活动会话（终止/清空所有）④数据探查（选表 + limit 预览）⑤危险操作（重置数据库按钮）                      | <br />                                               |

***

### 5.4 通用组件

#### `Icon.vue` — 内联 SVG 图标

[Icon.vue](file:///Users/joey/Projects/teacher-workbench/frontend/src/components/Icon.vue)

15 个手绘 24×24 stroke 图标（无外部依赖，通过 `PATHS` 对象映射 SVG 路径字符串）：

| name                   | 用途                |
| ---------------------- | ----------------- |
| `board`                | 品牌 Logo（黑板 + 粉笔字） |
| `plus`                 | 新建按钮              |
| `clipboard`            | 考试相关              |
| `users`                | 学生/班级相关           |
| `home`                 | 家访                |
| `alert`                | 薄弱项/警告            |
| `pencil`               | 成绩更正/编辑           |
| `swap`                 | 转班                |
| `note`                 | 备注/谈心/辅导          |
| `enroll`               | 入学                |
| `check`                | 成功确认              |
| `chevron-left/up/down` | 折叠导航箭头            |

使用：`<Icon name="board" :size="20" />`，颜色继承 `currentColor`。

#### `LineChart.vue` — 纯 SVG 折线图

[LineChart.vue](file:///Users/joey/Projects/teacher-workbench/frontend/src/components/LineChart.vue)

Props：

- `labels`：X 轴分类（如考试名称数组）

- `series`：`[{ key, label, color, values: (number|null)[] }]`；`null` 值会产生断裂

- `yMax`：Y 轴上限（默认 100）

- `highlightIndex`：高亮竖线的 X 索引（用于"当前考试标记"）

特性：640×300 viewBox 自适应、5 格 Y 轴刻度、hover 透明竖条 → tooltip 气泡、图例、断裂线处理。

#### `Timeline.vue` — 时间线列表

[Timeline.vue](file:///Users/joey/Projects/teacher-workbench/frontend/src/components/Timeline.vue)

Props：

- `events`：事件数组（`{id, event_type, occurred_at, actor, payload, is_system?}`）

- `clickable`：是否允许点击（人工事件可点击进入编辑，系统事件不可）

emit: `@select="(event)"` — 仅当 `!is_system` 时触发

渲染：左侧带图标的彩色圆点（取色 `eventTypeColor`）+ 卡片头部（事件名/操作人）+ 描述（`describeEvent`）+ 时间。

***

### 5.5 样式系统

[style.css](file:///Users/joey/Projects/teacher-workbench/frontend/src/style.css) — 零 UI 框架，纯手写 CSS。

**设计主题 "黑板与红笔"**：

| CSS 变量                    | 值                         | 语义                  |
| ------------------------- | ------------------------- | ------------------- |
| `--board`                 | `#1f3d2e`                 | 黑板绿（顶栏主色）           |
| `--chalk`                 | `#e8c868`                 | 粉笔黄（活跃导航下划线）        |
| `--chalk-ink`             | `#edf4ee`                 | 粉笔白（黑板上文字）          |
| `--bg`                    | `#f3f5f1`                 | 纸张色（页面背景）           |
| `--primary`               | `#2f5b44`                 | 主按钮/链接色（黑板绿浅版）      |
| `--danger`                | `#b42318`                 | **红笔**（低分/警告/破坏性操作） |
| `--ok / --warn / --amber` | 绿/棕/金                     | 状态色                 |
| `--font-display`          | Georgia, Songti SC, serif | 标题/大数字展示字体          |

**主要组件类**：`.card` `.badge` `.topnav` `.auth-*` `.stat-grid` `.two-col` `.timeline-*` `.chart-*` `.weakness` `.severity-bar` `.quick-actions` `.mini-event` `.countdown-item` `.student-chips` 等。

响应式：`@media (max-width: 900px)` 双栏降单栏；`@media (max-width: 720px)` 顶栏换行。

***

## 6. 依赖关系图

### 6.1 后端内部依赖

```
main.py
  ├─ database.py (Base, engine)
  ├─ deps.py (get_current_teacher)
  └─ routers/*
      ├─ database.py (get_db)
      ├─ deps.py (get_current_teacher / get_admin_teacher)
      ├─ models.py (所有 ORM 模型)
      ├─ events.py (add_event)
      ├─ security.py (仅 auth.py 与 admin.py 使用)
      └─ pydantic BaseModel (请求体校验)

models.py → database.py (Base)
deps.py   → database.py (get_db), models.py (AuthSession, Teacher)
security.py → 无内部依赖 (纯 hashlib / secrets)
events.py → models.py (StudentEvent)
seed.py   → database.py, events.py, models.py, security.py
```

### 6.2 前端内部依赖

```
main.js → App.vue + router.js + style.css

App.vue
  ├─ router (useRoute / useRouter)
  ├─ components/Icon.vue
  ├─ api.js (getToken, setToken, post logout)
  ├─ auth.js (loadMe, clearMe, me)
  └─ strings.js (t)

router.js
  ├─ api.js (getToken)
  ├─ auth.js (loadMe, me)
  └─ views/*

views/*
  ├─ api.js (全部使用)
  ├─ auth.js (读取 me.is_admin)
  ├─ strings.js (t / subject / event*Label* / describeEvent)
  ├─ components/* (Icon / LineChart / Timeline)
  └─ vue-router (useRoute / useRouter)

components/* → strings.js (仅 Timeline 用到，取色/取图标/描述)
```

### 6.3 第三方依赖

**后端** (`requirements.txt`)：

```
fastapi >= 0.115       # Web 框架
uvicorn >= 0.30        # ASGI 服务器
sqlalchemy >= 2.0.40   # ORM
pydantic >= 2.7        # 请求/响应模型校验
psycopg[binary] >= 3.2 # PostgreSQL 驱动（可选，SQLite 不需要）
```

**前端** (`package.json`)：

```
运行时:
  vue ^3.5.13           # 响应式 UI 框架
  vue-router ^4.5.0     # SPA 路由

开发时:
  vite ^6.0.7           # 构建工具 / 开发服务器
  @vitejs/plugin-vue ^5.2.1
```

***

## 7. 事件驱动与时间线机制

`student_event` 表是本系统的**单一真实事件源**（append-only event log）。

### 7.1 写入原则

> 每一个领域状态变更 **在同一数据库事务** 中，额外调用 `add_event()` 追加一条事件行。

示例流程（新建学生，[students.py L72-101](file:///Users/joey/Projects/teacher-workbench/backend/app/routers/students.py#L72-L101)）：

```
事务开始
  → INSERT student
  → INSERT enrollment (班级关系)
  → add_event("enrolled", payload={class: "七年级1班"})  ← 与业务同事务
事务 COMMIT
```

### 7.2 事件写入点汇总

| 触发动作                       | event\_type                   | 写入位置                                            |
| -------------------------- | ----------------------------- | ----------------------------------------------- |
| 新建学生                       | `enrolled`                    | `students.py:create_student`                    |
| 转班                         | `class_moved`                 | `students.py:update_student` (含 class\_id 变更分支) |
| 成绩更正                       | `result_changed`              | `students.py:update_result`                     |
| 学生停用                       | `note_added` (note="账号停用")    | `students.py:delete_student` (软删分支)             |
| 考试参加（种子数据）                 | `exam_taken`                  | `seed.py`（MVP 仅种子阶段生成）                          |
| 薄弱项首次标记（种子）                | `weakness_flagged`            | `seed.py`（MVP 仅种子阶段生成）                          |
| 教师记录家访/谈心/辅导/家长沟通/备注/自定义事件 | 对应 event\_type                | `students.py:create_event_record`               |
| 家访 + 教师备注（种子）              | `home_visited` / `note_added` | `seed.py`                                       |

### 7.3 消费方

- **首页最新动态**：`/api/dashboard` → `StudentEvent` 全表最新 8 条

- **首页待跟进**：`/api/dashboard` → `event_type == home_visited AND payload.follow_up_needed == true` 最新 5 条

- **学生详情时间线**：`/api/students/{id}/timeline` → 按时间倒序全部事件

- **学生详情事件列表**：`/api/students/{id}/events` → 仅人工事件（排除 SYSTEM\_EVENT\_TYPES）

- **个人中心统计**：`/api/profile` → 按 `actor_teacher_id == me.id` 分别统计 `home_visited` / `note_added` / `entered_by` 成绩录入数

***

## 8. 安全与鉴权

### 8.1 密码存储

[security.py](file:///Users/joey/Projects/teacher-workbench/backend/app/security.py)

- 算法：PBKDF2-HMAC-SHA256，200,000 次迭代

- 盐值：每用户独立 16 字节（128-bit）`secrets.token_hex(16)`

- 存储格式：`{salt_hex}${digest_hex}` 用 `$` 分隔

- 校验时用 `secrets.compare_digest` 防时序攻击

### 8.2 会话管理

- Token：`secrets.token_hex(32)` = 64 字符十六进制，以 `auth_session.token` 为主键存储

- 无过期时间（MVP 简化）；可通过管理员 `/admin/sessions` 手动终止或 kill-all

- 前端：Token 存 `localStorage`，每次请求自动加 `Authorization: Bearer <token>`

- **401 自动跳转**：`api.js` 对非 auth 接口的 401 响应 → 清 token → `window.location.href = "/login"`

### 8.3 角色隔离

| 角色   | `teacher.is_admin` | 可达路由                                                  | 顶部导航             |
| ---- | ------------------ | ----------------------------------------------------- | ---------------- |
| 管理员  | `True`             | `/admin`                                              | 仅「管理」            |
| 普通教师 | `False`            | `/`, `/profile`, `/classes*`, `/students*`, `/exams*` | 首页/学生/班级/考试 + 头像 |

**双重守卫**：

- **前端**：router.js `beforeEach` 守卫（见 5.2）

- **后端**：普通业务路由统一 `Depends(get_current_teacher)`；管理员路由 `Depends(get_admin_teacher)`，即使绕过前端也会 403

### 8.4 输入安全

- SQL 注入：全部查询走 SQLAlchemy 参数绑定 / ORM，零字符串拼接

- XSS：Vue 模板默认自动转义；`Icon.vue` 的 `v-html` 仅渲染项目内的白名单 SVG 路径

- Pydantic 校验：所有 POST/PATCH 路由使用 `BaseModel` 声明入参类型、长度、数值范围约束

### 8.5 已知安全缺口（生产化前需处理）

- CORS `allow_origins=["*"]`（演示宽松配置）

- Session token 无过期/刷新机制

- `.env` 默认弱密码占位值

- 无速率限制（登录爆破防护）

- 无 CSRF 防护（Bearer Token + SameSite 隐式依赖前端托管）

***

## 9. 运行指南

### 9.1 本地开发模式

**前后端分别启动，改代码热重载**。

#### 后端（端口 8001，API 文档 `http://127.0.0.1:8001/docs`）

```bash
cd backend
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
./.venv/bin/python -m app.seed        # 首次或重置：删表→建表→灌演示数据
./.venv/bin/uvicorn app.main:app --port 8001 --reload
```

不设置 `DATABASE_URL` → 自动使用本地 SQLite 文件 `backend/teacher_workbench.db`。

#### 前端（默认端口 5173，被占用自动顺延）

```bash
cd frontend
npm install
npm run dev
```

> 开发代理：`/gao/api/*` → `127.0.0.1:8000`（fallback `/api` → `8000`）。若后端端口改了，需同步修改 [frontend/vite.config.js](file:///Users/joey/Projects/teacher-workbench/frontend/vite.config.js) 中的 proxy target。

#### 端口占用排查

```bash
lsof -nP -iTCP:8001 -sTCP:LISTEN   # 后端
lsof -nP -iTCP:5173 -sTCP:LISTEN   # 前端
kill <PID>
```

***

### 9.2 Docker 模式

三容器编排：`db` (PostgreSQL 17) → `backend` (FastAPI) → `frontend` (nginx)。链式健康检查：每个服务均声明 `HEALTHCHECK`（Dockerfile 与 compose 双重定义），前服务 `(healthy)` 后才启动下一个（`depends_on.condition: service_healthy`）。

```bash
cp .env.example .env       # 填 Postgres 凭据（compose 缺文件会报错）
docker compose up -d --build   # 首次或改代码后加 --build
```

访问 `http://localhost/`（nginx 托管前端 + 反代 `/api` 到 backend）。

**常用运维**：

```bash
docker compose ps                           # 三服务都应显示 (healthy)
docker compose logs -f backend              # 跟踪后端日志
docker compose stop / start                 # 停止/重启（保留容器）
docker compose down                         # 删容器（保留 pgdata 卷）
docker compose down -v                      # 连数据卷一起删（彻底重置）
docker compose exec backend python -m app.seed   # （重新）灌入演示数据
```

**首次使用**：compose up 后需手动执行一次 seed（容器不会自动灌数据，避免持久化数据库被误清）。

***

### 9.3 演示账号

| 角色            | 手机号           | 密码         | 说明                |
| ------------- | ------------- | ---------- | ----------------- |
| 🧑‍🏫 陈老师（数学） | `13800000001` | `123456`   | 七1班班主任            |
| 🧑‍🏫 赵老师（英语） | `13800000002` | `123456`   | 七2班班主任            |
| 🔧 开发者（管理员）   | `13800000000` | `admin123` | 登录后直达 `/admin` 后台 |

演示数据亮点故事：

- **林晓雨**（七1班）：数学薄弱；期中 Q7 有成绩更正记录（`result_changed` 事件）+ 家访 + 教师备注

- **王浩**：2026-03-01 从七2班转入七1班（平均分按"考试当日班级归属"仍计入七1班）

***

## 10. 设计亮点与关键决策

### 10.1 带时间维度的 Enrollment 表

这是整个系统最有价值的设计。学生转班**从不 UPDATE 旧记录**：

```
关闭旧 enrollment.valid_to = 今天
追加新 enrollment(valid_from=今天, reason="moved")
写入 class_moved 事件
```

**收益**：查询"某考试当日某班平均分"时，用区间连接即可准确归属：

```sql
Enrollment.valid_from <= Exam.exam_date
AND (Enrollment.valid_to IS NULL OR Enrollment.valid_to >= Exam.exam_date)
```

王浩的演示故事线正是为此设计：两场考试都计入七1班，虽然他入学时在七2班。

**部分唯一索引**：`uq_one_current_enrollment` 在 DB 层保证每学生**最多一条在读**（`valid_to IS NULL`）记录。

### 10.2 追加式时间线 StudentEvent

- 表只增不改，业务变更与事件写入同事务

- `payload JSONB` 灵活携带展示数据；`ref_table/ref_id` 回指业务行

- 时间线、首页动态、待跟进列表直接查此表 → 零对账，零一致性问题

### 10.3 成绩录入链路（科目级）

```
exam → exam_subject（科目 / 满分）
           ↓
   exam_result（学生 × 科目：score / status / entered_by）
```

自 2026-09 起已移除逐题作答链路（`KnowledgePoint` / `Question` / `QuestionResponse`）和薄弱项预聚合表（`StudentWeakness`），成绩直接按"学生 × 科目"粒度录入 `exam_result`。前端学生详情页不再展示"错题下钻"与"薄弱项"卡片；种子脚本 `seed.py` 直接按高斯分布生成科目级成绩与趋势。后续如需恢复逐题明细，可在此基础上重新挂接 Question/QuestionResponse 表，不必改动现有 exam_result。

### 10.4 双角色前端隔离

管理员不是教师 → 管理员导航精简、路由守卫拦截、后端 `get_admin_teacher` 二次校验。前后端双重门保证即使管理员猜到教学页面 URL 也无法进入。

### 10.5 零前端 UI 框架

纯 CSS + 自绘 SVG 图标 + 自写 LineChart/Timeline。无 UI 框架运行时体积，首屏加载轻。代价：样式完全手写，需保证跨浏览器一致性。

### 10.6 PG-First + SQLite 回退

通过 `JSON().with_variant(JSONB(), "postgresql")` + 部分索引的 `postgresql_where/sqlite_where` 双声明，本地开发零依赖，部署直接获得 PostgreSQL JSONB 查询能力（首页 follow-ups 的 `payload.contains()` JSON 包含查询在 PG 上可利用 GIN 索引）。

***

## 11. 已知限制与后续 TODO

| #  | 类别                    | 现状                                                                           | 建议                                                          |
| -- | --------------------- | ---------------------------------------------------------------------------- | ----------------------------------------------------------- |
| 1  | **薄弱项实时聚合**           | 仅 seed 阶段推导一次；成绩更正 (`PATCH /results/{id}`) 后未重算                              | 在 `update_result` 中对受影响的 student\_id × question.kp\_id 重算聚合 |
| 2  | **Session 过期**        | Token 永不过期                                                                   | 加 `expires_at` 列 + 刷新机制 / Access/Refresh Token 分离           |
| 3  | **CORS 宽松**           | `allow_origins=["*"]`                                                        | 生产化时限定前端域名                                                  |
| 4  | **无迁移工具**             | 改 models → 重跑 seed 清库                                                        | 引入 Alembic 做增量迁移                                            |
| 5  | **无限流**               | 登录/接口无速率限制                                                                   | 加 slowapi / 自写依赖限 IP                                        |
| 6  | **无服务端 CSRF**         | Bearer Token 隐式依赖                                                            | 生产部署启用 SameSite cookie 或显式 CSRF Token                       |
| 7  | **前端 base 硬编码**       | `router.js base="/gao/"` + `vite.config.js base="/gao/"` 两处重复                | 统一为环境变量                                                     |
| 8  | **teacher\_out 函数重复** | `auth.py` 与 `profile.py` 各自定义了相同的 `teacher_out(t)`                           | 抽到公共模块（如 `schemas.py`）                                      |
| 9  | **ExamDetail 分页**     | 考试列表/平均分表格无分页（当前 2 场考试无影响）                                                   | 数据量增大后加 limit/offset 或游标分页                                  |
| 10 | **搜索仅前端**             | `StudentsView` 搜索在 JS `filter()` 内存过滤                                        | 后端加 `?q=` 参数走 DB LIKE / ILIKE                               |
| 11 | **HomeVisit 表定义残留**   | 2026-09 已清理 students.py 中所有读写；当前仅 models.py 保留 ORM 类（供 admin 探查 legacy 数据）   | 部署上线后 1\~2 个版本观察无回退，可在 Alembic 中 DROP TABLE 并移除 ORM 类       |
| 12 | **管理员密码重置校验**         | admin.py 重置密码无最小长度校验                                                         | 加上 `min_length=6` 与前端对齐                                     |
| 13 | **Docker 镜像版本 pin**   | `postgres:17`, `python:3.14-slim`, `node:22-alpine`, `nginx:alpine` 使用浮动 tag | 生产化建议 pin 到具体 digest 或精确 patch 版本                           |

***

*本文档最后更新：2026-09-02（HomeVisit → StudentEvent 迁移完成：students.py 读写全部归并到 StudentEvent）。*
