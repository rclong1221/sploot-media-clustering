# syntax=docker/dockerfile:1.6
FROM sploot/python-base:3.11-cpu AS runtime

# Install project dependencies inside the shared /opt/venv environment.
USER root
COPY requirements.txt /tmp/requirements.txt
RUN /opt/venv/bin/pip install --requirement /tmp/requirements.txt && \
    rm /tmp/requirements.txt

# Copy application code.
COPY src/ /app/src/
COPY workers/ /app/workers/

ENV PYTHONPATH=/app/src \
    APP_MODULE="sploot_media_clustering.app:create_app" \
    INTERNAL_TOKEN="changeme"

EXPOSE 9007

USER app

CMD ["uvicorn", "sploot_media_clustering.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "9007"]
