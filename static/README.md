# Frontend Dashboard

## Access

**URL:** http://localhost:8080/static/app.html

## Test Credentials

- **Email:** bi@hrvn.vn
- **Password:** Test1234!
- **API Key:** lak_971cbf08c82f678abdf5d112c4e3c6be19f35c2ed17da910

## Features

### 🔐 Authentication
- Login/Register forms with toggle
- Auto token management
- Session persistence via localStorage

### 💬 Chat (Main Feature)
- ChatGPT-style interface
- Markdown rendering with marked.js
- Citation cards below AI responses
- Chat history sidebar
- New chat creation
- Auto-scrolling messages
- "Đang tra cứu..." loading state

### 🔍 Search
- Full-text search across legal documents
- Domain filtering (lao_dong, doanh_nghiep, dan_su, etc.)
- Expandable result cards
- Relevance scoring
- Law name, article, and content preview

### 📋 Contract Review
- Paste contract text
- Review type selector (general, risk, compliance)
- Formatted markdown report output
- Risk level indicators

### ✍️ Document Drafting
- Multiple document types:
  - Hợp đồng lao động
  - Quyết định
  - Công văn
  - Nội quy
  - Hợp đồng mua bán
- Dynamic form fields per doc type
- Download generated documents

### 🔑 API Keys
- List all keys (masked display)
- Create new keys
- Copy to clipboard
- Shows creation date

### 📊 Usage Statistics
- Current month usage progress bar
- Requests used vs quota
- Plan information
- Visual percentage display

### ⚙️ Settings
- View account information
- Display user profile
- Company details

## Tech Stack

- **Pure Vanilla JS** - No frameworks
- **HTML5 + CSS3** - Responsive design
- **marked.js** - Markdown rendering
- **localStorage** - Token persistence
- **Fetch API** - Backend communication

## Design

- **Colors:** Indigo/purple gradient (#667eea primary, #1a1a2e sidebar)
- **Font:** system-ui, -apple-system
- **Style:** Clean, modern, ChatGPT-inspired
- **Responsive:** Mobile-friendly layout
- **Vietnamese UI:** All labels in Vietnamese

## API Integration

- `POST /v1/auth/login` - Login
- `POST /v1/auth/register` - Register
- `GET /v1/auth/me` - User profile
- `POST /v1/legal/ask` - Chat (uses X-API-Key)
- `POST /v1/legal/review` - Contract review (uses X-API-Key)
- `POST /v1/legal/draft` - Document drafting (uses X-API-Key)
- `GET /v1/legal/search` - Search documents (uses X-API-Key)
- `GET /v1/chats` - Chat history
- `GET /v1/chats/{id}` - Load specific chat
- `GET /v1/keys` - List API keys
- `POST /v1/keys` - Create API key
- `GET /v1/usage` - Usage statistics

## Notes

- Auto-creates first API key on login if none exists
- Auto-refresh token handling (401 → logout)
- Toast notifications for errors/success
- Enter to send message (Shift+Enter for newline)
- Chat input auto-resizes up to 120px
- All responses rendered as markdown
- Citations shown as expandable cards
