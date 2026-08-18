# 投融资知识库管理平台 — 项目全景讲解

## 一、项目实现逻辑

### 1.1 项目定位与核心价值

本平台是一个面向企业内部的投融资知识库管理系统，覆盖**项目/标的库、融资需求、尽调、投决、投后与知识沉淀**全流程。核心价值在于将分散的投融资文档（PDF/Word/Markdown/TXT）转化为结构化知识单元，并通过 AI 智能问答为业务人员提供精准的检索和回答服务，同时以四维数据权限体系确保信息安全。

### 1.2 整体架构

系统采用**前后端分离 + 微服务化基础设施**的架构：

- **后端**：Python 3.12 + FastAPI，提供 RESTful API，采用分层架构（API路由层 → Service业务层 → Core基础设施层 → Utils工具层）
- **前端**：Vue 3 + Vite + Pinia 状态管理，按权限动态渲染菜单
- **数据存储三层解耦**：MySQL（主数据）+ Milvus（向量索引）+ Elasticsearch（关键字索引）
- **缓存层**：Redis（FAQ缓存 / 看板聚合缓存）
- **监控栈**：Prometheus + Grafana + Loki
- **部署**：Docker Compose 一键编排 13 个容器

### 1.3 模块划分与职责

| 模块 | 职责 | 关键文件 |
|------|------|----------|
| 01 投融资知识维护 | 文档导入、解析、切片、字段抽取、知识单元CRUD、向量化同步 | `knowledge_service.py` / `text_splitter.py` / `document_parser.py` |
| 02 组织与权限 | 登录认证、JWT签发、RBAC操作权限、四维数据权限 | `org_service.py` / `permissions.py` / `auth.py` |
| 03 AI检索与问答鉴权 | 会话管理、混合召回、权限过滤、Prompt组装、SSE流式问答 | `ai_qa_service.py` / `milvus.py` / `es.py` |
| 04 数据看板 | 访问日志、项目漏斗、币种折算、行业分布、Token趋势 | `dashboard_service.py` |
| 05 知识沉淀与FAQ | 高频问题挖掘、审核发布、缓存加速、知识缺口识别 | `faq_service.py` |

### 1.4 数据模型与核心表

- **KnowledgeUnit（知识单元）**：主数据表，包含标题、内容、摘要、行业、融资轮次、金额、估值、保密级别等字段，unit_code 为业务唯一编号（YYYYMMDD + 4位序号）
- **UnitPermission（数据权限）**：四维权限——global（全局可读）、department（部门）、role（角色）、user（个人），支持 deny 类型（显式拒绝优先）
- **QaSession / QaMessage**：问答会话与消息记录
- **QaAccessLog**：问答访问日志，用于看板统计和FAQ挖掘
- **Faq / KnowledgeGap**：FAQ推荐与知识缺口

### 1.5 权限体系设计

系统采用**RBAC + 四维数据权限**双层模型：

1. **操作权限（RBAC）**：通过 RolePermission 表配置菜单/按钮级权限，前端路由守卫根据 `meta.permission` 拦截
2. **数据权限（四维）**：每个知识单元可配置多条 UnitPermission 规则，判定逻辑为 `has_allow and not has_deny`——即至少有一条 allow 规则匹配且无 deny 规则命中时放行。confidential_level <= 1（公开级）时，无显式权限配置也默认可读

---

## 二、具体功能

### 2.1 知识维护功能

- **文档导入**：支持 PDF/Word/Markdown/TXT 四种格式，上传后自动解析为纯文本
- **智能切片**：按 Markdown 标题层级 + 长度约束切片（max_length=500, overlap=50），保留上下文衔接
- **字段抽取与归一化**：行业统一为中文规范名（如 biotech→生物医药），融资轮次统一为英文枚举（如 A轮→series_a）
- **编号生成**：unit_code 采用 `YYYYMMDD + 当日4位序号` 格式，自动递增
- **知识单元CRUD**：支持创建、编辑、删除、列表查询，含版本号和状态管理
- **权限自动写入**：创建/导入时按 confidential_level 自动写入 global + user 默认权限

### 2.2 AI 智能问答功能

- **会话管理**：支持多轮对话，自动创建和恢复会话
- **混合召回**：Milvus 向量检索（权重0.7）+ ES BM25关键字检索（权重0.3），合并去重后按分数排序
- **权限过滤**：召回后对每个候选单元执行四维权限判定，区分 authorized/unauthorized
- **Rerank 重排**：对授权单元按相关性重排，截断到 TOP 5，提升回答质量
- **Prompt 组装**：将授权片段 + 对话历史 + 系统提示词组装为结构化 Prompt
- **SSE 流式回答**：通过 OpenAI API 流式生成回答，前端实时渲染 Markdown
- **引用来源**：回答中标注 [n] 引用，末尾附来源卡片（unit_code + 标题）
- **权限缺失提示**：对未授权的单元，在回答末尾给出"缺少项目数据权限"提示
- **安全过滤**：检测敏感问题（投资建议、未公开、内幕等），Prompt 注入防护

