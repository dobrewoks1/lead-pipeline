FROM python:3.11-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
VOLUME ["/app/out"]

# Переменные (ANTHROPIC_API_KEY и т. д.) передаются через --env-file .env
ENTRYPOINT ["python", "-m", "lead_pipeline"]
CMD ["run", "--input", "data/sample.jsonl", "--out", "out"]
