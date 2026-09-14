# Teacher Workbench (MVP demo)

A school-management workbench for teachers: student profiles (role + profile
fields live in a JSONB payload), per-subject exam scores, exam **averages**
(school-wide and per class), **home visits**, student **tags**, and a
per-student **timeline** of every event.

- **Backend**: Python 3.14 · FastAPI · SQLAlchemy 2（Docker 部署使用 PostgreSQL 17，本地开发默认 SQLite）
- **Frontend**: Vue 3 · Vite · vue-router（纯 CSS，无 UI 框架）

Design notes and schema rationale: [docs/design.md](docs/design.md)

## 启动与关闭

有两种运行方式：**本地开发模式**（前后端分开跑，改代码实时生效）和 **Docker 模式**
（一键构建，接近生产环境）。两者都占用 8001 端口，**不要同时运行**。

演示账号：`chen@school.edu / 123456`（陈老师）、`admin@school.dev / admin123`（管理员），
也可以在登录页自行注册（手机号可在个人中心选填）。

### 方式一：本地开发模式

**首次准备（只需一次）：**

```bash
cd backend
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
./.venv/bin/python -m app.seed        # 建表 + 灌入演示数据
```

不设置 `DATABASE_URL` 时，本地开发默认使用 SQLite 文件
`backend/teacher_workbench.db`，无需安装任何数据库。

**启动（两个终端分别运行）：**

```bash
# 终端 1 —— 后端：API 在 http://127.0.0.1:8001，交互文档在 /docs
cd backend
./.venv/bin/uvicorn app.main:app --port 8001 --reload

# 终端 2 —— 前端：Vite 会打印实际地址（默认 http://localhost:5173）
cd frontend
npm install                           # 首次需要
npm run dev
```

浏览器打开 Vite 打印的地址即可（若 5173 被占用会自动顺延到 5174，以终端输出为准）。

**停止**：在对应终端按 `Ctrl + C` 即可。

**端口被占用时**，找到并结束占用进程：

```bash
lsof -nP -iTCP:8001 -sTCP:LISTEN      # 查看占用进程（前端查 5173/5174）
kill <PID>                            # 结束它
```

**重置演示数据**：seed 脚本在非全新数据库上会**重复灌入**数据——先删除
SQLite 文件 `backend/teacher_workbench.db`（或 drop 掉整个 schema），再执行
`./.venv/bin/python -m app.seed`。

> 注意：若修改后端端口，需同步修改 `frontend/vite.config.js` 里的代理目标。

**（可选）本地后端连接 Docker 里的 PostgreSQL**：先按方式二把 `db` 服务跑起来，
然后给后端设置连接串再启动（需先重装一次依赖以获得 psycopg 驱动）：

```bash
./.venv/bin/pip install -r requirements.txt
export DATABASE_URL=postgresql+psycopg://workbench:workbench@127.0.0.1:5433/workbench
```

### 方式二：Docker Compose

一键构建并启动三个服务：`db`（PostgreSQL 17）、`backend`（FastAPI）、
`frontend`（nginx 托管在 **80 端口**并反向代理 `/api`）。访问
**http://localhost/** 即可。

**首次启动前**：复制环境变量模板并按需修改数据库凭据（compose 检测不到该文件
会直接报错；数据库凭据不入库，`.env` 已被 gitignore / dockerignore 忽略）：

```bash
cp .env.example .env
```

```bash
docker compose up -d --build     # 构建镜像并后台启动（首次或改代码后加 --build）
```

常用命令：

```bash
docker compose ps                # 查看状态，三个服务都应显示 healthy
docker compose logs -f           # 跟踪全部日志（只看后端用 -f backend）
docker compose stop              # 停止（保留容器，start 可再次启动）
docker compose down              # 停止并删除容器（数据卷保留）
docker compose down -v           # 连数据卷一起删除（彻底重置，含数据库文件）
docker compose up -d --build     # 修改代码后重新构建并启动
```

说明：

- 健康检查：`docker compose ps` 中 db / backend / frontend 都应显示 `(healthy)`；
  db 未 healthy 前 backend 不会启动，backend 未 healthy 前 frontend 不会启动
  （`depends_on` 约束）。
