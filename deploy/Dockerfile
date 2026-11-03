# Imagen para la nube (Render): compila la web y la entrega el mismo servidor de Python.
# Se construye desde la raiz del repo:  docker build -f deploy/Dockerfile -t llavetrack .
# Guia completa: docs/despliegue.md

# 1) La web: npm run build deja los archivos en dist/
FROM node:24-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# 2) El servidor, con la web compilada al lado
FROM python:3.12-slim
WORKDIR /app/backend
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./
COPY --from=web /web/dist /app/web

# La web la entrega este servidor; la cookie de sesion solo viaja por HTTPS
ENV WEB_DIST=/app/web \
    COOKIE_SEGURA=true \
    PYTHONUNBUFFERED=1

# Al arrancar: pone la base al dia (si ya lo esta, no hace nada) y levanta la API.
# Render dice en que puerto escuchar ($PORT). --proxy-headers: Render atiende el HTTPS y le pasa
# el pedido al servidor; asi el servidor sabe que el original era HTTPS.
CMD alembic upgrade head && \
    uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips '*'
