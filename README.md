# Teacher Workbench (MVP demo)

A school-management workbench for teachers: student profiles, exam scores with
**question-level drill-down**, per-knowledge-point **weakness tracking**, exam
**averages** (school-wide and per class), **home visits**, and a per-student
**timeline** of every event.

- **Backend**: Python 3.14 · FastAPI · SQLAlchemy 2（Docker 部署使用 PostgreSQL 17，本地开发默认 SQLite）
- **Frontend**: Vue 3 · Vite · vue-router（纯 CSS，无 UI 框架）

Design notes and schema rationale: [docs/design.md](docs/design.md)

## 启动与关闭

有两种运行方式：**本地开发模式**（前后端分开跑，改代码实时生效）和 **Docker 模式**
（一键构建，接近生产环境）。两者都占用 8001 端口，**不要同时运行**。

演示账号：`13800000001 / 123456`（陈老师）、`13800000002 / 123456`（赵老师），
也可以在登录页自行注册（邮箱选填）。

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

**重置演示数据**：停掉后端后重新执行 `./.venv/bin/python -m app.seed`
（会清空并重建所有表）。

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
  **不再自动灌种子数据**（旧版每次启动都会清库重建，对持久化数据库是灾难）。
  首次或想重置演示数据时手动执行：

  ```bash
  docker compose exec backend python -m app.seed   # 清空重建 + 灌入演示数据
  ```

- PostgreSQL 发布在宿主机 **5432** 端口，可用本地 psql /
  GUI 工具直连（用户名/库名见 `.env`）。
- ⚠️ **与本地开发模式互斥**：Docker 的后端也映射了 8001 端口。本地 uvicorn
  正在运行时 `docker compose up` 会端口绑定失败——先停掉本地服务，反之亦然。

## 页面

| 路由 | 用途 |
| --- | --- |
| `/login` | 手机号注册 / 登录（标签页切换） |
| `/` | 首页仪表盘：统计、考试倒计时、最新动态、待跟进家访、快捷操作 |
| `/profile` | 个人中心：资料编辑、我的班级、教学足迹 |
| `/classes`、`/classes/:id` | 班级列表（新建/编辑/删除）与班级详情（趋势图/平均成绩/名单） |
| `/students`、`/students/new`、`/students/:id` | 学生列表、添加学生、学生工作台（成绩趋势/薄弱项/错题/家访/时间线） |
| `/exams`、`/exams/new`、`/exams/:id` | 考试列表、新建考试、平均分与全校趋势图 |

界面语言为中文，文案集中维护在零依赖词典 `frontend/src/strings.js`。

## API

除 `/api/auth/*` 与 `/api/health` 外，所有接口需 `Authorization: Bearer <token>`。

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| POST | `/api/auth/register` | 手机号注册（姓名、手机号、密码，邮箱选填） |
| POST | `/api/auth/login` | 手机号 + 密码 → bearer token |
| POST | `/api/auth/logout` · GET `/api/auth/me` | 注销会话 · 当前教师 |
| GET | `/api/dashboard` | 首页聚合（统计、 upcoming 考试、待跟进、最新事件） |
| GET `/api/profile` · PATCH `/api/profile` | 教师资料（班级/学生/足迹） · 编辑姓名/邮箱/学科 |
| GET · POST | `/api/students` | 列表 · 新增（监护人电话必填） |
| GET | `/api/students/{id}` | 档案、成绩、家访记录 |
| GET | `/api/students/{id}/timeline` | 时间线（最新在前） |
| GET | `/api/students/{id}/weaknesses` | 知识点薄弱项汇总 |
| GET | `/api/students/{id}/failed-questions?subject=` | 错题明细 |
| POST | `/api/students/{id}/home-visits` | 记录家访（操作人 = 当前教师） |
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

Schema 定义在 `backend/app/models.py`（SQLAlchemy 2.0 声明式映射），共 **14 张表**，
部署在 PostgreSQL（`docker compose` 中的 `db` 服务），本地开发可回退 SQLite。
半结构化数据（逐题作答明细、时间线载荷）在 PostgreSQL 上落在 **JSONB** 列。

### 实体关系总览

```
teacher ──< auth_session                登录会话（Bearer token，无过期时间）

teacher（班主任）──< class ═══< enrollment >═══ student
                            时间维度：valid_from / valid_to
                            在读 = valid_to IS NULL（部分唯一索引）

exam ──< exam_subject（科目 / 满分）──< question（题号 / 题型 / 满分 / 知识点）
                                             │
knowledge_point（科目知识点，code 唯一）──────┘
                                             │
student ──< question_response           逐题作答：earned / is_correct / detail JSONB
student ──< student_weakness            student × knowledge_point 聚合（薄弱项）
student ──< home_visit                  家访：目的 / 摘要 / 是否需跟进 / 跟进备注
student ──< student_event               追加式时间线：event_type + occurred_at
                                        + payload JSONB + ref_table/ref_id 回指业务行
```

### 关键设计

