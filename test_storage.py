"""Test Supabase Storage integration"""
import asyncio
import os
from src.services.file_storage import upload_file, download_file, get_download_url

# Set the service key for testing — read from environment, never hardcode
if not os.environ.get("SUPABASE_SERVICE_KEY"):
    raise SystemExit("Set SUPABASE_SERVICE_KEY env var before running this test")

async def test_storage():
    # Create a test file
    test_content = b"Hello from Legal AI Agent! This is a test file."
    test_filename = "test.txt"
    company_id = "test-company"
    
    print("1. Testing upload...")
    result = await upload_file(test_content, company_id, test_filename)
    print(f"   ✓ Upload result: {result}")
    
    storage_path = result["storage_path"]
    
    print("\n2. Testing download...")
    downloaded = await download_file(storage_path)
    print(f"   ✓ Downloaded {len(downloaded)} bytes")
    print(f"   ✓ Content matches: {downloaded == test_content}")
    
    print("\n3. Testing signed URL...")
    url = await get_download_url(storage_path, expires_in=3600)
    print(f"   ✓ Signed URL: {url}")
    
    print("\n✅ All storage tests passed!")

if __name__ == "__main__":
    asyncio.run(test_storage())
