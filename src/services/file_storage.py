"""
File Storage Service — Supabase Storage for permanent file persistence.
Fallback to local disk if Supabase unavailable.
"""
import os
import httpx
import uuid
from pathlib import Path

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://chiokotzjtjwfodryfdt.supabase.co")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
BUCKET = "documents"
LOCAL_UPLOAD_DIR = Path("/tmp/legal-ai-agent-uploads/documents")

_MIME_MAP = {
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".doc": "application/msword",
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
}


def _content_type(filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    return _MIME_MAP.get(ext, "application/octet-stream")


async def upload_file(file_bytes: bytes, company_id: str, filename: str) -> dict:
    """Upload file to Supabase Storage. Returns {storage_path, provider, content_type}"""
    unique_name = f"{company_id}/{uuid.uuid4()}_{filename}"
    ct = _content_type(filename)

    if SUPABASE_SERVICE_KEY:
        # Upload to Supabase Storage
        url = f"{SUPABASE_URL}/storage/v1/object/{BUCKET}/{unique_name}"
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    url,
                    content=file_bytes,
                    headers={
                        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
                        "Content-Type": ct
                    }
                )
                if resp.status_code in (200, 201):
                    return {"storage_path": unique_name, "provider": "supabase", "content_type": ct}
                else:
                    print(f"Supabase upload failed: {resp.status_code} - {resp.text}")
        except Exception as e:
            print(f"Supabase upload error: {e}")
    
    # Fallback: local disk
    local_path = LOCAL_UPLOAD_DIR / unique_name
    local_path.parent.mkdir(parents=True, exist_ok=True)
    local_path.write_bytes(file_bytes)
    return {"storage_path": str(local_path), "provider": "local", "content_type": ct}


async def download_file(storage_path: str) -> bytes:
    """Download file from storage"""
    if SUPABASE_SERVICE_KEY and not storage_path.startswith("/"):
        url = f"{SUPABASE_URL}/storage/v1/object/{BUCKET}/{storage_path}"
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    url, 
                    headers={"Authorization": f"Bearer {SUPABASE_SERVICE_KEY}"}
                )
                if resp.status_code == 200:
                    return resp.content
                else:
                    print(f"Supabase download failed: {resp.status_code}")
        except Exception as e:
            print(f"Supabase download error: {e}")
    
    # Local fallback
    return Path(storage_path).read_bytes()


async def get_download_url(storage_path: str, expires_in: int = 3600) -> str:
    """Get signed download URL (Supabase) or local path"""
    if SUPABASE_SERVICE_KEY and not storage_path.startswith("/"):
        url = f"{SUPABASE_URL}/storage/v1/object/sign/{BUCKET}/{storage_path}"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    url, 
                    json={"expiresIn": expires_in},
                    headers={"Authorization": f"Bearer {SUPABASE_SERVICE_KEY}"}
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return f"{SUPABASE_URL}/storage/v1{data['signedURL']}"
                else:
                    print(f"Supabase signed URL failed: {resp.status_code}")
        except Exception as e:
            print(f"Supabase signed URL error: {e}")
    
    # Return local path for fallback
    return f"/uploads/{storage_path}"


async def delete_file(storage_path: str) -> bool:
    """Delete file from storage"""
    if SUPABASE_SERVICE_KEY and not storage_path.startswith("/"):
        url = f"{SUPABASE_URL}/storage/v1/object/{BUCKET}/{storage_path}"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.delete(
                    url,
                    headers={"Authorization": f"Bearer {SUPABASE_SERVICE_KEY}"}
                )
                return resp.status_code == 200
        except Exception as e:
            print(f"Supabase delete error: {e}")
            return False
    
    # Local fallback
    try:
        Path(storage_path).unlink(missing_ok=True)
        return True
    except Exception:
        return False
