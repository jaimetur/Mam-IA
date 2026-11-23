# Mam-IA: production image (FastAPI + SQLite server, the web app, the landing and account pages)
FROM python:3.12-slim
ARG SOURCE_REVISION=dev
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    TZ=Europe/Madrid DATA_DIR=/data FRONTEND_DIR=/app/frontend DOCS_DIR=/app/docs \
    PUID=1000 PGID=1000 MAMIA_REVISION=${SOURCE_REVISION}
RUN apt-get update && apt-get install -y --no-install-recommends tzdata && rm -rf /var/lib/apt/lists/* \
 && groupadd -g 1000 mamia && useradd -u 1000 -g 1000 -M -d /app -s /usr/sbin/nologin mamia
WORKDIR /app/backend
COPY pyproject.toml /app/pyproject.toml
RUN python -c "import tomllib; print('\n'.join(tomllib.load(open('/app/pyproject.toml','rb'))['project']['dependencies']))" > /tmp/req.txt \
 && pip install --no-cache-dir -r /tmp/req.txt && rm /tmp/req.txt
COPY src/backend/app ./app
COPY src/frontend /app/frontend
COPY README.md CHANGELOG.md /app/docs/
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod 0755 /entrypoint.sh && python -c "import app.main"
VOLUME ["/data"]
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=4)"
ENTRYPOINT ["/entrypoint.sh"]
# a single process: the reminders and backup loops live inside and must not be duplicated
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--proxy-headers", "--forwarded-allow-ips", "*"]
