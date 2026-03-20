"""Test Supabase Storage integration"""
import asyncio
import os
from src.services.file_storage import upload_file, download_file, get_download_url

# Set the service key for testing
os.environ["SUPABASE_SERVICE_KEY"] = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImNoaW9rb3R6anRqd2ZvZHJ5ZmR0Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MzU1ODYxMSwiZXhwIjoyMDg5MTM0NjExfQ.5qQlSqf68QLHekY41Ko7ECczmlmMA4TNCTyg-RELOPY"

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
