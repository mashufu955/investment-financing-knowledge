# Docker Compose 一键部署

本目录 `docker-investment-financing/` 集中管理项目的容器化编排，包含 13 个服务：MySQL、Redis、Elasticsearch、etcd、MinIO、Milvus、Prometheus、Grafana、Loki、后端（FastAPI）、前端（Nginx）。

> 后端代码位于项目根目录的 `app/` 下，前端代码位于项目根目录的 `frontend/` 下，编排文件位于 `docker-investment-financing/`，三者均为 `docker-compose.yml` 的相对路径引用。

## 配置来源

> 项目所有配置统一集中在**根目录 `.env`**（`investment-financing-knowledge/.env`），包括 LLM、MySQL/Redis/ES/MinIO 账号密码与容器内部服务主机名等。docker 部署同样以它为准，`docker-compose.yml` 内全部变量通过 `--env-file ../.env` 插值读取。**修改根目录 `.env` 后执行 `docker compose up -d` 即可生效**（无需改任何其他配置文件）。

## 启动

```bash
# 1. 进入 docker 编排目录
cd docker-investment-financing

# 2. 启动全部服务（推荐用包装脚本，自动读取根目录 .env）
deploy.cmd up -d --build        # Windows CMD / PowerShell
# 或：docker compose --env-file ../.env up -d --build

# 3. 查看启动状态（等待 mysql / elasticsearch / milvus 的 healthcheck 通过）
deploy.cmd ps                   # 或 docker compose --env-file ../.env ps
```

## 端口对照

| 服务 | 宿主机端口 | 用途 |
| --- | --- | --- |
| Frontend (Nginx) | 5173 | Web 入口，浏览器打开 http://106.55.0.45:5173 |
| Backend (FastAPI) | 8000 | API 入口（http://106.55.0.45:8000/health 健康检查） |
| MySQL | 3306 | 业务数据库 |
| Redis | 6379 | FAQ 缓存 / 看板聚合缓存 |
| Elasticsearch | 9200 | 文本检索 + 推理 |
| Milvus | 19530 / 9091 | 向量数据库 |
| MinIO | 9000 / 9001 | 对象存储（控制台 http://106.55.0.45:9001） |
| Prometheus | 9090 | 指标采集 |
| Grafana | 3000 | 监控面板（默认 admin / admin） |
| Loki | 3100 | 日志聚合 |

## 默认账号

- Web 登录：admin / admin123
- Grafana：admin / admin（`GRAFANA_ADMIN_PASSWORD`）
- MinIO 控制台：minio / minio123（`MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD`）

## 常用命令

> 全部命令需在 `docker-investment-financing/` 目录下执行，`deploy.cmd` / `deploy.sh` 等价于 `docker compose --env-file ../.env`。

```bash
deploy.cmd logs -f backend                  # 查看后端日志
deploy.cmd restart backend                  # 重启后端
deploy.cmd down                             # 停止并移除容器（保留数据卷）
deploy.cmd down -v                          # 停止并清空数据卷
deploy.cmd pull && deploy.cmd up -d --build # 升级重建
```

## 初始化数据加载

MySQL 容器启动时会自动执行项目根目录下的 `database/init.sql`（compose 中通过 `../database/init.sql:/docker-entrypoint-initdb.d/01-init.sql:ro` 挂载），包含：

- 12 张表（users / departments / roles / user_roles / role_permissions / knowledge_units / unit_permissions / qa_sessions / qa_messages / qa_access_logs / faqs / knowledge_gaps）
- 3 个团队节点、8 个角色、1 个管理员用户

首次启动 Elasticsearch 后需手动创建 Embedding inference endpoint（用于 BGE-M3 向量化）：

```bash
curl -X PUT "http://106.55.0.45:9200/_inference/text_embedding/bge-m3" \
  -H "Content-Type: application/json" \
  -d '{
    "service": "elasticsearch",
    "service_settings": {
      "model_id": ".multilingual-e5-small",
      "num_allocations": 1,
      "num_threads": 1
    }
  }'
```

## 关键路径映射

| 用途 | 宿主机路径（项目根） | 容器内路径 | 备注 |
| --- | --- | --- | --- |
| 后端代码 | `./app/` | `/app/app/` | compose `context: ..` + `dockerfile: docker-investment-financing/Dockerfile` |
| 后端 requirements | `./requirements.txt` | `/app/requirements.txt` | 镜像构建阶段安装依赖 |
| 前端代码 | `./frontend/` | `/usr/share/nginx/html`（构建）+ Nginx 反向代理 | `frontend/Dockerfile` Node 20 构建 → Nginx 1.25 |
| MySQL 初始化 | `./database/init.sql` | `/docker-entrypoint-initdb.d/01-init.sql` | 只读挂载，首次启动自动执行 |
| Prometheus 配置 | `./deploy/prometheus.yml` | `/etc/prometheus/prometheus.yml` | 只读挂载 |
| Loki 配置 | `./deploy/loki-config.yml` | `/etc/loki/loki-config.yml` | 只读挂载 |
| 后端上传目录 | 命名卷 `backend_uploads` | `/app/uploads` | 用户上传文档持久化 |

## 数据卷命名

| 数据卷 | 所属服务 | 用途 |
| --- | --- | --- |
| `mysql_data` | mysql | 数据库文件 |
| `redis_data` | redis | 缓存数据 |
| `es_data` | elasticsearch | ES 索引数据 |
| `etcd_data` | etcd | Milvus 元数据 |
| `minio_data` | minio | MinIO 对象 |
| `milvus_data` | milvus | Milvus 向量数据 |
| `prometheus_data` | prometheus | 指标历史 |
| `grafana_data` | grafana | 仪表盘配置 |
| `loki_data` | loki | 日志数据 |
| `backend_uploads` | backend | 用户上传文件 |