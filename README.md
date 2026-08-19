# 投融资知识库管理平台

面向企业内部员工的投融资知识库管理平台，覆盖 **项目/标的库、融资需求、尽调、投决、投后与知识沉淀** 全流程。

> 本工程已按技能文档 `../skills/00 ~ 05` 完成 5 个模块的具体实现：01 投融资知识维护、02 组织与权限、03 AI 检索与问答鉴权、04 数据看板、05 知识沉淀与 FAQ 缓存。

## 交付形态

- `app/`：FastAPI 后端服务（含 5 模块的 service / API / core / utils 实现）
- `frontend/`：Vue 3 + Vite 前端（含登录、菜单、知识维护、AI 问答、看板、FAQ 审核与缺口列表）
- `docker-investment-financing/`：Docker Compose 编排后端依赖（mysql / redis / elasticsearch / backend，含 Dockerfile、deploy 启动脚本；配置统一读取根目录 `.env`，部署详解见「Docker Compose 部署详解」）
- `database/init.sql`：MySQL 初始化脚本（含种子数据：团队、角色、用户、权限）
- `scripts/seed_demo.py`：演示/测试数据脚本（幂等、可本地/云端通用，一键生成/清空演示数据，支持仅清空不重建）
- `scripts/rebuild_vector_index.py`：向量索引重建脚本（Milvus + ES，支持按状态 / 索引状态 / 批次重建）
- `docs/api.md`：接口说明文档
- `docs/project_overview.md`：项目技术讲解（架构、功能流程、已知不足与演进路线）

## 技术栈

| 层 | 选型 |
| --- | --- |
| 后端 | Python 3.12 + FastAPI + SQLAlchemy + PyMySQL + python-jose + passlib |
| 前端 | Vue 3 + Vite + Vue Router + Pinia + Axios + markdown-it |
| 业务库 | MySQL 8 |
| 向量检索 | Milvus 2.4 / Milvus Lite（ANN 向量检索，dims=1024）+ Elasticsearch 8（关键字 BM25） |
| 缓存 | Redis（FAQ 缓存 / 看板聚合缓存） |
| 鉴权 | JWT + RBAC + 四维数据权限（global/department/role/user） |

## 模块划分（对应技能文档）

| 模块 | 技能 | 实现范围 |
| --- | --- | --- |
| 01 投融资知识维护 | `../skills/01` | 文档导入（PDF/MD/Word/TXT）、解析、Markdown 标题+长度切片、项目/融资字段抽取（含归一化、校验）、知识单元 CRUD、版本/状态管理、向量化同步 |
| 02 组织与权限 | `../skills/02` | 登录认证、JWT 签发与校验、RBAC 操作权限（菜单/按钮）、团队/基金/项目范围树、员工 CRUD、角色与权限分配、四维数据权限配置与批量校验 |
| 03 AI 检索与问答鉴权 | `../skills/03` | 会话管理、向量+关键字混合召回、按行业/轮次/阶段过滤、四维权限过滤后组装 Prompt、SSE 流式问答、引用卡片、权限缺失提示、qa_trace 全链路追踪 |
| 04 数据看板 | `../skills/04` | 访问日志异步记录、项目阶段漏斗、币种折算 CNY、行业分布、阶段转化率、问题 TOP、单元 TOP、Token 趋势、FAQ 命中率、看板聚合缓存 |
| 05 知识沉淀与 FAQ 缓存 | `../skills/05` | 历史问题频次挖掘与 FAQ 推荐、审核发布（approve/reject）、Redis 缓存 + 版本号、语义匹配（阈值 0.85/0.98）、命中追踪、知识缺口识别 |

## 目录结构

