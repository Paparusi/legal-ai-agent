FROM python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir fastapi uvicorn
COPY test_app.py entrypoint.py ./
CMD ["python3", "entrypoint.py"]