- **数据持久化在 PostgreSQL**（`pgdata` 数据卷），重启容器不会丢数据。容器
  **不自动灌种子数据**。启动时 `python -m app.bootstrap_db` 会执行
  `alembic upgrade head` 建表/迁到最新 schema（v1 起为单条 `0001_initial`
  迁移；**旧版预发布数据卷需先 `docker compose down -v` 清空**）。首次或想
  重置演示数据时手动执行：

  ```bash
  docker compose exec backend python -m app.seed   # 全新库灌演示数据（已有库会重复灌入，先 down -v 删卷）
  ```

- PostgreSQL 发布在宿主机 **5432** 端口（仅绑定 `127.0.0.1` 回环接口，
  不对外网暴露），可用本机 psql / GUI 工具直连（用户名/库名见 `.env`）。
- ⚠️ **与本地开发模式互斥**：Docker 的后端也映射了 8001 端口。本地 uvicorn
  正在运行时 `docker compose up` 会端口绑定失败——先停掉本地服务，反之亦然。

## 页面

| 路由 | 用途 |
| --- | --- |
| `/login` | 邮箱注册 / 登录 |
| `/` | 首页仪表盘：统计、考试倒计时、最新动态、待跟进家访、快捷操作 |
| `/profile` | 个人中心：资料编辑、我的班级、教学足迹 |
| `/classes`、`/classes/:id` | 班级列表（新建/编辑/删除）与班级详情（趋势图/平均成绩/名单） |
| `/students`、`/students/new`、`/students/:id` | 学生列表、添加学生、学生工作台（成绩趋势/标签/事件/家访/时间线） |
| `/exams`、`/exams/new`、`/exams/:id` | 考试列表、新建考试、平均分与全校趋势图 |

界面语言为中文，文案集中维护在零依赖词典 `frontend/src/strings.js`。

### 版本号

用户界面显示的版本来自 `frontend/package.json` 的 `version` 字段（当前为测试版 **Beta**）。
发版时：

