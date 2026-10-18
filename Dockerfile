# 1) Página web
FROM node:22-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

# 2) Servidor de voz
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    MODELS_DIR=/models MEMORY_DIR=/data/memory WEB_DIR=/app/web
WORKDIR /app
COPY server/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY server/duarte ./duarte
COPY --from=web /web/dist ./web
EXPOSE 7860
CMD ["python", "-m", "duarte.server"]