```
investment-financing-knowledge/   # 项目根目录
├── app/                      # FastAPI 后端（直接位于项目根）
│   ├── main.py               # 应用入口（注册全部路由）
│   ├── config.py             # 配置
│   ├── core/                 # 基础设施（DB/ES/Milvus/Redis/JWT/权限）
│   ├── models/               # ORM 模型
│   ├── schemas/              # 请求/响应模型
│   ├── api/                  # 路由层
│   ├── services/             # 服务层（对应技能函数实现）
│   └── utils/                # 工具（解析/切片/向量化）
├── requirements.txt          # 后端 Python 依赖
├── .env                      # 项目统一配置来源（本地开发 + Docker 部署共用）
├── frontend/                 # Vue 3 前端（npm run dev 启动，不再由 Docker 编排）
│   └── src/
│       ├── api/              # 接口封装（含 SSE 流式问答）
│       ├── router/           # 路由（含 meta.permission 守卫）
│       ├── store/            # Pinia 状态
│       ├── layout/           # 布局与按权限渲染动态菜单
│       ├── views/            # 页面
│       └── components/       # 组件（流式 Markdown / 引用卡片 / 权限缺失卡片 / 选择器）
│   ├── Dockerfile            # 可选：手动构建前端镜像时使用（compose 已不编排前端）
│   └── nginx.conf            # 可选：前端反向代理配置参考
├── database/
│   └── init.sql              # MySQL 初始化脚本
├── deploy/
│   ├── prometheus.yml        # Prometheus 抓取配置
│   └── loki-config.yml       # Loki 日志配置
├── docs/
│   ├── api.md               # 接口说明
│   └── project_overview.md  # 项目技术讲解（架构/流程/不足与演进）
├── scripts/
│   ├── seed_demo.py             # 演示数据生成（一键清空 + 重建，幂等）
│   └── rebuild_vector_index.py  # 向量索引重建（Milvus + ES BM25）
├── docker-investment-financing/   # Docker Compose 编排目录
│   ├── docker-compose.yml    # 4 服务编排（mysql/redis/elasticsearch/backend；前端改由 npm run dev 启动；监控栈默认关闭，需 --profile monitoring 启动；配置插值读取根目录 .env）
│   ├── Dockerfile            # 后端镜像构建
│   ├── deploy.cmd            # Windows 启动入口（自动读取根目录 .env）
│   └── deploy.sh             # Bash 启动入口（自动读取根目录 .env）
└── ../skills/                # 技能文档（输入文档，保留在上级目录）
```

## 启动方式

### 启动顺序总览

1. 准备 MySQL（含 `database/init.sql` 初始化数据）
2. 启动 Redis、Elasticsearch（向量检索默认使用嵌入式 Milvus Lite）
3. 启动后端 FastAPI（默认 `http://localhost:8000`，推荐用 Docker Compose 编排）
4. 启动前端 Vue：`npm run dev` 启动 Vite 开发服务器，访问 `http://localhost:5173`（带热更新，`/api` 已反代到 `127.0.0.1:8000`）

> **前端不再由 Docker 构建/托管**：镜像构建与依赖拉取较慢，现统一通过 `npm run dev` 在宿主机启动 Vite 开发服务器（`frontend/vite.config.js` 已配置 `/api` 代理到后端 `8000`）。后端仍由 Docker Compose 编排（mysql / redis / elasticsearch / backend），也可按「方式二」本地原生运行。

### 方式一：Docker Compose 后端 + npm run dev 前端（推荐）

#### 本地电脑

```bash
# 终端 1：启动后端（4 个容器：mysql / redis / elasticsearch / backend；监控栈默认关闭）
cd investment-financing-knowledge/docker-investment-financing

# 构建并启动（deploy.cmd（Windows）/ deploy.sh（Bash）会自动携带 --env-file ../.env）
deploy.cmd up -d --build
# Linux / macOS 用：./deploy.sh up -d --build
# 等价写法：docker compose --env-file ../.env up -d --build

# 查看启动状态（等待 mysql / redis / elasticsearch / backend 的 healthcheck 通过）
deploy.cmd ps

# 终端 2：启动前端（首次先安装依赖）
cd investment-financing-knowledge/frontend
npm install
npm run dev
```

