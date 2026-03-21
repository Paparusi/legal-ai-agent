# Quick Test Guide - DOCX Editing Feature

## Prerequisites

- Server running on port 8080 ✓
- API key with valid company_id
- Sample `.docx` file for testing

## Test 1: Upload & Download Original File

### 1.1 Upload via Chat

```bash
curl -X POST http://localhost:8080/v1/chat/upload \
  -H "X-API-Key: your_api_key_here" \
  -F "file=@test_contract.docx"
```

**Expected response:**
```json
{
  "filename": "test_contract.docx",
  "content": "extracted text...",
  "file_type": ".docx",
  "document_id": "123",
  "file_path": "uploads/documents/456/abc_test_contract.docx"
}
```

**Save the `document_id` for next steps.**

### 1.2 Download Original File

```bash
curl -X GET http://localhost:8080/v1/documents/{document_id}/download \
  -H "X-API-Key: your_api_key_here" \
  -o downloaded_original.docx
```

**Expected:** File downloads successfully, open in Word to verify it's the same.

## Test 2: Edit DOCX File

### 2.1 Apply Edits

```bash
curl -X POST http://localhost:8080/v1/documents/{document_id}/edit-docx \
  -H "X-API-Key: your_api_key_here" \
  -H "Content-Type: application/json" \
  -d '{
    "edits": [
      {"find": "10.000.000", "replace": "15.000.000"},
      {"find": "12 tháng", "replace": "24 tháng"}
    ]
  }'
```

**Expected response:**
```json
{
  "message": "Document edited successfully",
  "document_id": "123",
  "changes_made": 2,
  "edits_applied": [
    {"find": "10.000.000", "replace": "15.000.000", "location": "paragraph"},
    {"find": "12 tháng", "replace": "24 tháng", "location": "paragraph"}
  ],
  "download_url": "/v1/documents/123/download",
  "output_filename": "abc_edited_test_contract.docx"
}
```

### 2.2 Download Edited File

```bash
curl -X GET http://localhost:8080/v1/documents/{document_id}/download \
  -H "X-API-Key: your_api_key_here" \
  -o downloaded_edited.docx
```

**Expected:** File downloads successfully.

### 2.3 Verify Edits

Open `downloaded_edited.docx` in Microsoft Word or LibreOffice:

✅ Check that "10.000.000" changed to "15.000.000"  
✅ Check that "12 tháng" changed to "24 tháng"  
✅ Check that **bold text is still bold**  
✅ Check that **tables are still formatted**  
✅ Check that **fonts and sizes are preserved**

## Test 3: Frontend Test (Browser)

### 3.1 Open Chat Interface

1. Go to: `http://localhost:8080/app.html`
2. Login with valid credentials

### 3.2 Upload File via Chat

1. Click upload button (📎) in chat
2. Select a `.docx` file
3. Wait for upload confirmation
4. Verify file appears in chat with extracted text

### 3.3 Ask AI to Edit

Type in chat:
```
Sửa mức lương từ 10 triệu thành 15 triệu
```

### 3.4 Check Download Button

**Expected in chat:**
- Diff view showing changes
- Button: **📥 Tải xuống file Word (.docx)**

### 3.5 Download and Verify

1. Click the download button
2. Open the downloaded `.docx` file
3. Verify edits are applied
4. Verify formatting is preserved

## Test 4: Automated Test Suite

### Run the test script

```bash
cd /tmp/legal-ai-agent
python3 test_docx_editing.py
```

**Expected output:**
```
📝 Testing DOCX editing...

1. Creating test DOCX...
   ✓ Created: test_output/test_contract.docx

2. Applying edits...
   ✓ Edited: test_output/test_contract_edited.docx
   ✓ Changes made: 3
   ✓ Edits applied: 3

3. Verifying edits...
   Original length: 228 chars
   Edited length: 228 chars

✅ All tests passed!
```

## Test 5: Edge Cases

### 5.1 Upload non-DOCX file

```bash
curl -X POST http://localhost:8080/v1/chat/upload \
  -H "X-API-Key: your_api_key_here" \
  -F "file=@test.pdf"
```

**Expected:** Upload succeeds, but edit endpoint should reject PDF files.

### 5.2 Try to edit PDF

```bash
curl -X POST http://localhost:8080/v1/documents/{pdf_doc_id}/edit-docx \
  -H "X-API-Key: your_api_key_here" \
  -H "Content-Type: application/json" \
  -d '{"edits": [{"find": "old", "replace": "new"}]}'
```

**Expected:** Error 400: "Only .docx files can be edited"

### 5.3 Edit with no matches

```bash
curl -X POST http://localhost:8080/v1/documents/{document_id}/edit-docx \
  -H "X-API-Key: your_api_key_here" \
  -H "Content-Type: application/json" \
  -d '{"edits": [{"find": "text that does not exist", "replace": "new"}]}'
```

**Expected:** Success with `changes_made: 0`

### 5.4 Try to download without auth

```bash
curl -X GET http://localhost:8080/v1/documents/{document_id}/download
```

**Expected:** Error 401 or 403: Unauthorized

### 5.5 Try to download another company's document

Use API key from company A to download document from company B.

**Expected:** Error 403 or 404: Access denied

## Verification Checklist

After all tests, verify:

✅ Original files are kept on server  
✅ Edited files are saved with `_edited_` prefix  
✅ Downloads work correctly  
✅ Formatting is preserved (bold, italic, tables)  
✅ Company ownership is enforced  
✅ Non-DOCX files are rejected for editing  
✅ Frontend shows download button for DOCX files  
✅ Old chat uploads without file_path handle gracefully

## Troubleshooting

### Issue: "File not found on disk"

**Cause:** Old documents in DB have `file_path = 'chat-upload'`

**Fix:** These documents can't be downloaded (expected behavior)

### Issue: "Edit failed: No module named 'docx'"

**Cause:** python-docx not installed

**Fix:**
```bash
pip install python-docx
```

### Issue: Download button not showing in frontend

**Check:**
1. Does the `document_edit` event include `download_url`?
2. Open browser console (F12) and check event data
3. Verify `renderDiffView()` receives `downloadUrl` parameter

### Issue: Formatting not preserved

**Check:**
1. Is the original file actually `.docx` format?
2. Open original and edited files side-by-side in Word
3. Check if original file has complex nested formatting (might not preserve 100%)

## Sample Test Document

Create a test DOCX with:

```
HỢP ĐỒNG LÀM VIỆC

ĐIỀU 1: Các bên tham gia
Bên A: Công ty ABC
Bên B: Nguyễn Văn A

ĐIỀU 2: Mức lương
Mức lương: 10.000.000 VNĐ/tháng
Phụ cấp: 2.000.000 VNĐ/tháng

ĐIỀU 3: Thời hạn hợp đồng
Thời hạn: 12 tháng kể từ ngày ký
```

**Formatting to include:**
- Bold headings (ĐIỀU 1, ĐIỀU 2, etc.)
- Normal text for content
- Some italic text (e.g., company name)
- A simple table (optional)

This will help verify formatting preservation.

---

**Ready to test!** 🚀

Run these tests to verify the DOCX editing feature works correctly.