### 2.3 组织与权限功能

- **登录认证**：JWT 签发与校验，access_token 有效期 120 分钟
- **RBAC 操作权限**：角色-权限分配，前端按权限动态渲染菜单
- **四维数据权限**：global/department/role/user 四种授权实体 + deny 显式拒绝
- **团队/基金/项目范围树**：树形组织结构，支持跨基金访问审批

### 2.4 数据看板功能

- **访问日志**：异步记录每轮问答的耗时、Token消耗、命中单元
- **项目阶段漏斗**：sourcing → due_diligence → investment_committee → closing → post_investment
- **币种折算**：自动将 USD/HKD/EUR 等折算为 CNY
- **行业分布**：按标准行业统计项目数量
- **问题 TOP 榜**：高频问题排行
- **单元 TOP 榜**：最常被访问的知识单元排行
- **Token 趋势**：近7天 Token 消耗与响应时间趋势
- **FAQ 命中率**：已发布 FAQ 的命中统计
- **看板缓存**：Redis 缓存 300 秒，降级为内存缓存

### 2.5 知识沉淀与FAQ功能

- **FAQ 挖掘**：对历史问答按频次聚合，达到阈值（≥3次）自动生成 FAQ 推荐项
- **语义去重**：按 Jaccard 相似度聚类，阈值 0.85
- **审核发布**：管理员 approve/reject，通过后写入 Redis 缓存
- **缓存加速**：FAQ 命中时直接返回标准答案，阈值精确匹配 0.98 / 语义匹配 0.85
- **知识缺口识别**：识别召回相似度低或无可用知识支撑的问答记录，生成缺口项
- **一键创建**：从缺口直接创建知识单元，自动关闭缺口状态

---

## 三、文档导入与知识问答的实现过程

### 3.1 文档导入全流程

```
用户上传文件 → 保存到 /app/uploads → 识别文件类型 → 选择解析器
    ↓
解析为纯文本 → 按标题+长度切片 → 每个切片生成一个 KnowledgeUnit
    ↓
写入 MySQL（unit_code/标题/内容/行业/轮次等） → 自动写入 UnitPermission
    ↓
db.commit() → 状态设为 done
    ↓
异步向量化：bge-m3 编码 → 写入 Milvus（upsert） → 写入 ES（index）
    ↓
前端轮询进度 → 完成
```

**关键细节**：

1. **解析器**：PDF 用 pypdf，Word 用 python-docx，Markdown 用 markdown-it-py，TXT 用编码探测
2. **切片策略**：先按 Markdown 标题切分（保留标题上下文），再按长度（500字符）+ 重叠（50字符）二次切分
3. **编号生成**：`generate_unit_code()` 查当日已有最大编号 +1，如 `202608180001`
4. **导入顺序**：MySQL 先 commit（保证列表可见），Milvus/ES 后写入（失败仅告警不回滚）
5. **权限写入**：confidential_level<=1 自动写 global + user 两条权限记录

### 3.2 知识问答全流程

```
用户提问 → 前端 SSE 请求 → 后端 chat_stream()
    ↓
1. validate_login：校验用户登录态，获取部门/角色上下文
    ↓
2. manage_session：创建或恢复会话
    ↓
3. retrieve_candidates：混合召回
   ├── Milvus 向量检索（bge-m3 编码问题 → HNSW/COSINE ANN → top 20）
   ├── ES BM25 关键字检索（问题文本 → match → top 20）
   └── 合并去重：unit_id 为 key，向量权重 0.7 + 关键字权重 0.3
    ↓
4. filter_authorized_units：逐个候选单元执行权限判定
   ├── 查 KnowledgeUnit 的 confidential_level
   ├── 查 UnitPermission 规则列表
   └── _eval_rules：has_allow and not has_deny
    ↓
5. rerank：对授权单元重排，截断到 TOP 5
    ↓
6. assemble_prompt：拼接 System + History + Authorized + References + Question
    ↓
7. stream_answer：调 OpenAI API 流式生成回答
    ↓
8. 前端 SSE 事件流：
   ├── trace：追踪信息
   ├── answer：逐 chunk 回答
   ├── permission_missing：权限缺失提示
   ├── sources：引用来源卡片
   └── done：完成信号
    ↓
9. record_access_log：异步记录访问日志
```

**关键设计决策**：

