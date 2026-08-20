FROM python:3.12-slim AS base
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev curl && rm -rf /var/lib/apt/lists/*
COPY shared/ /app/shared/
COPY services/llm-service/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY services/llm-service/ /app/
ENV PYTHONPATH=/app:/app/shared
EXPOSE 800
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=3 CMD curl -f http://localhost:8000/health || exit 1
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
