FROM python:3.12-slim

# uv como único gestor de paquetes (copiado desde su imagen oficial)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# git para versionar desde el contenedor; curl para probar servicios
RUN apt-get update \
    && apt-get install -y --no-install-recommends git curl \
    && rm -rf /var/lib/apt/lists/*

# El entorno virtual vive FUERA de la carpeta del proyecto (ver docker-compose)
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_LINK_MODE=copy \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /workspace

# Instalar dependencias, solo si existe el archivo uv.lock
RUN if [ -f uv.lock ]; then uv sync; fi