**1. `enrollment`：带时间维度的选课/班级关系。** 这是整个系统最有价值的设计。
学生转班**从不修改旧记录**，而是关闭旧行（写入 `valid_to`）并追加新行，因此
`enrollment` 本身就是完整的转班历史。它支撑了"按考试当日所在班级归属"的统计：
班级平均分的查询把 `Exam.exam_date` 与 `enrollment` 的有效期做区间连接
（`valid_from <= exam_date AND (valid_to IS NULL OR valid_to >= exam_date)`），
学生转班后，历史成绩仍正确计入当时的班级。部分唯一索引
（`postgresql_where=valid_to IS NULL`）在数据库层面保证每名学生**至多一条**
在读记录。风险提示见 `docs/design.md` 的数据模型小节：转班必须走"关旧开新"，
直接 UPDATE 会破坏历史。

**2. `student_event`：追加式（append-only）时间线。** 每个业务写操作（入学、
转班、考试、成绩更正、薄弱项标记、家访、备注）在**同一个数据库事务**里额外
写入一条事件行（`backend/app/events.py` 的 `add_event`，见各 router）。
`payload`（JSONB）携带展示所需数据，`ref_table`/`ref_id` 回指业务行。
表只增不改，学生档案页的时间线和首页"最新动态"都直接查它，无需对账。

**3. 逐题成绩链路：`exam → exam_subject → question → question_response`。**
一场考试有若干科目（`exam_subject`，含满分），每个科目下挂具体题目，每题
标注知识点（`knowledge_point`，`code` 如 `MATH.G7.FRACTION.ADD`）。每名学生
每题一行作答（`question_response`：得分、是否正确、`detail` JSONB）。总分是
由逐题得分汇总出的 `exam_result`，因此"错题明细"可以下钻到题，薄弱项可以
归因到知识点。

**4. `student_weakness`：由作答推导的聚合表。** 按 student × knowledge_point
汇总答错次数（`evidence_count`）、尝试次数（`attempts`）、严重度
（`severity = evidence/attempts`）与状态（`open`/`resolved`），并记录首末出现
时间。它让"薄弱项"是一个**可查询的状态**而不是每次现算的报表。当前实现里
聚合由种子脚本推导；运行时成绩更正后实时重算（设计意图见 `docs/design.md`）
尚未接线，是已知的 MVP 简化。

**5. 约束与索引。** 业务唯一性大多下沉到数据库：同学年班级名唯一
（`uq_class_name_year`）、每生每科成绩唯一（`uq_result_per_subject`）、每生
每题作答唯一（`uq_response_per_question`）、每生每知识点薄弱项唯一
（`uq_weakness_per_kp`）；热点查询路径都有复合索引（时间线的
`(student_id, occurred_at)`、家访的 `(student_id, visited_at)` 等）。

**6. 内容即纯文本。** 姓名班级、知识点、家访摘要、备注、时间线 payload 全部
存纯中文文本（此前一版的双语 `{zh, en}` 约定已整体移除）；科目、题型、状态
等枚举值存代码（如 `math`、`choice`），由前端字典渲染成中文。

### 建表与迁移

应用启动时 `Base.metadata.create_all` 按 models.py 建表（幂等）。MVP 阶段没有
引入 Alembic：改模型后开发环境直接重跑 `python -m app.seed`（drop + create +
灌种子）即可；接入生产数据库后应引入迁移工具。

## 演示数据与故事线

种子数据包含 2 个班级、24 名学生、2 场考试（数学 + 英语，题目均挂知识点）、
全量逐题作答、推导出的薄弱项、家访记录与 100+ 条时间线事件。推荐看：

- **林晓雨**（七年级1班）——分数薄弱；期中数学成绩有更正记录（`result_changed`
  事件），另有教师备注与家访。
- **王浩**——2026-03-01 由七年级2班转入七年级1班；平均分页按"考试当日所在
  班级"归属，所以两场考试都计入 7-1。

重置演示数据：本地模式重跑 `python -m app.seed`；Docker 模式执行
`docker compose exec backend python -m app.seed`。

## 项目结构

```
backend/
  app/
    database.py        # 引擎 + 会话（DATABASE_URL 优先，缺省 SQLite 文件）
    models.py          # 14 张表，含时间维度的 enrollment 与追加式 student_event
    events.py          # 同事务写时间线事件的辅助函数
    security.py        # PBKDF2 密码哈希 / token
    deps.py            # get_current_teacher 鉴权依赖
    seed.py            # 确定性演示数据（建表 + 灌数据）
    main.py            # FastAPI 应用与路由装配
    routers/
      auth.py          # 注册 / 登录 / 登出 / me
      students.py      # 学生、时间线、薄弱项、家访、成绩更正
      classes.py       # 班级列表 / 详情 / 新建 / 编辑 / 删除
      exams.py         # 考试 + 平均分 + 趋势（按考试当日班级归属）
      dashboard.py     # 首页聚合
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
凭据仅在 pgdata 卷首次初始化时生效）。接入生产前还需处理：
会话 token 无过期时间（需加过期与刷新机制）、CORS 允许任意来源（演示配置）、
更换 `.env` 中的弱演示密码并考虑接入密钥管理服务，以及引入 Alembic 做增量
迁移（当前无迁移工具）。
