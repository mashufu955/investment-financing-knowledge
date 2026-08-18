#!/usr/bin/env bash
# ============================================================
# docker compose 启动入口：所有配置统一读取项目根目录 .env
# 用法示例： ./deploy.sh up -d --build
# ============================================================
set -e
cd "$(dirname "$0")"
docker compose --env-file ../.env "$@"
