@echo off
rem Docker compose entry: all config reads project root .env
rem Usage: deploy.cmd up -d --build
cd /d "%~dp0"
docker compose --env-file ../.env %*
