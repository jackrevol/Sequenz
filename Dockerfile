FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DJANGO_ENV=production \
    DJANGO_DB_PATH=/data/db.sqlite3 \
    DJANGO_MEDIA_ROOT=/data/media \
    DJANGO_STATIC_ROOT=/app/staticfiles

WORKDIR /app

RUN groupadd --system sequenz \
    && useradd --system --gid sequenz --home-dir /app sequenz

COPY requirements.txt ./
RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements.txt

COPY . .

RUN chmod +x /app/docker/entrypoint.sh \
    && mkdir -p /data/media /app/staticfiles \
    && chown -R sequenz:sequenz /app /data

USER sequenz

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; r=urllib.request.Request('http://127.0.0.1:8000/healthz/', headers={'X-Forwarded-Proto':'https'}); raise SystemExit(0 if urllib.request.urlopen(r, timeout=3).status == 200 else 1)"

ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["gunicorn", "sequenz.wsgi:application", "--bind", "0.0.0.0:8000", "--access-logfile", "-", "--error-logfile", "-"]