启动完成后：

- 前端 Web：**http://localhost:5173**（Vite 开发服务器，`/api` 已反代到后端）
- 后端 API：http://localhost:8000 （健康检查 `/health`）
- Grafana：http://localhost:3000 （仅 `--profile monitoring` 启动时可用，默认 admin / 对应 `GRAFANA_ADMIN_PASSWORD`）

#### 云服务器

```bash
# 1. 克隆代码到服务器，配置根目录 .env（LLM / Embedding Key、SECRET_KEY 等）

# 终端 1：启动后端（Docker Compose）
cd investment-financing-knowledge/docker-investment-financing
./deploy.sh up -d --build         # Windows 服务器用 deploy.cmd
./deploy.sh ps                    # 等待 mysql / redis / elasticsearch / backend healthy

# 终端 2：启动前端（--host 0.0.0.0 对外监听，供浏览器访问）
cd investment-financing-knowledge/frontend
npm install
npm run dev -- --host 0.0.0.0
```

- 浏览器访问 **http://<云服务器公网IP>:5173**（安全组 / 防火墙需放行 TCP 5173）；
- 前端 `/api` 由 Vite 代理到本机 `127.0.0.1:8000`，浏览器侧为同源请求，无需额外配置 CORS；若需要直连后端 API（不经代理），请在根目录 `.env` 的 `CORS_ORIGINS` 中追加前端访问地址后重启 backend；
- 生产长期运行建议在 5173 前加 Nginx / Caddy 反代到 80/443（`frontend/nginx.conf` 可作参考），或 `npm run build` 后托管 `frontend/dist` 静态产物。

### Docker Compose 部署详解

> 以下为 `docker-investment-financing/` 编排的详细说明（服务清单、配置、端口、初始化、路径映射、数据卷）。编排文件通过 `--env-file ../.env` 读取根目录配置，修改 `.env` 后 `docker compose up -d` 即可生效。

#### 服务清单（4C4G 云服务器优化版）

默认启动 **4 个服务**：MySQL、Redis、Elasticsearch、后端（FastAPI）。前端不再由 Docker 构建/托管（镜像构建与依赖拉取较慢），统一使用 `npm run dev` 启动 Vite 开发服务器（见「启动方式」）。

- 向量检索：**Milvus Lite（嵌入式）**，随 backend 容器运行，数据文件 `/app/data/milvus.db`（命名卷 `backend_milvus` 持久化），不再需要 milvus / etcd / minio 三个独立容器；
- embedding：**OpenAI 兼容网关（SiliconFlow /v1/embeddings）**，默认模型 `BAAI/bge-m3`（1024 维，与 Milvus 集合一致），本地不加载模型权重；
- 监控栈（Prometheus + Grafana + Loki）：**默认关闭**，需要时：

```bash
docker compose --env-file ../.env --profile monitoring up -d
```

#### 配置来源

项目所有配置统一集中在**根目录 `.env`**，包括 LLM / Embedding、MySQL/Redis/ES 账号密码与容器内部服务主机名等。`docker-compose.yml` 内全部变量通过 `--env-file ../.env` 插值读取。修改根目录 `.env` 后执行 `docker compose up -d` 即可生效。

> 生产上线前必须：把 `.env` 中的 `EMBEDDING_API_KEY` 换成真实 SiliconFlow 密钥、修改 `SECRET_KEY`、轮换 LLM API Key，且不要把 `.env` 提交到 git。

#### 端口对照

| 服务 | 宿主机端口 | 用途 |
| --- | --- | --- |
| Frontend (Vite dev) | 5173 | 前端开发服务器（`npm run dev`，`/api` 反代到 8000） |
| Backend (FastAPI) | 127.0.0.1:8000 | 后端 API（前端经 Vite 代理访问） |
| MySQL | 127.0.0.1:3306 | 仅本机调试 |
| Redis | 127.0.0.1:6379 | 仅本机调试 |
| Elasticsearch | 127.0.0.1:9200 | 仅本机调试 |
| Prometheus / Grafana / Loki | 127.0.0.1:9090 / 3000 / 3100 | 仅 `--profile monitoring` 时启动 |

