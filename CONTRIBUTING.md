# Contributing to AI Legal Agent

Thank you for your interest in contributing! This guide will help you get started.

## 🛠️ Development Setup

### Prerequisites
- Python 3.10+
- PostgreSQL 15+ (or use Docker)
- A Claude API key from [console.anthropic.com](https://console.anthropic.com)

### Local Setup

```bash
# 1. Fork & clone
git clone https://github.com/<your-username>/legal-ai-agent.git
cd legal-ai-agent

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env with your database and API credentials

# 5. Run database migrations
python scripts/run_migration.py

# 6. Start the dev server
uvicorn src.api.main:app --host 0.0.0.0 --port 8080 --reload
```

### Docker Setup (Recommended)

```bash
cp .env.example .env
# Edit .env with your credentials

docker compose up -d
```

## 📁 Project Structure

```
src/
├── api/
│   ├── main.py              # FastAPI app entry point, route registration
│   ├── routes/              # API route modules
│   │   ├── auth.py          # Authentication (login, register, API keys)
│   │   ├── contracts.py     # Contract CRUD and analysis
│   │   ├── documents.py     # Document upload handling
│   │   ├── chats.py         # Chat history management
│   │   ├── company.py       # Company profile management
│   │   └── admin.py         # Admin dashboard endpoints
│   └── middleware/
│       ├── auth.py          # API key verification middleware
│       └── logging.py       # Request/response logging
├── agents/
│   ├── legal_agent.py       # Core AI agent with 11 tools (Claude tool_use)
│   └── company_memory.py    # Persistent company context across sessions
├── rag/
│   ├── embedder.py          # Text embedding for vector search
│   └── search.py            # Full-text + vector search engine
├── services/
│   └── supabase_client.py   # Database connection and queries
└── models/
    └── schemas.py           # Pydantic models for request/response

static/                      # Frontend (vanilla JS SPA)
scripts/                     # Database migrations, data loading, indexing
data/                        # Sample/seed data
```

## 🤖 Adding a New AI Tool

The AI agent uses Claude's `tool_use` feature. To add a new tool:

1. **Define the tool** in `src/agents/legal_agent.py`:

```python
# Add to the TOOLS list
{
    "name": "your_tool_name",
    "description": "What this tool does — be specific so Claude knows when to use it",
    "input_schema": {
        "type": "object",
        "properties": {
            "param1": {
                "type": "string",
                "description": "Description of param1"
            }
        },
        "required": ["param1"]
    }
}
```

2. **Implement the handler** in the same file:

```python
async def handle_your_tool_name(params: dict) -> str:
    """Process the tool call and return results as a string."""
    param1 = params["param1"]
    # Your logic here
    return "Result string that Claude will use in its response"
```

3. **Register it** in the tool dispatch logic (the `if/elif` chain that routes tool calls).

4. **Test it** by asking the AI a question that should trigger your tool.

## 📝 Pull Request Guidelines

### Before Submitting

- [ ] Test your changes locally
- [ ] Ensure existing functionality still works
- [ ] Update documentation if needed
- [ ] Keep commits focused and well-described

### PR Process

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Make your changes
4. Commit with descriptive messages: `git commit -m "feat: add contract template export"`
5. Push to your fork: `git push origin feature/your-feature`
6. Open a PR against `master`

### Commit Message Convention

We loosely follow [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` — New feature
- `fix:` — Bug fix
- `docs:` — Documentation only
- `refactor:` — Code change that neither fixes a bug nor adds a feature
- `style:` — Formatting, missing semicolons, etc.
- `test:` — Adding or updating tests
- `chore:` — Maintenance tasks

### What We're Looking For

- **Vietnamese legal data sources** — More law documents, court decisions, etc.
- **Vietnamese NLP improvements** — Better tokenization, synonym handling
- **Test coverage** — Unit and integration tests
- **Performance** — Search speed, response time optimizations
- **Accessibility** — i18n, a11y improvements

## 💬 Questions?

Open an issue or start a discussion on GitHub. We're happy to help!
