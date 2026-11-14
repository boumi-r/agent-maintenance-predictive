# API MaintenanceAI — image de production (Railway) et de développement (docker compose)
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /srv
COPY pyproject.toml ./
COPY backend ./backend
COPY scripts ./scripts
RUN pip install . \
    && useradd --create-home --uid 1000 app

USER app
WORKDIR /srv/backend
EXPOSE 8000

# Migrations puis serveur. PORT est fourni par Railway (8000 en local).
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers"]