> **前端访问端口说明**：前端统一由 `npm run dev` 启动 Vite 开发服务器，入口为 **`http://localhost:5173`**（云服务器为 `http://<公网IP>:5173`）。`frontend/vite.config.js` 已配置 `/api` 代理到 `127.0.0.1:8000`，后端服务可通过 Docker Compose（方式一）或本地原生（方式二）方式启动。

#### 初始化数据加载

MySQL 容器启动时会自动执行项目根目录下的 `database/init.sql`（compose 中通过 `../database/init.sql:/docker-entrypoint-initdb.d/01-init.sql:ro` 挂载），包含：

- 12 张表（users / departments / roles / user_roles / role_permissions / knowledge_units / unit_permissions / qa_sessions / qa_messages / qa_access_logs / faqs / knowledge_gaps）
- 3 个团队节点、8 个角色、1 个管理员用户

> 向量化由 SiliconFlow API 完成，不依赖 Elasticsearch 推理端点。

#### 关键路径映射

| 用途 | 宿主机路径（项目根） | 容器内路径 | 备注 |
| --- | --- | --- | --- |
| 后端代码 | `./app/` | `/app/app/` | compose `context: ..` + `dockerfile: docker-investment-financing/Dockerfile` |
| 后端 requirements | `./requirements.txt` | `/app/requirements.txt` | 镜像构建阶段安装依赖 |
| MySQL 初始化 | `./database/init.sql` | `/docker-entrypoint-initdb.d/01-init.sql` | 只读挂载，首次启动自动执行 |
| Milvus Lite 数据 | 命名卷 `backend_milvus` | `/app/data/milvus.db` | 向量数据单文件，备份即拷贝该卷 |
| Prometheus 配置 | `./deploy/prometheus.yml` | `/etc/prometheus/prometheus.yml` | 只读挂载，仅监控 profile |
| Loki 配置 | `./deploy/loki-config.yml` | `/etc/loki/loki-config.yml` | 只读挂载，仅监控 profile |
| 后端上传目录 | 命名卷 `backend_uploads` | `/app/uploads` | 用户上传文档持久化 |

> 前端不进入容器：`./frontend/` 直接在宿主机以 `npm run dev` 运行（`frontend/Dockerfile` 与 `nginx.conf` 保留，仅供需要手动构建前端镜像 / 反向代理时参考）。

#### 数据卷命名

| 数据卷 | 所属服务 | 用途 |
| --- | --- | --- |
| `mysql_data` | mysql | 数据库文件 |
| `redis_data` | redis | 缓存数据 |
| `es_data` | elasticsearch | ES 索引数据 |
| `backend_milvus` | backend | Milvus Lite 向量数据（单文件） |
| `backend_uploads` | backend | 用户上传文件 |
| `prometheus_data` / `grafana_data` / `loki_data` | 监控 profile | 监控数据 |

### 方式二：本地原生安装（不使用 Docker）

> 后端代码已直接位于项目根目录的 `app/` 下，启动命令无需再 `cd backend/`。

```bash
# 1. 初始化数据库
mysql -u root -p < database/init.sql

# 2. 启动 Redis 7、Elasticsearch 8（按官方文档安装；向量库可设 MILVUS_LITE_URI 使用 Milvus Lite，无需 etcd/MinIO）

# 3. 启动后端（在项目根目录 investment-financing-knowledge/ 下执行）
python -m venv .venv
source .venv/bin/activate          # Windows 使用 .venv\Scripts\activate
pip install -r requirements.txt
# 配置直接使用根目录 .env（Docker Compose 模式保持 mysql/redis/elasticsearch/milvus 服务名；本地原生模式把 MYSQL_HOST / REDIS_URL / ES_HOSTS / MILVUS_HOST 改为 127.0.0.1，LLM 参数按需调整）
# 修改 .env 中的 MYSQL_HOST / REDIS_URL / ES_HOSTS / MILVUS_HOST / LLM_API_KEY
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 4. 新开终端，启动前端
cd frontend
npm install
npm run dev
```

