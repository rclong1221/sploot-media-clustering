# syntax=docker/dockerfile:1.6
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/src

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

COPY src ./src
COPY workers ./workers

EXPOSE 9007

ENV APP_MODULE="sploot_media_clustering.app:create_app" \
    INTERNAL_TOKEN="changeme"

CMD ["uvicorn", "sploot_media_clustering.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "9007"]
