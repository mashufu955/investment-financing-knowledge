# 投融资知识库管理平台

面向企业内部员工的投融资知识库管理平台，覆盖 **项目/标的库、融资需求、尽调、投决、投后与知识沉淀** 全流程。

> 本工程已按技能文档 `../skills/00 ~ 05` 完成 5 个模块的具体实现：01 投融资知识维护、02 组织与权限、03 AI 检索与问答鉴权、04 数据看板、05 知识沉淀与 FAQ 缓存。

## 交付形态

- `app/`：FastAPI 后端服务（含 5 模块的 service / API / core / utils 实现）
- `frontend/`：Vue 3 + Vite 前端（含登录、菜单、知识维护、AI 问答、看板、FAQ 审核与缺口列表）
- `docker-investment-financing/`：Docker Compose 一键编排（含 Dockerfile、deploy 启动脚本、compose 说明；配置统一读取根目录 `.env`）
- `database/init.sql`：MySQL 初始化脚本（含种子数据：团队、角色、用户、权限）
- `docs/api.md`：接口说明文档

## 技术栈

| 层 | 选型 |
| --- | --- |
| 后端 | Python 3.12 + FastAPI + SQLAlchemy + PyMySQL + python-jose + passlib |
| 前端 | Vue 3 + Vite + Vue Router + Pinia + Axios + markdown-it |
| 业务库 | MySQL 8 |
| 向量检索 | Milvus 2.4（ANN 向量检索，dims=1024）+ Elasticsearch 8（关键字 BM25） |
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
├── frontend/                 # Vue 3 前端
│   └── src/
│       ├── api/              # 接口封装（含 SSE 流式问答）
│       ├── router/           # 路由（含 meta.permission 守卫）
│       ├── store/            # Pinia 状态
│       ├── layout/           # 布局与按权限渲染动态菜单
│       ├── views/            # 页面
│       └── components/       # 组件（流式 Markdown / 引用卡片 / 权限缺失卡片 / 选择器）
│   ├── Dockerfile
│   └── nginx.conf
├── database/
│   └── init.sql              # MySQL 初始化脚本
├── deploy/
│   ├── prometheus.yml        # Prometheus 抓取配置
│   └── loki-config.yml       # Loki 日志配置
├── docs/
│   └── api.md                # 接口说明
├── docker-investment-financing/   # Docker Compose 编排目录
│   ├── docker-compose.yml    # 13 服务编排（配置插值读取根目录 .env）
│   ├── docker-compose.README.md   # Docker Compose 使用说明
│   ├── Dockerfile            # 后端镜像构建
│   ├── deploy.cmd            # Windows 启动入口（自动读取根目录 .env）
│   └── deploy.sh             # Bash 启动入口（自动读取根目录 .env）
└── ../skills/                # 技能文档（输入文档，保留在上级目录）
```

## 启动方式

### 启动顺序总览

1. 准备 MySQL（含 `database/init.sql` 初始化数据）
2. 启动 Redis、Milvus（含 etcd + MinIO）、Elasticsearch
3. 启动后端 FastAPI（默认 `http://localhost:8000`）
4. 启动前端 Vue（默认 `http://localhost:5173`，开发模式）

### 方式一：Docker Compose（推荐）

> 配置统一读取**项目根目录 `.env`**（含 LLM、数据库账号密码等），无需在 docker 目录另建 `.env`。

```bash
# 1. 进入项目根目录
cd investment-financing-knowledge

# 2. 进入 docker 编排目录
cd docker-investment-financing

# 3. 构建并启动全部服务（13 个容器：mysql / redis / elasticsearch / etcd / minio / milvus / prometheus / grafana / loki / backend / frontend）
#    deploy.cmd（Windows）/ deploy.sh（Bash）会自动携带 --env-file ../.env
deploy.cmd up -d --build
# 等价写法：docker compose --env-file ../.env up -d --build

# 4. 查看启动状态（等待 mysql / elasticsearch / milvus 的 healthcheck 通过）
deploy.cmd ps

# 5. 查看后端启动日志（可选）
deploy.cmd logs -f backend
```

启动完成后：

- 前端 Web：http://106.55.0.45:5173
- 后端 API：http://106.55.0.45:8000 （健康检查 `/health`）
- Grafana：http://106.55.0.45:3000 （默认 admin / admin）
- MinIO 控制台：http://106.55.0.45:9001

### 方式二：本地原生安装

> 后端代码已直接位于项目根目录的 `app/` 下，启动命令无需再 `cd backend/`。

```bash
# 1. 初始化数据库
mysql -u root -p < database/init.sql

# 2. 启动 Redis 7、Elasticsearch 8、Milvus（含 etcd + MinIO）（按官方文档安装）

# 3. 启动后端（在项目根目录 investment-financing-knowledge/ 下执行）
python -m venv .venv
source .venv/bin/activate          # Windows 使用 .venv\Scripts\activate
pip install -r requirements.txt
# 配置直接使用根目录 .env（本地开发时注意把 MYSQL_HOST / REDIS_URL / ES_HOSTS / MILVUS_HOST 改为 106.55.0.45，LLM 参数按需调整）
# 修改 .env 中的 MYSQL_HOST / REDIS_URL / ES_HOSTS / MILVUS_HOST / LLM_API_KEY
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 4. 新开终端，启动前端
cd frontend
npm install
npm run dev
```

### 登录验证

浏览器打开 http://106.55.0.45:5173，使用默认账号登录：

- 用户名：`admin`
- 密码：`admin123`

登录后进入数据看板，左侧菜单包含：项目文档导入、知识单元、团队/基金/项目范围、内部员工、角色权限、投融资智能问答、FAQ 审核、知识缺口。

### 常用运维命令

> 全部命令需在 `docker-investment-financing/` 目录下执行。

```bash
cd docker-investment-financing

docker compose logs -f backend        # 查看后端日志
docker compose restart backend       # 重启后端
docker compose down                  # 停止并移除容器（保留数据卷）
docker compose down -v               # 停止并清空数据卷
docker compose pull && docker compose up -d --build   # 升级重建
```

### 向量索引说明

- **Milvus** 承担向量存储与 ANN 检索：首次写入时自动创建集合 `if_knowledge_units`（`unit_id` 主键 + 1024 维向量 + 标量元数据，HNSW/COSINE 索引），无需手动建集合。
- **Elasticsearch** 保留标题/内容文本字段，用于关键字 BM25 检索（hybrid 召回的关键字路）。
- 若因 Milvus 故障导致「数据已入库但向量索引缺失」，恢复后可重建索引：

```bash
# 在 backend 容器内执行
python scripts/rebuild_vector_index.py                  # 重建 status=active
python scripts/rebuild_vector_index.py --status all     # 重建全部
python scripts/rebuild_vector_index.py --dry-run        # 仅统计数量
```

- 也可通过接口触发：`POST /api/knowledge/reindex`（后台异步，返回 `task_id` 轮询 `GET /api/knowledge/reindex/{task_id}`）。

## 默认账号

| 系统 | 用户名 | 密码 | 说明 |
| --- | --- | --- | --- |
| Web 平台 | `admin` | `admin123` | 系统管理员角色，可访问全部菜单 |
| Grafana 监控 | `admin` | `admin` | 通过 `GRAFANA_ADMIN_PASSWORD` 配置 |
| MinIO 控制台 | `minio` | `minio123` | 通过 `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` 配置 |