"""FastAPI 应用入口：注册路由与中间件。"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import ai, auth, dashboard, knowledge, org, settlement
from app.config import settings

app = FastAPI(title=settings.app_name, debug=settings.debug)

# CORS：默认允许本地前端开发服务器；生产可经 CORS_ORIGINS 配置域名（逗号分隔）
_cors_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册各模块路由
app.include_router(auth.router, prefix="/api/auth", tags=["认证"])
app.include_router(org.router, prefix="/api/org", tags=["组织与权限"])
app.include_router(knowledge.router, prefix="/api/knowledge", tags=["投融资知识维护"])
app.include_router(ai.router, prefix="/api/ai", tags=["AI 检索与问答鉴权"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["数据看板"])
app.include_router(settlement.router, prefix="/api/settlement", tags=["知识沉淀与 FAQ"])


@app.get("/health")
async def health() -> dict:
    """健康检查。"""
    return {"status": "ok", "app": settings.app_name}
