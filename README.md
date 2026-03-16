# ⚖️ AI Legal Agent

> **Created by [Hiếu Nguyễn](https://github.com/Paparusi)** — Trader turned Builder 🇻🇳

**Trợ lý pháp lý AI cho doanh nghiệp Việt Nam**

Nền tảng AI giúp tra cứu luật, rà soát hợp đồng, soạn văn bản pháp lý — tất cả trong một giao diện VSCode-style.

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green)
![Claude](https://img.shields.io/badge/AI-Claude%20Sonnet-purple)
![License](https://img.shields.io/badge/License-MIT-yellow)

## 📸 Screenshots

<p align="center">
  <img src="docs/screenshots/landing.jpg" width="800" alt="Landing Page">
  <br><em>Landing Page — Hero, features, pricing</em>
</p>

<p align="center">
  <img src="docs/screenshots/dashboard.jpg" width="800" alt="Dashboard">
  <br><em>Dashboard — VSCode-style 3-panel layout</em>
</p>

<p align="center">
  <img src="docs/screenshots/ai-review.jpg" width="400" alt="AI Contract Review">
  <br><em>AI Contract Review — Phân tích rủi ro, điểm tích cực, khuyến nghị</em>
</p>

<p align="center">
  <img src="docs/screenshots/upload.jpg" width="400" alt="Contract Upload">
  <br><em>Upload hợp đồng — Drag & drop, AI tự động phân tích</em>
</p>

## ✨ Features

### 🤖 AI Agent (11 Tools)
- **Tra cứu luật** — Tìm kiếm trong 40,000+ văn bản pháp luật Việt Nam
- **Rà soát hợp đồng** — Phân tích rủi ro, điều khoản thiếu, đề xuất sửa đổi
- **Kiểm tra compliance** — Check HĐ lao động/thương mại/dịch vụ theo luật VN
- **Soạn điều khoản** — Tạo bảo mật, phạt vi phạm, chấm dứt, bất khả kháng...
- **Tóm tắt HĐ** — Quick summary các bên, giá trị, thời hạn
- **So sánh HĐ** — Diff 2 hợp đồng side-by-side
- **Company memory** — Nhớ context công ty qua các phiên chat

### 📊 Dashboard & Analytics
- Risk Dashboard — Tổng quan rủi ro tất cả HĐ
- Contract Calendar — Lịch HĐ theo tháng
- Usage Analytics — Thống kê sử dụng, top queries
- Audit Log — Nhật ký hoạt động

### 🎯 Enterprise Features
- Batch upload (10 files/lần)
- Report export (.docx)
- Contract versioning & notes
- Smart suggestions (AI gợi ý cải thiện HĐ)
- Bulk analysis (phân tích 20 HĐ cùng lúc)
- Universal search (contracts + docs + laws + chats)
- Template auto-fill
- Onboarding wizard

### 📱 Modern UI
- VSCode-style 3-panel layout
- Dark/Light theme
- Mobile responsive (bottom tab bar)
- PWA installable
- SSE streaming chat
- Command palette (Ctrl+K)
- Keyboard shortcuts

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- PostgreSQL (or Supabase)
- Claude API key ([console.anthropic.com](https://console.anthropic.com))

### 1. Clone & Install

```bash
git clone https://github.com/Paparusi/legal-ai-agent.git
cd legal-ai-agent
pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env with your credentials
```

### 3. Database Setup

```bash
# Run migrations
python scripts/run_migration.py

# Load Vietnamese law data (optional, ~40K documents)
python scripts/load_law_data.py
python scripts/index_chunks.py
```

### 4. Run

```bash
uvicorn src.api.main:app --host 0.0.0.0 --port 8080
```

Open http://localhost:8080/static/app.html

## 📁 Project Structure

```
├── src/
│   ├── api/
│   │   ├── main.py              # FastAPI app + all routes
│   │   ├── routes/              # Route modules
│   │   │   ├── auth.py          # Login, register, API keys
│   │   │   ├── contracts.py     # Contract CRUD
│   │   │   ├── documents.py     # Document upload
│   │   │   ├── chats.py         # Chat history
│   │   │   ├── company.py       # Company management
│   │   │   └── admin.py         # Admin dashboard
│   │   └── middleware/
│   │       ├── auth.py          # API key verification
│   │       └── logging.py       # Usage logging
│   └── agents/
│       ├── legal_agent.py       # AI agent with 11 tools
│       └── company_memory.py    # Company context memory
├── static/
│   ├── app.html                 # Main SPA (~5600 lines)
│   ├── index.html               # Landing page
│   ├── admin.html               # Admin dashboard
│   └── manifest.json            # PWA manifest
├── scripts/
│   ├── load_law_data.py         # Import law documents
│   ├── index_chunks.py          # Chunk & index for search
│   └── run_migration.py         # DB migrations
├── .env.example                 # Environment template
├── requirements.txt
└── Procfile                     # Railway/Heroku deploy
```

## 🔧 API Endpoints

### Auth
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/v1/auth/register` | Đăng ký |
| POST | `/v1/auth/login` | Đăng nhập |
| POST | `/v1/auth/api-key` | Tạo API key |

### AI Chat
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/v1/legal/ask` | Hỏi AI agent |
| POST | `/v1/legal/ask-stream` | Hỏi AI (SSE streaming) |

### Contracts
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/v1/contracts` | Danh sách HĐ |
| POST | `/v1/contracts/upload` | Upload HĐ |
| POST | `/v1/contracts/batch-upload` | Upload nhiều HĐ |
| POST | `/v1/contracts/{id}/review` | AI review HĐ |
| POST | `/v1/contracts/{id}/report` | Export Word report |
| POST | `/v1/contracts/{id}/diff` | So sánh 2 HĐ |
| GET | `/v1/contracts/{id}/suggestions` | AI gợi ý |
| POST | `/v1/contracts/bulk-analyze` | Phân tích hàng loạt |
| GET | `/v1/contracts/calendar` | Lịch HĐ |
| GET | `/v1/contracts/risk-overview` | Tổng quan rủi ro |

### Search
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/v1/legal/search` | Tìm kiếm luật |
| GET | `/v1/search/all` | Tìm kiếm tất cả |

### Analytics
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/v1/analytics` | Thống kê sử dụng |
| GET | `/v1/audit-log` | Nhật ký hoạt động |
| GET | `/v1/insights` | AI insights |

## 🛠️ Tech Stack

- **Backend:** FastAPI + Python
- **AI:** Claude Sonnet (tool_use agent)
- **Database:** PostgreSQL (Supabase)
- **Search:** Full-text search + synonym expansion + TF-IDF ranking
- **Frontend:** Vanilla JS SPA (single HTML file)
- **Deploy:** Railway / any Docker host

## 📝 Vietnamese Law Database

The search engine indexes Vietnamese legal documents including:
- Bộ luật Lao động 2019 (BLLĐ)
- Bộ luật Dân sự 2015 (BLDS)
- Luật Doanh nghiệp 2020
- Luật Thương mại 2005
- Luật Thuế TNDN, TNCN, GTGT
- And 40,000+ more...

## 🤝 Contributing

PRs welcome! Areas that need help:
- [ ] More Vietnamese legal document sources
- [ ] Better NLP for Vietnamese text
- [ ] Test coverage
- [ ] Docker setup
- [ ] Multi-language support

## 📄 License

MIT — sử dụng tự do, kể cả thương mại.

## ⚠️ Disclaimer

Đây là công cụ hỗ trợ, **không thay thế** tư vấn pháp lý chuyên nghiệp. Luôn tham khảo ý kiến luật sư cho các quyết định pháp lý quan trọng.

---

Made with ❤️ by [Hiếu Nguyễn](https://github.com/Paparusi) 🇻🇳