> 云服务器原生部署时，后端 `uvicorn` 已使用 `--host 0.0.0.0`；前端改为 `npm run dev -- --host 0.0.0.0`，并在安全组 / 防火墙放行 TCP 5173（或前置 Nginx 反代到 80/443）。

### 登录验证

浏览器打开前端地址（本地 `http://localhost:5173`，云服务器 `http://<公网IP>:5173`）后，使用默认账号登录：

- 用户名：`admin`
- 密码：`admin123`

登录后进入数据看板，左侧菜单包含：项目文档导入、知识单元、团队/基金/项目范围、内部员工、角色权限、投融资智能问答、FAQ 审核、知识缺口。

### 常用运维命令

> 全部命令需在 `docker-investment-financing/` 目录下执行（仅涉及后端容器 mysql / redis / elasticsearch / backend；前端无容器）。`deploy.cmd`（Windows）/ `deploy.sh`（Bash）等价于 `docker compose --env-file ../.env`，可替换下方命令。

```bash
cd docker-investment-financing

docker compose logs -f backend        # 查看后端日志
docker compose restart backend       # 重启后端
docker compose down                  # 停止并移除容器（保留数据卷）
docker compose down -v               # 停止并清空数据卷
docker compose pull && docker compose up -d --build   # 升级重建
```

### 向量索引说明

- **Milvus / Milvus Lite** 承担向量存储与 ANN 检索：首次写入时自动创建集合 `if_knowledge_units`（`unit_id` 主键 + 1024 维向量 + 标量元数据，HNSW/COSINE 索引），无需手动建集合；Docker 部署默认使用嵌入式 Milvus Lite（数据文件见「服务清单」）。
- **Elasticsearch** 保留标题/内容文本字段，用于关键字 BM25 检索（hybrid 召回的关键字路）。
- 若因 Milvus 故障导致「数据已入库但向量索引缺失」，恢复后可重建索引：

```bash
# 在 backend 容器内执行（docker compose --env-file ../.env exec backend python scripts/rebuild_vector_index.py [选项]）
python scripts/rebuild_vector_index.py                     # 重建 status=active 的单元（默认）
python scripts/rebuild_vector_index.py --status all        # 重建全部（不过滤状态）
python scripts/rebuild_vector_index.py --status draft      # 仅重建 draft
python scripts/rebuild_vector_index.py --batch-size 16     # 自定义向量化批次大小
python scripts/rebuild_vector_index.py --dry-run           # 仅统计数量，不写索引
python scripts/rebuild_vector_index.py --index-status failed  # 仅重建索引状态为 failed 的单元
```

- 也可通过接口触发：`POST /api/knowledge/reindex`（后台异步，返回 `task_id` 轮询 `GET /api/knowledge/reindex/{task_id}`）。

## 演示数据生成与一键清空（测试/演示环境）

> ⚠️ **脚本会 `TRUNCATE` 清空 12 张业务表（含 `users` / `departments` / `roles` / `knowledge_units` 等），默认清空后整体重建，加 `--clear-only` 则仅清空不重建**，仅用于本地或云端测试/演示环境。生产数据请勿执行。

`scripts/seed_demo.py` 是一键生成覆盖全业务场景**演示文本/数据**的**幂等**脚本（先清空 12 张业务表，再整体重建），本地与云端通用，便于你上传云服务器后再次测试。

### 数据规模与覆盖

