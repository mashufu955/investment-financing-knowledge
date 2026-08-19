# Docker Compose 部署（后端依赖）

本目录 `docker-investment-financing/` 集中管理项目的容器化编排，默认启动 **4 个服务**（前端不再由 Docker 构建/托管，统一用 `npm run dev` 启动 Vite 开发服务器，完整流程见项目根 README.md）：

| 服务 | 镜像 | 宿主机端口 | 用途 |
| --- | --- | --- | --- |
| mysql | mysql:8.0 | 3306 | 业务数据库（首次启动自动执行 `database/init.sql`） |
| redis | redis:7-alpine | 6379 | FAQ / 看板聚合缓存 |
| elasticsearch | elasticsearch:8.13.4 | 9200 | 关键字 BM25 检索 |
| backend | 自建 `ifk-backend:latest` | 8000 | FastAPI 后端（健康检查 `/health`） |

向量存储使用**嵌入式 Milvus Lite**（backend 容器内 `/app/data/milvus.db`，命名卷 `backend_milvus` 持久化），不再需要 milvus / etcd / minio 独立容器。Embedding 默认走 OpenAI 兼容网关（SiliconFlow），本地不加载模型权重。

监控栈（Prometheus + Grafana + Loki）默认关闭，需要时通过 `--profile monitoring` 启动。

## 配置来源

所有配置统一集中在**项目根目录 `.env`**（`investment-financing-knowledge/.env`）。`docker-compose.yml` 内全部变量通过 `--env-file ../.env` 插值读取，**修改根目录 `.env` 后执行 `docker compose up -d` 即可生效**。

## 启动

```bash
# 1. 进入 docker 编排目录
cd docker-investment-financing

# 2. 构建并启动后端依赖服务（推荐用包装脚本，自动读取根目录 .env）
deploy.cmd up -d --build        # Windows CMD / PowerShell
./deploy.sh up -d --build       # Linux / macOS
# 等价写法：docker compose --env-file ../.env up -d --build

# 3. 另开终端，用 npm run dev 启动前端（前端不再由 Docker 托管）
cd ../frontend
npm install                     # 首次执行
npm run dev                     # 本地访问 http://localhost:5173
                                # 云服务器对外访问：npm run dev -- --host 0.0.0.0

# 4. 查看后端启动状态（等待 mysql / redis / elasticsearch / backend 的 healthcheck 通过）
deploy.cmd ps

# 可选：启动监控栈
docker compose --env-file ../.env --profile monitoring up -d
```

启动完成后：

- 前端 Web：**http://localhost:5173**（Vite 开发服务器，`/api` 自动反代到 `127.0.0.1:8000`）
- 后端 API：http://localhost:8000 （健康检查 `/health`）
- Grafana：http://localhost:3000 （仅 `--profile monitoring` 启动时可用，默认 admin / `GRAFANA_ADMIN_PASSWORD`）

## 常用命令

> 全部命令需在 `docker-investment-financing/` 目录下执行，`deploy.cmd` / `deploy.sh` 等价于 `docker compose --env-file ../.env`。

```bash
deploy.cmd logs -f backend                  # 查看后端日志
deploy.cmd restart backend                  # 重启后端
deploy.cmd down                             # 停止并移除容器（保留数据卷）
deploy.cmd down -v                          # 停止并清空数据卷
deploy.cmd pull && deploy.cmd up -d --build # 升级重建
```

## 关键路径映射

| 用途 | 宿主机路径（项目根） | 容器内路径 | 备注 |
| --- | --- | --- | --- |
| 后端代码 | `./app/` | `/app/app/` | compose `context: ..` + `dockerfile: docker-investment-financing/Dockerfile` |
| 后端 requirements | `./requirements.txt` | `/app/requirements.txt` | 镜像构建阶段安装依赖 |
| MySQL 初始化 | `./database/init.sql` | `/docker-entrypoint-initdb.d/01-init.sql` | 只读挂载，首次启动自动执行 |
| Milvus Lite 数据 | 命名卷 `backend_milvus` | `/app/data/milvus.db` | 向量数据单文件，备份即拷贝该卷 |
| 后端上传目录 | 命名卷 `backend_uploads` | `/app/uploads` | 用户上传文档持久化 |
| Prometheus 配置 | `./deploy/prometheus.yml` | `/etc/prometheus/prometheus.yml` | 只读挂载，仅监控 profile |
| Loki 配置 | `./deploy/loki-config.yml` | `/etc/loki/loki-config.yml` | 只读挂载，仅监控 profile |

> 前端不进入容器：`./frontend/` 直接在宿主机以 `npm run dev` 运行。`frontend/Dockerfile` 与 `frontend/nginx.conf` 保留，仅供需要手动构建前端镜像 / 反向代理时参考。

## 数据卷

`mysql_data`（MySQL 数据）、`redis_data`（Redis 数据）、`es_data`（ES 索引）、`backend_uploads`（上传文件）、`backend_milvus`（Milvus Lite 向量库）、`prometheus_data` / `grafana_data` / `loki_data`（仅监控 profile 使用）。
