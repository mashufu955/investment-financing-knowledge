# 投融资知识库管理平台 - 接口说明

> 统一响应约定：`code` / `message` / `data`，以下表格仅展示 `data` 主字段。

## 鉴权（`/api/auth`）

| 方法 | 路径 | 说明 | 请求 | 响应 |
| --- | --- | --- | --- | --- |
| POST | `/api/auth/login` | 内部员工登录 | `username`, `password` | `access_token`, `user_info`, `permissions` |
| GET | `/api/auth/me` | 当前登录用户信息 | - | `user_info` |

## 组织与权限（`/api/org`）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/org/departments` | 团队/基金/项目范围树形列表 |
| POST | `/api/org/departments` | 新增团队/基金/项目组节点 |
| PUT | `/api/org/departments/{id}` | 编辑团队/基金/项目组 |
| DELETE | `/api/org/departments/{id}` | 删除团队/基金/项目组节点 |
| POST | `/api/org/departments/{id}/members` | 维护团队成员关联 |
| GET | `/api/org/users` | 内部员工列表（含团队归属、角色） |
| POST | `/api/org/users` | 新增内部员工 |
| PUT | `/api/org/users/{id}` | 编辑内部员工 |
| POST | `/api/org/users/{id}/reset-password` | 重置员工密码 |
| POST | `/api/org/users/{id}/status` | 启停用员工账号 |
| GET | `/api/org/roles` | 角色列表 |
| POST | `/api/org/roles` | 新增角色 |
| PUT | `/api/org/roles/{id}` | 更新角色 |
| DELETE | `/api/org/roles/{id}` | 删除角色 |
| POST | `/api/org/roles/{id}/permissions` | 分配角色操作权限 |

## 投融资知识维护（`/api/knowledge`）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/knowledge/import` | 单文件/批量导入项目文档，返回 `task_id` |
| GET | `/api/knowledge/import/{task_id}` | 轮询导入任务进度 |
| POST | `/api/knowledge/units` | 新建投融资知识单元 |
| GET | `/api/knowledge/units` | 按行业/轮次/阶段/保密级别/状态分页查询 |
| GET | `/api/knowledge/units/{id}` | 单元详情与已配置的数据权限列表 |
| PUT | `/api/knowledge/units/{id}` | 更新知识单元（自增版本） |
| DELETE | `/api/knowledge/units` | 批量删除知识单元 |
| POST | `/api/knowledge/units/{id}/permissions` | 批量配置数据权限实体（global/department/role/user） |
| POST | `/api/knowledge/check-permissions` | 批量校验数据权限：请求 `user_id`, `unit_ids`；响应 `authorized_unit_ids`, `unauthorized_unit_ids` |

## AI 检索与问答鉴权（`/api/ai`）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/ai/chat/stream` | SSE 流式问答，请求 `question`, `session_id`；事件类型 `trace` / `answer` / `permission_missing` / `sources` / `done` |
| GET | `/api/ai/sessions` | 历史对话会话列表 |
| GET | `/api/ai/sessions/{session_id}/messages` | 单会话消息列表 |

## 数据看板（`/api/dashboard`）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/dashboard/metrics` | 访问总次数、独立用户数、知识单元数、Token 总量、平均耗时 |
| GET | `/api/dashboard/project-pipeline` | 项目阶段漏斗、融资金额（折算 CNY）、行业分布、阶段转化率 |
| GET | `/api/dashboard/rankings/questions` | 投融资常见问题 TOP 榜（默认 top_n=10） |
| GET | `/api/dashboard/rankings/units` | 最常访问项目知识单元 TOP 榜 |
| GET | `/api/dashboard/stats/tokens` | Token 消耗与响应时间趋势（近 7 天）+ FAQ 命中率 |

## 知识沉淀与 FAQ（`/api/settlement`）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/settlement/faqs/recommendations` | 高频问题挖掘推荐列表（source_type=auto_mined, status=pending_review） |
| POST | `/api/settlement/faqs/{id}/review` | 审核 FAQ，请求 `action`（`approve`/`reject`）、`edited_answer` |
| GET | `/api/settlement/faqs` | 已发布 FAQ 库及缓存生效状态（cache_status: active/miss） |
| GET | `/api/settlement/knowledge-gaps` | 知识缺口列表（识别低相似度/无可用知识的问答） |