FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# build-essential / pkg-config：部分依赖无预编译 wheel 时可现场编译；
# curl：供 compose healthcheck 探测 /health
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential pkg-config curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