1. **向量+关键字混合**：纯向量召回可能遗漏关键字精确匹配，纯关键字无法理解语义，混合方案互补
2. **权限后置过滤**：在召回后而非召回时过滤，避免在 Milvus/ES 中存储权限信息
3. **向量召回降级**：Milvus 异常时自动降级为 ES 关键字检索，保证问答不中断
4. **Rerank 截断**：从 20 条候选截断到 5 条，减少 token 消耗、提升相关性
5. **SSE 流式**：前端可实时渲染 Markdown，用户体验更流畅

---

## 四、当前项目的不足与缺陷

### 4.1 已修复的问题

- ✅ 导入文档不写权限记录 → 问答默认拒绝（已修复：自动写入 global + user 权限）
- ✅ FAQ/缺口列表只返回本次新挖掘项 → 数据已存在后页面空白（已修复：改为查全部 pending）
- ✅ 路由守卫无限重定向（已修复：无权限回退到个人中心）
- ✅ deny 权限规则失效（已修复：allow 提前 return 绕过 deny）
- ✅ 知识缺口闭环断裂（已修复：创建单元时自动关闭缺口）
- ✅ 改保密级不联动权限（已修复：update_unit 同步增删权限记录）
- ✅ 导入进度轮询失效（已修复：改为按 creator_id + 时间窗关联）
- ✅ rerank 未接入 + 引用 unit_code 缺失（已修复）
- ✅ 权限摘要列恒空（已修复：列表序列化补 permission_summary）

### 4.2 仍存在的不足

| 编号 | 问题 | 严重度 | 说明 |
|------|------|--------|------|
| 1 | 向量索引与 DB 非强一致 | 中 | Milvus/ES 写入在 commit 之后异步执行，失败仅告警不回滚，可能导致"DB 有数据但索引缺" |
| 2 | 导入任务状态为内存级 | 中 | `_import_tasks` 和 `_reindex_tasks` 存在进程内存，容器重启后丢失 |
| 3 | FAQ 语义匹配用 Jaccard | 中 | Jaccard 相似度不考虑词序和语义，"融资需求"和"需求融资"可能误匹配；应改用向量余弦相似度 |
| 4 | 嵌入模型仅 CPU | 中 | bge-m3 在 CPU 上推理较慢，大批量向量化时耗时长 |
| 5 | 无单元级锁 | 低 | 并发创建同一天的知识单元时，unit_code 编号可能冲突（概率极低） |
| 6 | 无分页 | 低 | FAQ/缺口列表和部分知识单元查询未分页，数据量大时可能超时 |
| 7 | 看板缓存无主动失效 | 低 | Redis 缓存 300 秒 TTL，数据更新后最多延迟 5 分钟可见 |
| 8 | 向量索引无状态字段 | 低 | knowledge_units 表没有"是否已索引"字段，前端无法显示向量缺失状态 |

---

## 五、后期技术扩展方向

### 5.1 短期优化（1-3 个月）

1. **索引一致性保障**：引入 Outbox 模式或消息队列，将 Milvus/ES 写入从同步改为异步消息消费，保证最终一致性
2. **任务持久化**：将导入/重索引任务状态从内存迁移到 Redis 或 MySQL，支持容器重启后恢复
3. **FAQ 语义匹配升级**：将 Jaccard 替换为 bge-m3 向量余弦相似度，提升匹配准确率
4. **GPU 加速推理**：在 Milvus 独立 GPU 服务器上部署 embedding 模型，或使用推理服务（如 TEI/Triton）
5. **分页与排序**：所有列表接口增加分页参数，支持按时间/热度/行业排序
6. **单元级乐观锁**：用 version 字段做乐观并发控制，避免编号冲突

### 5.2 中期功能扩展（3-6 个月）

1. **多模态知识单元**：支持图片、表格、PDF 原始页面的索引和检索，引入多模态 embedding 模型（如 CLIP）
2. **知识图谱**：从知识单元中抽取实体关系（公司-行业-轮次-金额），构建知识图谱，支持关联推荐和路径查询
3. **协作编辑**：支持多人同时编辑知识单元，引入 OT/CRDT 冲突解决机制
4. **审批流**：知识单元的创建/修改/删除走审批流程，集成企业微信/钉钉审批
5. **审计日志**：完整记录所有数据变更操作，支持回溯和合规审查
6. **移动端适配**：响应式布局或小程序，支持移动端问答和知识查阅

### 5.3 长期架构演进（6-12 个月）

