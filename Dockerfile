FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Cache bust: v2-2026-03-16
COPY src/ ./src/
COPY static/ ./static/

EXPOSE 8080

CMD ["python3", "-m", "uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8080"]
