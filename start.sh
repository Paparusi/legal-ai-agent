#!/bin/sh
echo "Starting Legal AI Agent..."
echo "PORT=$PORT"
echo "Python version:"
python3 --version
echo "Testing imports..."
python3 -c "
try:
    import fastapi; print(f'fastapi OK: {fastapi.__version__}')
    import psycopg2; print('psycopg2 OK')
    import httpx; print('httpx OK')
    import bcrypt; print('bcrypt OK')
    import jwt; print('jwt OK')
    from dotenv import load_dotenv; print('dotenv OK')
    print('All imports OK, starting app...')
except Exception as e:
    print(f'IMPORT ERROR: {e}')
"
exec uvicorn src.api.main:app --host 0.0.0.0 --port ${PORT:-8080}
