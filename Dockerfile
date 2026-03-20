FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (including LibreOffice for DOCX editing)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc curl libreoffice-writer \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY static/ ./static/
COPY scripts/ ./scripts/
COPY data/ ./data/

# Create volume mount points
RUN mkdir -p /app/uploads /app/logs

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

CMD ["python3", "-m", "uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8080"]
