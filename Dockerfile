FROM node:22-bookworm-slim AS frontend
WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 APP_ENV=production SCOUTLIQ_CONTAINER=1 DATABASE_URL=sqlite:////data/scoutliq.db SCOUTLIQ_PROCESS_MODE=combined
WORKDIR /app
COPY requirements.txt requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock && useradd --create-home --uid 10001 scout && mkdir /data && chown scout:scout /data
COPY backend/ backend/
COPY migrations/ migrations/
COPY alembic.ini ./
COPY scripts/start.py scripts/start.py
COPY scripts/backup.py scripts/backup.py
COPY scripts/reset_password.py scripts/reset_password.py
COPY --from=frontend /build/dist frontend/dist
# Bootstrap owns only /data and its database, then drops UID/GID before migrations and children.
USER root
EXPOSE 8000
CMD ["python", "scripts/start.py"]
