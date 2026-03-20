# Contract Diff View Feature

## Overview

This feature allows the Legal AI Agent to analyze, edit, and display contract changes in an inline diff view (similar to VSCode), making it easy for users to review AI-suggested edits before accepting them.

## What Was Built

### 1. Backend Changes

#### New Tool: `edit_and_diff_document`
- **Location:** `src/agents/legal_agent.py` (line ~350)
- **Description:** AI tool that reads a document, analyzes it for legal issues, generates an edited version, and creates a diff view
- **Input:**
  - `document_id` (required): UUID of the document/contract
  - `edit_instructions` (optional): Specific editing instructions
  - `auto_fix` (default: True): Automatically fix common legal issues
- **Output:** Returns diff metadata including original, edited, diff_html, additions, deletions, changes_count

#### Diff Utility Service
- **Location:** `src/services/diff_utils.py`
- **Function:** `generate_inline_diff(original: str, edited: str) -> dict`
- Uses Python's `difflib` to compare texts line-by-line
- Generates HTML-formatted diff with color-coded additions/deletions
- Smart context display (shows only changed sections + 3 lines of context)
- Returns structured diff data for frontend rendering

#### Streaming Integration
- **Location:** `src/agents/legal_agent.py` (line ~2370)
- When `edit_and_diff_document` tool is executed, a special SSE event is emitted:
  ```python
  {
    "type": "document_edit",
    "original": "...",
    "edited": "...",
    "filename": "...",
    "changes": "summary",
    "diff_html": "...",
    "additions": 5,
    "deletions": 3,
    "changes_count": 8
  }
  ```

### 2. Frontend Changes

#### CSS Styling
- **Location:** `static/app.html` (before `</style>`)
- `.diff-container`: Main container with border and rounded corners
- `.diff-header`: Shows filename and change statistics
- `.diff-body`: Scrollable diff content area (max 500px height)
- `.diff-line`: Individual line styling
- `.diff-add`: Green background for added lines (with `+` prefix)
- `.diff-del`: Red background for deleted lines (with `−` prefix)
- `.diff-unchanged`: Muted color for unchanged context lines
- `.diff-actions`: Footer with action buttons
- Dark theme compatible using CSS variables
- Mobile-friendly with responsive design

#### JavaScript Functions

##### `renderDiffView(original, edited, filename, changesSummary, additions, deletions, changesCount)`
- **Location:** `static/app.html` (after `renderCitation()`)
- Generates inline diff HTML from original and edited text
- Limits display to first 100 lines for performance
- Escapes HTML to prevent XSS
- Returns complete HTML structure for diff view

##### `downloadEditedDocument(text, filename)`
- **Location:** `static/app.html` (after `renderDiffView()`)
- Creates a downloadable .txt file with the edited content
- Uses Blob API to create download link
- Shows success toast notification

#### Event Handler
- **Location:** `static/app.html` (inside `sendMessageStreamEnhanced()`)
- Listens for `document_edit` or `diff` event types
- Calls `renderDiffView()` and appends result to chat message
- Automatically scrolls to show the diff

### 3. System Prompt Update
- **Location:** `src/agents/legal_agent.py` (line ~400)
- Added guidance for when to use `edit_and_diff_document`
- Suggests tool for "rà soát và sửa", "chỉnh sửa hợp đồng", "fix hợp đồng" queries

### 4. Tool Status Label
- **Location:** `src/agents/legal_agent.py` (TOOL_STATUS_LABELS)
- Added: `"edit_and_diff_document": "✏️ Đang chỉnh sửa và tạo diff view..."`

## How It Works

### User Flow

1. **User uploads a contract** (e.g., PDF)
2. **User asks:** "Rà soát và chỉnh sửa hợp đồng này"
3. **AI analyzes the contract** using existing tools (search_law, analyze_contract_risk)
4. **AI calls `edit_and_diff_document` tool** with the contract ID
5. **Backend:**
   - Reads the original contract from database
   - Sends it to Claude with instructions to fix legal issues
   - Receives edited version
   - Generates diff using `diff_utils.py`
   - Emits `document_edit` SSE event with diff data
6. **Frontend:**
   - Receives `document_edit` event
   - Calls `renderDiffView()` to create HTML
   - Displays inline diff in the chat message
7. **User reviews changes** (green = added, red = deleted)
8. **User downloads edited version** by clicking "📥 Tải xuống"

### Example Output

```
📄 Hop_Dong_Lao_Dong.docx
12 thay đổi (6 thêm, 6 xóa)
─────────────────────────────────
  Điều 3: Thời hạn hợp đồng
- Hợp đồng có hiệu lực 1 năm
+ Hợp đồng có hiệu lực 1 năm, tự động gia hạn theo Điều 22 BLLĐ 2019

  Điều 4: Lương cơ bản

- Chưa có điều khoản bảo mật
+ Điều 5: Bảo mật thông tin
+ Các bên cam kết bảo mật theo Điều 16 BLLĐ 2019
─────────────────────────────────
[📥 Tải xuống] [❌ Đóng]
```

## Technical Details

### Diff Algorithm
- Uses `difflib.Differ()` for line-by-line comparison
- Handles Vietnamese text correctly (UTF-8)
- Smart context: shows only changed sections + 3 lines around each change
- Ellipsis (`...`) for long unchanged sections

### Performance
- Limits frontend rendering to 100 lines to avoid browser slowdown
- Backend processes full document but only sends necessary data
- Streaming ensures UI remains responsive during processing

### Security
- HTML escaping in `renderDiffView()` prevents XSS
- Document access controlled by `company_id` (multi-tenant safe)
- No direct file system writes (downloads use browser Blob API)

### Error Handling
- If LLM provider is not configured, returns error message
- If document not found, returns clear error
- If diff generation fails, falls back to showing text only

## Testing

Run the included test:
```bash
cd /tmp/legal-ai-agent
python3 test_diff.py
```

Expected output:
```
✅ Changes count: 9
✅ Additions: 6
✅ Deletions: 3
✅ Summary: +6 dòng thêm, -3 dòng xóa
```

## Usage Examples

### Basic Edit Request
```
User: "Rà soát hợp đồng này và sửa các lỗi pháp lý"
```

### Specific Edit
```
User: "Bổ sung điều khoản bảo mật vào hợp đồng"
```

### With Instructions
```
User: "Chỉnh sửa hợp đồng để tuân thủ BLLĐ 2019"
```

## Future Enhancements

- [ ] Side-by-side diff view (desktop only)
- [ ] Accept/reject individual changes
- [ ] Export to Word with track changes
- [ ] Diff comparison with law articles (show legal citations inline)
- [ ] Version history (save edited versions)

## Files Modified

1. `src/agents/legal_agent.py` (+150 lines)
2. `src/services/diff_utils.py` (new file, 200 lines)
3. `static/app.html` (+200 lines CSS + JS)
4. `test_diff.py` (new file, test script)

## Compatibility

- ✅ Dark theme
- ✅ Light theme
- ✅ Mobile responsive
- ✅ Vietnamese text
- ✅ Long documents (100+ lines)
- ✅ Special characters
- ✅ Multiple sessions

## Known Limitations

- Max 100 lines displayed in frontend (full version available via download)
- Inline diff only (no side-by-side on desktop)
- Plain text output (no Word formatting preservation)
- Requires ANTHROPIC_API_KEY for edit generation

---

**Commit:** `631005c`
**Status:** ✅ Complete and pushed to `origin/main`
