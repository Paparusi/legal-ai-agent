# ⚖️ AI Legal Agent

🇻🇳 [Tiếng Việt](README_VI.md) | 🇺🇸 English

> **Created by [Lê Minh Hiếu](https://github.com/Paparusi)** — Trader turned Builder 🇻🇳

**AI-powered legal assistant for Vietnamese businesses**

An AI platform for legal research, contract review, and legal document drafting — all in a VSCode-style interface.

![Stars](https://img.shields.io/github/stars/Paparusi/legal-ai-agent?style=flat-square)
![Forks](https://img.shields.io/github/forks/Paparusi/legal-ai-agent?style=flat-square)
![License](https://img.shields.io/github/license/Paparusi/legal-ai-agent?style=flat-square)
![Python](https://img.shields.io/badge/Python-3.10+-blue?style=flat-square)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green?style=flat-square)
![Claude](https://img.shields.io/badge/AI-Claude%20Sonnet-purple?style=flat-square)

---

## 🚀 Used in Production

This project powers **[FundGo Law AI](https://ai.fundgolaw.vn)** 🇻🇳 — a real-world Vietnamese legal AI platform serving businesses across Vietnam.

**Production Stats:**
- 📚 **40,000+** Vietnamese legal documents indexed
- 🔍 **97,000+** searchable chunks
- ⚖️ **11 AI-powered tools** for legal research & contract review
- 🏢 Serving **real clients** with contract analysis, compliance checks, and legal drafting

Trusted, tested, and battle-proven in real legal workflows.

---

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
  <br><em>AI Contract Review — Risk analysis, highlights, recommendations</em>
</p>

<p align="center">
  <img src="docs/screenshots/upload.jpg" width="400" alt="Contract Upload">
  <br><em>Contract Upload — Drag & drop, AI auto-analysis</em>
</p>

## ✨ Features

### 🤖 AI Agent (11 Tools)
- **Legal search** — Search across 40,000+ Vietnamese legal documents
- **Contract review** — Risk analysis, missing clauses, amendment suggestions
- **Compliance check** — Verify labor/commercial/service contracts against Vietnamese law
- **Clause drafting** — Generate confidentiality, penalty, termination, force majeure clauses...
- **Contract summary** — Quick summary of parties, value, duration
- **Contract comparison** — Side-by-side diff of 2 contracts
- **Company memory** — Remembers company context across chat sessions

### 📊 Dashboard & Analytics
- Risk Dashboard — Overview of risks across all contracts
- Contract Calendar — Monthly contract schedule
- Usage Analytics — Usage stats, top queries
- Audit Log — Activity journal

### 🎯 Enterprise Features
- Batch upload (10 files at a time)
- Report export (.docx)
- Contract versioning & notes
- Smart suggestions (AI-powered contract improvements)
- Bulk analysis (analyze 20 contracts simultaneously)
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

### 🐳 Docker (Recommended)

```bash
# 1. Clone
git clone https://github.com/Paparusi/legal-ai-agent.git
cd legal-ai-agent

# 2. Configure
cp .env.example .env
nano .env  # Add your ANTHROPIC_API_KEY

# 3. Start (PostgreSQL + App)
docker compose up -d

# 4. Open
# http://localhost:8080/static/app.html
```

This starts PostgreSQL 15 (with pgvector) and the FastAPI app automatically.

#### 🖥️ Self-hosted (NAS / Xpenology / Synology)

Works on any Docker-capable device — NAS, Raspberry Pi, VPS, or local server.

```bash
# SSH into your NAS/server
git clone https://github.com/Paparusi/legal-ai-agent.git
cd legal-ai-agent
cp .env.example .env

# Edit .env — only ANTHROPIC_API_KEY is required
nano .env

# Start
docker compose up -d

# Access from any device on your network:
# http://NAS_IP:8080/static/app.html
```

**System requirements:**
- Docker + Docker Compose
- 512MB RAM minimum (1GB recommended)
- 1GB disk space
- Any CPU (x86_64 or ARM64)

**Ports:** `8080` (web UI), `5432` (PostgreSQL, optional external access)

**Persistent data:** PostgreSQL data is stored in a Docker volume (`pgdata`). Your data survives container restarts and updates.

**Update to latest version:**
```bash
git pull
docker compose build
docker compose up -d
```

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
├── docker-compose.yml           # One-command deploy
├── Dockerfile                   # Container build
├── .env.example                 # Environment template
├── requirements.txt
└── Procfile                     # Railway/Heroku deploy
```

## 🔧 API Endpoints

### Auth
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/v1/auth/register` | Register |
| POST | `/v1/auth/login` | Login |
| POST | `/v1/auth/api-key` | Generate API key |

### AI Chat
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/v1/legal/ask` | Ask AI agent |
| POST | `/v1/legal/ask-stream` | Ask AI (SSE streaming) |

### Contracts
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/v1/contracts` | List contracts |
| POST | `/v1/contracts/upload` | Upload contract |
| POST | `/v1/contracts/batch-upload` | Batch upload contracts |
| POST | `/v1/contracts/{id}/review` | AI contract review |
| POST | `/v1/contracts/{id}/report` | Export Word report |
| POST | `/v1/contracts/{id}/diff` | Compare 2 contracts |
| GET | `/v1/contracts/{id}/suggestions` | AI suggestions |
| POST | `/v1/contracts/bulk-analyze` | Bulk analysis |
| GET | `/v1/contracts/calendar` | Contract calendar |
| GET | `/v1/contracts/risk-overview` | Risk overview |

### Search
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/v1/legal/search` | Search laws |
| GET | `/v1/search/all` | Search everything |

### Analytics
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/v1/analytics` | Usage statistics |
| GET | `/v1/audit-log` | Activity log |
| GET | `/v1/insights` | AI insights |

## 🛠️ Tech Stack

- **Backend:** FastAPI + Python
- **AI:** Claude Sonnet (tool_use agent)
- **Database:** PostgreSQL (Supabase) with pgvector
- **Search:** Full-text search + synonym expansion + TF-IDF ranking
- **Frontend:** Vanilla JS SPA (single HTML file)
- **Deploy:** Railway / Docker / any container host

## 📝 Vietnamese Law Database

The search engine indexes Vietnamese legal documents including:
- Labor Code 2019 (Bộ luật Lao động)
- Civil Code 2015 (Bộ luật Dân sự)
- Enterprise Law 2020 (Luật Doanh nghiệp)
- Commercial Law 2005 (Luật Thương mại)
- Corporate Income Tax, Personal Income Tax, VAT Laws
- And 40,000+ more...

## 🤝 Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines. Areas that need help:
- [ ] More Vietnamese legal document sources
- [ ] Better NLP for Vietnamese text
- [ ] Test coverage
- [ ] Multi-language support

## 📄 License

MIT — free to use, including commercially.

## ⚠️ Disclaimer

This is an assistive tool and **does not replace** professional legal advice. Always consult a qualified lawyer for important legal decisions.

---

## 💖 Sponsors

Love this project? **[Become a sponsor!](https://github.com/sponsors/Paparusi)** 🙏

Your support helps maintain and expand this **open-source Vietnamese legal AI** platform. By sponsoring, you're supporting:

- 🇻🇳 **Vietnamese open-source** development
- ⚖️ **Democratized legal tech** for small businesses
- 📚 **Free legal AI tools** for everyone
- 🚀 **New features** and improvements

### 💰 Sponsor Tiers

| Tier | Monthly | Benefits |
|------|---------|----------|
| ☕ **Coffee** | $5 | Your name in sponsors list |
| 🥉 **Bronze** | $25 | Logo in README + priority issue response (24h) |
| 🥈 **Silver** | $100 | Direct support channel + feature request priority |
| 🥇 **Gold** | $500 | Prominent logo + custom features + quarterly calls |
| 🏢 **Enterprise** | Custom | SLA, white-label, custom development, private hosting |

**[👉 View all tiers & sponsor now](https://github.com/sponsors/Paparusi)**

_For Enterprise inquiries: [GitHub Issues](https://github.com/Paparusi/legal-ai-agent/issues) or [@gau_trader on Telegram](https://t.me/gau_trader)_

### 🌟 Current Sponsors

_No sponsors yet — **be the first!** Your logo could be here. 🚀_

See [.github/SPONSORS.md](.github/SPONSORS.md) for full details.

---

Made with ❤️ by [Lê Minh Hiếu](https://github.com/Paparusi) 🇻🇳
