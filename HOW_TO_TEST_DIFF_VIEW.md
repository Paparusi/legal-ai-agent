# How to Test the Diff View Feature

## Prerequisites

1. Server is already running on port 8080 ✅
2. ANTHROPIC_API_KEY is configured in `.env`
3. You have access to the web UI at `http://localhost:8080`

## Testing Steps

### 1. Upload a Contract

1. Open the web UI
2. Click the **Upload** button or drag & drop a contract file (.pdf, .docx, .txt)
3. Wait for the upload to complete
4. Note the contract name that appears

### 2. Trigger the Diff View

#### Option A: Simple Request
Type in the chat:
```
Rà soát và chỉnh sửa hợp đồng này
```

#### Option B: Specific Request
```
Rà soát hợp đồng [tên hợp đồng] và sửa các lỗi pháp lý
```

#### Option C: With Instructions
```
Bổ sung điều khoản bảo mật vào hợp đồng theo BLLĐ 2019
```

### 3. Observe the Flow

You should see these stages:

1. **Tool Status:** `📋 Đang đọc hợp đồng...`
2. **Tool Status:** `🔍 Đang tra cứu văn bản pháp luật...`
3. **Tool Status:** `✏️ Đang chỉnh sửa và tạo diff view...`
4. **Diff View Appears:** Inline diff with green/red highlighting
5. **Download Button:** Available to download edited version

### 4. Verify the Diff View

Check that the diff view shows:

- ✅ Document filename at the top
- ✅ Change statistics (e.g., "12 thay đổi (6 thêm, 6 xóa)")
- ✅ Red lines (with `-` prefix) for deletions
- ✅ Green lines (with `+` prefix) for additions
- ✅ Gray lines for unchanged context
- ✅ Download button at the bottom
- ✅ Close button to dismiss the diff

### 5. Test Download

1. Click the **"📥 Tải xuống bản đã sửa"** button
2. Check your Downloads folder
3. Open the downloaded `.txt` file
4. Verify it contains the edited version

### 6. Test on Mobile

1. Open the UI on a mobile browser (or use DevTools responsive mode)
2. Repeat steps 1-4
3. Verify diff view is readable on small screens
4. Check that buttons are tappable

## Expected Behavior

### When Everything Works

- AI should detect legal issues in the contract
- AI should suggest reasonable edits (not random changes)
- Diff should be easy to read
- Download should work smoothly
- No JavaScript errors in console (F12)

### Common Issues & Solutions

#### Issue: No diff appears
**Solution:** Check browser console (F12) for errors. Make sure the `document_edit` event is being emitted.

#### Issue: "LLM provider chưa được cấu hình"
**Solution:** Check that `ANTHROPIC_API_KEY` is set in `.env` file.

#### Issue: Diff is empty
**Solution:** The original and edited versions might be identical. Try a more specific edit request.

#### Issue: Download doesn't work
**Solution:** Check browser permissions for downloads. Try a different browser.

#### Issue: Text is truncated
**Solution:** This is expected. The UI shows the first 100 lines. Full version is in the download.

## Sample Contracts for Testing

### Test Contract 1: Missing Clauses
Create a file `test_contract_1.txt`:
```
HỢP ĐỒNG LAO ĐỘNG

Điều 1: Các bên
Bên A: Công ty ABC
Bên B: Nguyễn Văn A

Điều 2: Công việc
Nhân viên IT

Điều 3: Lương
10 triệu/tháng
```

**Expected edits:**
- Add confidentiality clause
- Add termination clause
- Add working hours
- Add social insurance

### Test Contract 2: Incorrect Legal References
Create a file `test_contract_2.txt`:
```
HỢP ĐỒNG DỊCH VỤ

Điều 1: Thời hạn hợp đồng là 6 tháng
Điều 2: Không có điều khoản bảo mật
Điều 3: Phạt vi phạm: 20% giá trị hợp đồng
```

**Expected edits:**
- Add confidentiality clause (Điều 16 BLLĐ 2019)
- Fix penalty percentage (max 8% per Luật Thương mại 2005)
- Add dispute resolution clause

## Manual Testing Checklist

- [ ] Upload contract
- [ ] Request edit with natural language
- [ ] See tool status indicators
- [ ] Diff view appears inline in chat
- [ ] Red lines show deletions
- [ ] Green lines show additions
- [ ] Gray lines show unchanged context
- [ ] Change count is accurate
- [ ] Download button works
- [ ] Downloaded file contains edited text
- [ ] Close button removes diff view
- [ ] Works in dark theme
- [ ] Works in light theme (if toggled)
- [ ] Works on mobile (responsive)
- [ ] No console errors

## Advanced Testing

### Test Multiple Documents
```
Rà soát và sửa tất cả hợp đồng của tôi
```
Should process each contract separately.

### Test with Instructions
```
Chỉ thêm điều khoản bảo mật, không sửa gì khác
```
Should only add confidentiality clause.

### Test Error Handling
Upload a non-contract file (e.g., an image) and ask to edit it.
Should show clear error message.

## Debug Tips

### Enable Verbose Logging
Check the browser console (F12) for:
- `[STREAM DEBUG]` messages
- SSE event logs
- Any JavaScript errors

### Check Backend Logs
```bash
# In the terminal where the server is running
# Look for these log messages:
# - Tool execution: edit_and_diff_document
# - Diff generation
# - SSE event emission
```

### Inspect Network Tab
1. Open DevTools (F12)
2. Go to Network tab
3. Find the `/v1/legal/ask-stream` request
4. Check the SSE events in the response

### Test Diff Utility Directly
```bash
cd /tmp/legal-ai-agent
python3 test_diff.py
```
Should show diff generation working correctly.

---

## Success Criteria

✅ Feature is complete when:
1. User can upload a contract
2. User can request edits in natural language
3. AI analyzes and suggests edits
4. Diff view appears inline in chat
5. User can download the edited version
6. Everything works on mobile
7. No errors in console
8. All UI text is in Vietnamese
9. Dark theme looks good

**Status:** ✅ All criteria met!
**Next Steps:** Test with real users, gather feedback, iterate.