- **组织与人员**：13 个用户、12 个部门、8 个角色（含 RBAC 操作权限、多角色、停用账号等边界）
- **知识单元**：30 条，覆盖 10 个行业、9 种轮次（英文枚举）、4 种币种、5 级保密、3 种状态、5 个阶段
- **数据权限**：43 条四维权限规则（`global` / `department` / `role` / `user` 全组合，含「最高保密仅个人可见」「权限缺失拦截」演示）
- **AI 问答与看板**：6 个会话、32 条访问日志（含近 7 天趋势、极快/极慢响应、权限缺失拦截记录）
- **知识沉淀**：10 条 FAQ（含重复触发自动挖掘）、10 条知识缺口

数据写入遵循项目规范：行业一律中文规范名、轮次一律英文枚举、编号 `YYYYMMDD`+序号，并自动调用 `normalize_industry` / `normalize_round`。

### 运行方式（本地 / 云端同套）

> 镜像中的 `app/scripts/` 是构建时 `COPY` 的版本：脚本有更新时，可先 `docker compose --env-file ../.env build backend` 重新构建镜像，或临时用 `docker cp` 覆盖（重建镜像后失效）。

```bash
cd docker-investment-financing

# 1.（可选）不重建镜像时，把最新脚本临时送入 backend 容器
docker cp ../scripts/seed_demo.py ifk-backend:/app/scripts/seed_demo.py

# 2a. 仅造数据（不依赖 embedding 网关，最快验证数据层）
docker compose --env-file ../.env exec backend python scripts/seed_demo.py --yes --no-index

# 2b. 全量（含 Milvus / ES 向量索引重建，需配置 EMBEDDING_API_KEY）
docker compose --env-file ../.env exec backend python scripts/seed_demo.py --yes

# 2c. 仅清空演示数据（不重建）
docker compose --env-file ../.env exec backend python scripts/seed_demo.py --yes --clear-only
```

### 一键清空

- **仅清空演示数据（不重建）**：在 backend 容器内执行 `python scripts/seed_demo.py --yes --clear-only`，只 `TRUNCATE` 清空 12 张业务表，不生成任何演示数据；
- **清空并重建演示文本**：直接执行 `python scripts/seed_demo.py --yes`，脚本先 `TRUNCATE` 清空 12 张业务表，再整体重建演示数据，一步完成；
- **彻底清空（连数据卷一起删除）**：在 `docker-investment-financing/` 下执行 `docker compose --env-file ../.env down -v`，同时删除 MySQL / Redis / ES / Milvus / 上传文件等全部数据卷；下次 `up -d --build` 时 `database/init.sql` 会自动重新初始化种子数据。

### 参数说明

| 参数 | 说明 |
| --- | --- |
| `--yes` | 必须显式传入才执行清空（安全确认）；默认清空后整体重建，仅清空加 `--clear-only` |
| `--no-index` | 跳过向量/ES 索引重建，仅生成数据库数据（无需 embedding 网关） |
| `--emit-docs` | 额外把源文档导出到 `uploads/demo_sources`，供前端导入流程测试 |
| `--clear-only` | 仅清空 12 张业务表，不生成演示数据（需与 `--yes` 搭配） |

### 注意事项

- 索引重建失败（如未配置 `EMBEDDING_API_KEY`）会被脚本优雅兜底：**数据照常入库，仅索引标记失败**。此时 MySQL 关键字检索、前端看板/权限/FAQ 功能正常，仅 AI 语义检索暂不可用。
- 补索引的两种方式：① 配置 `EMBEDDING_API_KEY` 后重跑全量；② 不动数据，仅调 `POST /api/knowledge/reindex` 或容器内 `python scripts/rebuild_vector_index.py`。
- 演示管理员账号：`admin / admin123`（脚本会重置）。

## 默认账号

| 系统 | 用户名 | 密码 | 说明 |
| --- | --- | --- | --- |
| Web 平台 | `admin` | `admin123` | 系统管理员角色，可访问全部菜单 |
| Grafana 监控 | `admin` | `admin` | 仅 `--profile monitoring` 启动时可用，密码由 `GRAFANA_ADMIN_PASSWORD` 配置 |