1. 修改 `frontend/package.json` 中的 `version`（遵循 [语义化版本](https://semver.org/lang/zh-CN/)）。
2. 同步更新 `backend/app/version.py` 中的 `APP_VERSION`（供 `/api/health` 与 OpenAPI 文档使用）。

## API

除 `/api/auth/*` 与 `/api/health` 外，所有接口需 `Authorization: Bearer <token>`。

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| POST | `/api/auth/register` | 邮箱注册（姓名、邮箱、密码） |
| POST | `/api/auth/login` | 邮箱 + 密码 → bearer token |
| POST | `/api/auth/logout` · GET `/api/auth/me` | 注销会话 · 当前教师 |
| GET | `/api/dashboard` · `/api/calendar` | 首页聚合（统计、 upcoming 考试、待跟进、最新事件） · 日历视图 |
| GET `/api/profile` · PATCH `/api/profile` | 教师资料（班级/学生/足迹） · 编辑姓名/手机号 |
| GET · POST | `/api/students` | 列表 · 新增（监护人电话必填） |
| GET | `/api/students/{id}` | 档案、成绩、跟进记录（家访来自 `Event` type=`home_visited`） |
| GET | `/api/students/{id}/timeline` | 时间线（最新在前，一切事件追加式写入 `event` 表） |
| GET · POST · DELETE | `/api/tags` · `/api/students/{id}/tags[/{tag_id}]` | 标签列表/新建 · 给学生打/摘标签 |
| GET · POST · PATCH · DELETE | `/api/students/{id}/events` · `/events/{eid}` | 事件记录（家访/谈心/辅导/家长沟通/备注/自定义）；系统事件不可编辑/不可删除 |
| GET | `/api/records` | 全部跟进记录（跨学生，最新在前） |
| PATCH | `/api/results/{id}` | 更正成绩（写入 `result_changed` 事件） |
| GET · POST | `/api/exams` | 考试列表 · 新建考试（同学年同名 → 409） |
| GET | `/api/exams/trend` | 各科全校平均分趋势（趋势图数据） |
| GET | `/api/exams/{id}/averages` | 全校 + 各班平均分 |
| GET | `/api/classes`、`/api/classes/{id}` | 班级列表 · 班级详情（趋势/平均/名单） |
| PATCH · DELETE | `/api/classes/{id}` | 编辑班级 · 删除（有学生记录 → 409） |
| GET | `/api/teachers` | 教师列表 |

所有查询均通过 SQLAlchemy 参数绑定（无字符串拼接 SQL）。密码使用
PBKDF2-HMAC-SHA256（20 万次迭代 + 每用户盐值）；token 为 `auth_session`
表中的服务端会话。

## 数据库设计

Schema 定义在 `backend/app/models/` 包（SQLAlchemy 2.0 声明式映射），共 **6 张表**
（person / event / tag / class / enrollment / auth_session，外加 person_events、
person_tags 两张多对多关联表），部署在 PostgreSQL（`docker compose` 中的 `db`
服务），本地开发可回退 SQLite。半结构化数据（角色档案、事件载荷）在
PostgreSQL 上落在 **JSONB** 列。

> 自 2026-09 起数据模型整体切换为**以事件为中心**的 schema：person 是唯一的
> 身份表（角色 student/teacher/admin 与角色专属档案都在 `person.payload`），
> 一切动态都是 Event 行（考试、成绩、家访、备注…），标签挂人，班级/在读保持
> 关系表。旧版列式 schema 已在 v1 发布前废弃；迁移历史已压成单条
> `0001_initial`。

### 实体关系总览

```
person ──< auth_session                登录会话（Bearer token，无过期时间）

person                                 唯一身份表：payload.role = student |
                                       teacher | admin；角色专属字段（学号、
                                       出生年月、监护人、任教学科…）都在 payload

teacher（班主任）──< class ═══< enrollment >═══ student（payload.role="student"）
                            时间维度：valid_from / valid_to
                            在读 = valid_to IS NULL（部分唯一索引）

event ──< person_events >── person       追加式时间线：type + title + start/end
                                         + payload JSONB；考试坐席（type="exam"）、
                                         单科成绩（type="score"）、家访/谈心/备注…
person ──< person_tags >── tag           学生标签（按约定仅学生挂标签）
```

### 关键设计

**1. `person.payload`：角色即数据形状。** 全系统只有一张身份表，角色
（student/teacher/admin）与该角色的全部档案字段都存在 payload JSONB 里，
由 `app/payloads.py` 的校验注册表统一把关（新增角色 = 新增一种 payload
形状 + 一条注册项，**无需 DDL**）。学生无邮箱/不登录，教师/管理员用
email + 密码登录。

**2. `enrollment`：带时间维度的班级归属。** 学生转班**从不修改旧记录**，
而是关闭旧行（写入 `valid_to`）并追加新行，因此 `enrollment` 本身就是完整
的转班历史。它支撑了"按考试当日所在班级归属"的统计：班级平均分的查询把
`Event.start_time`（考试日期）与 `enrollment` 的有效期做区间连接
（`valid_from <= day AND (valid_to IS NULL OR valid_to >= day)`），
学生转班后，历史成绩仍正确计入当时的班级。部分唯一索引
（`postgresql_where=valid_to IS NULL`）在数据库层面保证每名学生**至多一条**
在读记录。转班必须走"关旧开新"，直接 UPDATE 会破坏历史。

**3. `event`：一切动态皆事件（追加式）。** 入学、转班、考试坐席、每生每科
成绩、家访、谈心、备注——全部是 `event` 表里的行，经 `app/eventing.py` 的
`create_event`（payload 校验 + 关联出席人）统一写入。成绩是
`type="score"` 的事件（payload 带 subject / max_score / score，缺勤约定为
`{"absent": true}` 无 score 键），考试本身是 `type="exam"` 的事件
（payload.full_scores 带各科满分）；系统事件（enrolled / class_moved /
exam_taken / result_changed）由业务流程自动写入，教师手写事件见
`app/eventing.py` 的类型分组。时间线、日历、首页动态、跟进记录都直接查它。

**4. `tag` / `person_tags`：学生标签。** 标签全局唯一（名称可重复使用），
按约定只挂在学生身上；`person_tags` 关联表带双向索引。

**5. 约束与索引。** 业务唯一性大多下沉到数据库：同学年班级名唯一
（`uq_class_name_year`）、每人至多一条在读（`uq_one_current_enrollment`
部分唯一索引）、学号在学生 payload 上唯一（表达式唯一索引）。热点查询路径
都有索引：事件的 `(type, start_time)`、出席关联表 `(event_id)`、标签关联
`(tag_id)`；PostgreSQL 上 person.payload 与 event.payload 还有 GIN 索引，
支持 payload 包含查询。

**6. 内容即纯文本。** 姓名班级、家访摘要、备注、时间线 payload 全部
存纯中文文本；科目、状态等枚举值存代码（如 `math`），由前端字典渲染成中文。

### 建表与迁移

迁移工具为 **Alembic**（v1 起单条 `0001_initial`，从当前模型建表）。
部署入口是 `python -m app.bootstrap_db`，每次启动执行 `alembic upgrade head`。
本地 SQLite 开发库可跳过 Alembic——删掉文件重跑 `python -m app.seed`（内部
`create_all`）即可。

## 演示数据与故事线

种子数据包含 2 个班级、24 名学生、7 场考试（全科 9 科：6 场已出分 + 1 场
未开考）、每生每科的 score 事件、标签、家访与随笔等 100+ 条时间线事件。
推荐看：

- **林晓雨**（七年级1班）——数学薄弱；期中数学成绩有更正记录（`result_changed`
  事件），另有教师备注与家访。
- **王浩**——2026-03-01 由七年级2班转入七年级1班；平均分页按"考试当日所在
  班级"归属，所以两场考试都计入 7-1。

重置演示数据：本地模式先删除 `backend/teacher_workbench.db` 再跑
`python -m app.seed`（非全新库重跑会重复灌入）；Docker 模式先
`docker compose down -v` 删卷，重启后再执行
`docker compose exec backend python -m app.seed`。

## 项目结构

```
backend/
  app/
    database.py        # 引擎 + 会话（DATABASE_URL 优先，缺省 SQLite 文件）
    models/            # 事件中心 schema：Person(payload 角色) / Event / Tag / Class / Enrollment / AuthSession
    payloads.py        # 角色/事件 payload 的校验注册表
    eventing.py        # create_event：事件表唯一写入口
    security.py        # PBKDF2 密码哈希 / token
    deps.py            # get_current_person 鉴权依赖
    seed.py            # 确定性演示数据（建表 + 灌数据）
    bootstrap_db.py    # 部署入口：alembic upgrade head + 运行时数据修补
    main.py            # FastAPI 应用与路由装配
    alembic/           # 迁移链（v1：0001_initial）
    routers/
      auth.py          # 注册 / 登录 / 登出 / me
      students.py      # 学生、时间线、事件、标签、成绩更正
      classes.py       # 班级列表 / 详情 / 新建 / 编辑 / 删除
      exams.py         # 考试 + 平均分 + 趋势（按考试当日班级归属）
      dashboard.py     # 首页聚合 + 日历
      profile.py       # 教师资料
      misc.py          # 教师列表
frontend/
  src/
    views/             # 首页/登录/个人中心/学生/班级/考试各页面
    components/        # LineChart.vue（SVG 折线图）、Timeline.vue、Icon.vue（内联图标）
    strings.js         # 中文界面词典 + 枚举代码的中文标签/取色
    auth.js  api.js  router.js  style.css
backend/Dockerfile  frontend/Dockerfile  docker-compose.yml
docs/design.md
```

## 生产化说明

Docker 部署已使用 PostgreSQL 17（JSONB、部分唯一索引、事件索引均已生效）；
本地开发仍可用 SQLite，连接串由 `DATABASE_URL` 决定。数据库凭据统一放在
`.env`（已 gitignore / dockerignore，compose 从中读取；模板见 `.env.example`，
凭据仅在 pgdata 卷首次初始化时生效）。数据库迁移走 Alembic（`0001_initial`，
容器启动时 `python -m app.bootstrap_db` 自动 `upgrade head`）。接入生产前还需处理：
会话 token 无过期时间（需加过期与刷新机制）、CORS 允许任意来源（演示配置）、
更换 `.env` 中的弱演示密码并考虑接入密钥管理服务。