1. **微服务拆分**：将单体 FastAPI 拆分为知识服务、问答服务、权限服务、看板服务，通过 gRPC/消息队列通信
2. **多租户**：支持多个基金/团队独立隔离，数据物理隔离或逻辑隔离
3. **联邦检索**：跨多个知识库检索，支持跨团队/跨基金的知识共享
4. **Agent 化**：将问答系统升级为 AI Agent，支持多步推理、工具调用（如调用外部数据源、生成报告）
5. **私有化部署**：支持离线部署，LLM 使用本地模型（如 Qwen/ChatGLM），embedding 使用本地 bge-m3
6. **可观测性**：引入 OpenTelemetry 全链路追踪，替代当前的 trace_id 方案

---

## 六、技术栈的升级实现

### 6.1 后端技术栈升级

| 当前 | 升级方向 | 原因 |
|------|----------|------|
| FastAPI 同步服务 | FastAPI + asyncio 全面异步化 | 当前 Milvus/ES/DB 操作均为同步阻塞，全面异步化可提升并发吞吐 |
| SQLAlchemy 2.0 同步 | SQLAlchemy 2.0 async + asyncpg/aiomysql | 异步数据库驱动，减少 IO 等待 |
| 内存任务状态 | Celery + Redis/RabbitMQ | 持久化任务队列，支持重试、超时、并发控制 |
| 同步 Milvus/ES 写入 | Outbox + 消息队列异步消费 | 保证 DB 与索引最终一致性 |
| OpenAI API 直调 | LiteLLM 统一代理 | 支持 100+ 模型切换，统一接口，降低模型绑定风险 |
| pypdf 解析 | Unstructured / LlamaParse | 支持更复杂的 PDF 布局、表格、图片提取 |
| bge-m3 CPU 推理 | TEI (Text Embeddings Inference) GPU 服务 | 推理加速 10-50 倍，支持批量推理 |

### 6.2 前端技术栈升级

| 当前 | 升级方向 | 原因 |
|------|----------|------|
| Vue 3 Options API | Vue 3 Composition API + `<script setup>` | 更好的类型推导、逻辑复用、代码组织 |
| Pinia 手动管理 | Pinia + VueQuery | VueQuery 自动管理缓存/重试/过期，减少手动状态管理 |
| markdown-it 渲染 | Markdown 渲染 + Mermaid 图表 | 支持回答中的流程图、架构图渲染 |
| 无测试 | Vitest + Playwright | 单元测试 + E2E 测试，保障前端质量 |
| 无国际化 | vue-i18n | 支持多语言，面向国际化场景 |

### 6.3 基础设施升级

| 当前 | 升级方向 | 原因 |
|------|----------|------|
| Docker Compose 单机 | Kubernetes (K8s) | 支持水平扩展、自动伸缩、滚动更新、健康检查 |
| Milvus Standalone | Milvus Cluster | 支持数据分片、高可用、读写分离 |
| MySQL 单实例 | MySQL 主从 + 读写分离 | 读多写少场景，主库写、从库读 |
| Redis 单实例 | Redis Sentinel / Cluster | 高可用，自动故障转移 |
| 无 CI/CD | GitHub Actions + ArgoCD | 自动化测试、构建、部署 |
| Prometheus + Grafana | Prometheus + Grafana + OpenTelemetry | 全链路追踪 + 指标 + 日志三位一体 |

### 6.4 向量检索升级

| 当前 | 升级方向 | 原因 |
|------|----------|------|
| Milvus HNSW | Milvus GPU 索引 (GPU_IVF_PQ) | 大规模数据（百万级）检索加速 |
| 单路召回 | 多路召回 + Cross-Encoder Rerank | 粗排 + 精排两阶段，提升 Top-K 准确率 |
| 无向量压缩 | PQ/SQ 量化 | 减少内存占用，支持更大规模数据 |
| 1024 维 bge-m3 | bge-m3 + Matryoshka 维度截断 | 支持灵活降维，平衡精度与性能 |

---

## 附录：技术栈一览

| 层 | 选型 |
|---|---|
| 后端框架 | Python 3.12 + FastAPI + SQLAlchemy 2.0 + PyMySQL |
| 前端框架 | Vue 3 + Vite + Vue Router + Pinia + Axios |
| 业务数据库 | MySQL 8.0 |
| 向量检索 | Milvus 2.4 (HNSW/COSINE, 1024维) |
| 关键字检索 | Elasticsearch 8 (BM25) |
| 缓存 | Redis 7 |
| 嵌入模型 | BAAI/bge-m3 (本地部署, sentence-transformers) |
| LLM | OpenAI GPT-4o (可配置) |
| 认证 | JWT + RBAC + 四维数据权限 |
| 文档解析 | pypdf + python-docx + markdown-it-py |
| 监控 | Prometheus + Grafana + Loki |
| 部署 | Docker Compose (13容器) |
