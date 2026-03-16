import os, sys, subprocess
port = os.environ.get('PORT', '8080')
print(f"Starting on port {port}", flush=True)
sys.exit(subprocess.call([
    sys.executable, '-m', 'uvicorn', 
    'test_app:app', 
    '--host', '0.0.0.0', 
    '--port', port
]))
