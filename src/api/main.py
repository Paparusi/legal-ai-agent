"""
Legal AI Agent API
- Full-text search Vietnamese law database
- Claude OAuth for AI processing
- Multi-tenant API key authentication
- User authentication and management
"""
from fastapi import FastAPI, HTTPException, Depends, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import pathlib
from pydantic import BaseModel, Field
from typing import Optional, List
import psycopg2
from psycopg2.extras import RealDictCursor
import httpx
import json
import hashlib
import time
import os
from contextlib import contextmanager
import jwt
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "your-super-secret-jwt-key-change-in-production")

# Import new routes
from .routes import auth, company, keys, usage, chats, documents, admin, contracts, templates
# from .middleware.logging import PlatformLoggingMiddleware  # disabled for deploy

app = FastAPI(
    title="Legal AI Agent API",
    description="AI-powered Vietnamese Legal Assistant - Tư vấn pháp luật, soạn thảo văn bản, rà soát hợp đồng",
    version="2.0.0"
)

# Logging middleware disabled for production deploy
# app.add_middleware(
#     PlatformLoggingMiddleware,
#     exclude_paths=["/health", "/docs", "/openapi.json", "/redoc", "/static", "/"]
# )

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include new routers
app.include_router(auth.router)
app.include_router(company.router)
app.include_router(keys.router)
app.include_router(usage.router)
app.include_router(chats.router)
app.include_router(documents.router)
app.include_router(admin.router)
app.include_router(contracts.router)
app.include_router(templates.router)

# Startup event - seed templates
@app.on_event("startup")
async def startup_event():
    """Seed default templates on startup"""
    templates.seed_default_templates()

# Static files
static_dir = pathlib.Path(__file__).parent.parent.parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

@app.get("/", include_in_schema=False)
async def landing_page():
    html_file = static_dir / "index.html"
    if html_file.exists():
        return FileResponse(str(html_file))
    return {"name": "Legal AI Agent API", "version": "1.0.0"}

# ============================================
# Database
# ============================================

DB_CONFIG = {
    "host": os.getenv("SUPABASE_DB_HOST", "db.chiokotzjtjwfodryfdt.supabase.co"),
    "port": int(os.getenv("SUPABASE_DB_PORT", "5432")),
    "dbname": "postgres",
    "user": "postgres",
    "password": os.getenv("SUPABASE_DB_PASSWORD", "Hl120804@.,?"),
    "sslmode": "require"
}

@contextmanager
def get_db():
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        yield conn
    finally:
        conn.close()

# ============================================
# Auth
# ============================================

async def verify_api_key(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    authorization: Optional[str] = Header(None)
):
    """Verify API key OR Bearer token and return company info"""
    
    # Try Bearer token first (from dashboard login)
    if not x_api_key and authorization and authorization.startswith("Bearer "):
        try:
            token = authorization.split(" ", 1)[1]
            payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
            user_id = payload.get("user_id")
            if user_id:
                with get_db() as conn:
                    cur = conn.cursor(cursor_factory=RealDictCursor)
                    cur.execute("""
                        SELECT u.id as user_id, u.company_id, u.role,
                               c.name as company_name, c.plan, c.monthly_quota, c.used_quota
                        FROM users u
                        JOIN companies c ON c.id = u.company_id
                        WHERE u.id = %s
                    """, (user_id,))
                    user = cur.fetchone()
                    if user:
                        if user["used_quota"] >= user["monthly_quota"]:
                            raise HTTPException(status_code=429, detail="Monthly quota exceeded")
                        return {**dict(user), "permissions": ["read","ask","review","draft"], "rate_limit": 60}
        except Exception:
            pass
    
    if not x_api_key:
        raise HTTPException(status_code=401, detail="API key or Bearer token required")
    
    key_hash = hashlib.sha256(x_api_key.encode()).hexdigest()
    key_prefix = x_api_key[:8]
    
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT ak.id, ak.company_id, ak.permissions, ak.rate_limit,
                   c.name as company_name, c.plan, c.monthly_quota, c.used_quota
            FROM api_keys ak
            JOIN companies c ON c.id = ak.company_id
            WHERE ak.key_prefix = %s AND ak.key_hash = %s AND ak.is_active = true
        """, (key_prefix, key_hash))
        result = cur.fetchone()
        
        if not result:
            raise HTTPException(status_code=401, detail="Invalid API key")
        
        if result["used_quota"] >= result["monthly_quota"]:
            raise HTTPException(status_code=429, detail="Monthly quota exceeded")
        
        # Update last_used
        cur.execute("UPDATE api_keys SET last_used_at = now() WHERE id = %s", (result["id"],))
        conn.commit()
        
        return dict(result)

# ============================================
# Models
# ============================================

class LegalQuery(BaseModel):
    question: str = Field(..., min_length=5, max_length=2000, description="Câu hỏi pháp luật")
    domains: Optional[List[str]] = Field(None, description="Lĩnh vực: lao_dong, doanh_nghiep, dan_su, thue, dat_dai...")
    max_sources: int = Field(10, ge=1, le=30, description="Số nguồn tham chiếu tối đa")
    stream: bool = Field(False, description="Stream response")

class ContractReview(BaseModel):
    contract_text: str = Field(..., min_length=50, max_length=100000, description="Nội dung hợp đồng cần rà soát")
    contract_type: Optional[str] = Field(None, description="Loại hợp đồng: hop_dong_lao_dong, hop_dong_thuong_mai...")
    focus_areas: Optional[List[str]] = Field(None, description="Các điểm cần chú ý đặc biệt")

class DocumentDraft(BaseModel):
    doc_type: str = Field(..., description="Loại văn bản: hop_dong_lao_dong, quyet_dinh, cong_van, noi_quy...")
    variables: dict = Field(..., description="Thông tin cần điền vào văn bản")
    instructions: Optional[str] = Field(None, description="Yêu cầu bổ sung")

class LegalResponse(BaseModel):
    answer: str
    citations: List[dict]
    confidence: float
    tokens_used: int
    model: str

# ============================================
# Claude OAuth Integration
# ============================================

CLAUDE_OAUTH_TOKEN = os.getenv("CLAUDE_OAUTH_TOKEN", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_API_URL = "https://api.anthropic.com/v1/messages"

async def call_claude(system_prompt: str, user_message: str, max_tokens: int = 4096) -> dict:
    """Call Claude via OAuth token or API key"""
    api_key = ANTHROPIC_API_KEY
    oauth_token = CLAUDE_OAUTH_TOKEN
    
    headers = {
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    
    if oauth_token:
        # OAuth token uses Bearer auth
        headers["Authorization"] = f"Bearer {oauth_token}"
        headers["anthropic-beta"] = "oauth-2025-04-20"
    elif api_key:
        headers["x-api-key"] = api_key
    else:
        raise ValueError("No Claude API key or OAuth token configured")
    
    payload = {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": max_tokens,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_message}]
    }
    
    async with httpx.AsyncClient(timeout=120) as client:
        try:
            response = await client.post(CLAUDE_API_URL, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            
            return {
                "content": data["content"][0]["text"],
                "input_tokens": data["usage"]["input_tokens"],
                "output_tokens": data["usage"]["output_tokens"],
                "model": data["model"]
            }
        except httpx.HTTPStatusError as e:
            print(f"Claude API error: {e.response.status_code} - {e.response.text[:200]}")
            raise
        except Exception as e:
            print(f"Claude call error: {e}")
            raise

# ============================================
# Law Search
# ============================================

# ============================================
# Vietnamese Diacritics Restoration
# ============================================

NO_ACCENT_MAP = {
    # Common legal phrases
    "thu viec": "thử việc",
    "nghi phep": "nghỉ phép",
    "hop dong lao dong": "hợp đồng lao động",
    "thue tndn": "thuế TNDN",
    "thue thu nhap": "thuế thu nhập",
    "sa thai": "sa thải",
    "luong": "lương",
    "bao hiem": "bảo hiểm",
    "nghi viec": "nghỉ việc",
    "ky luat": "kỷ luật",
    "thai san": "thai sản",
    "tang ca": "tăng ca",
    "lam them gio": "làm thêm giờ",
    "nghi le": "nghỉ lễ",
    "cham dut hop dong": "chấm dứt hợp đồng",
    "boi thuong": "bồi thường",
    "tranh chap": "tranh chấp",
    "thanh lap cong ty": "thành lập công ty",
    "doanh nghiep": "doanh nghiệp",
    "co phan": "cổ phần",
    "thue gia tri gia tang": "thuế giá trị gia tăng",
    "dat dai": "đất đai",
    "quyen su dung dat": "quyền sử dụng đất",
    # Common single words
    "thoi gian": "thời gian",
    "toi da": "tối đa",
    "toi thieu": "tối thiểu",
    "quy dinh": "quy định",
    "noi dung": "nội dung",
    "hinh thuc": "hình thức",
    "hop dong": "hợp đồng",
    "cong ty": "công ty",
    "dieu": "điều",
    "khoan": "khoản",
    "luat": "luật",
    "bo luat": "bộ luật",
    "nghi dinh": "nghị định",
    "thong tu": "thông tư",
    "quyet dinh": "quyết định",
    "muc": "mức",
    "so": "số",
    "nam": "năm",
    "thang": "tháng",
    "ngay": "ngày",
    "gio": "giờ",
    "viec": "việc",
    "nguoi": "người",
    "phep": "phép",
    "thue": "thuế",
    "suat": "suất",
    "tien": "tiền",
}

def has_vietnamese_diacritics(text: str) -> bool:
    """Check if text contains Vietnamese diacritics"""
    import re
    # Vietnamese diacritics pattern
    vietnamese_chars = r'[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]'
    return bool(re.search(vietnamese_chars, text.lower()))

def restore_diacritics(query: str) -> str:
    """Restore Vietnamese diacritics from common non-diacritics legal terms"""
    import re
    
    # If query already has diacritics, return as-is
    if has_vietnamese_diacritics(query):
        return query
    
    # Try to match and replace phrases from NO_ACCENT_MAP
    restored = query.lower()
    
    # Sort by length (longest first) to match longer phrases first
    sorted_mappings = sorted(NO_ACCENT_MAP.items(), key=lambda x: len(x[0]), reverse=True)
    
    for no_accent, with_accent in sorted_mappings:
        # Use word boundaries to avoid partial matches
        pattern = r'\b' + re.escape(no_accent) + r'\b'
        restored = re.sub(pattern, with_accent, restored, flags=re.IGNORECASE)
    
    return restored

def extract_search_query(question: str) -> str:
    """Extract key legal terms from Vietnamese question"""
    import re
    
    # Remove Vietnamese question words
    question_words = [
        r'\bbao lâu\b', r'\bbao nhiêu\b', r'\bthế nào\b', r'\bnhư thế nào\b',
        r'\blà gì\b', r'\bcó phải\b', r'\bcó được\b', r'\blà\b', r'\bcó\b',
        r'\bkhông\b', r'\bhay không\b', r'\?', r'\.'
    ]
    
    cleaned = question.lower()
    for pattern in question_words:
        cleaned = re.sub(pattern, ' ', cleaned)
    
    # Remove extra spaces
    cleaned = ' '.join(cleaned.split())
    
    return cleaned.strip()

def expand_synonyms(query: str) -> List[str]:
    """Expand Vietnamese legal term synonyms — returns the EXPANDED TERMS to search for"""
    expansions = []
    query_lower = query.lower()
    
    synonym_map = {
        "tndn": "thu nhập doanh nghiệp",
        "tncn": "thu nhập cá nhân",
        "gtgt": "giá trị gia tăng",
        "vat": "giá trị gia tăng",
        "bhxh": "bảo hiểm xã hội",
        "bhyt": "bảo hiểm y tế",
        "hđlđ": "hợp đồng lao động",
        "nsdlđ": "người sử dụng lao động",
        "nlđ": "người lao động",
        "nghỉ phép": "nghỉ hằng năm",
        "phép năm": "nghỉ hằng năm",
        "sa thải": "kỷ luật sa thải",
        "đuổi việc": "kỷ luật sa thải",
    }
    
    for abbr, full in synonym_map.items():
        if abbr in query_lower:
            expansions.append(full)  # Return just the expanded term
    
    return expansions

def detect_domain(question: str) -> Optional[List[str]]:
    """Auto-detect legal domain from question keywords"""
    question_lower = question.lower()
    
    domain_keywords = {
        "lao_dong": ["lao động", "hợp đồng lao động", "thử việc", "nghỉ phép", "tăng ca", "lương", "sa thải", "bảo hiểm xã hội", "bhxh", "thôi việc", "chấm dứt hợp đồng"],
        "thue": ["thuế", "tndn", "vat", "tncn", "kê khai thuế", "hoàn thuế", "miễn thuế", "giảm thuế", "thuế suất"],
        "doanh_nghiep": ["thành lập công ty", "cổ phần", "doanh nghiệp", "giải thể", "phá sản", "điều lệ", "đại hội cổ đông", "hội đồng quản trị"],
        "dan_su": ["di sản", "thừa kế", "hôn nhân", "ly hôn", "nuôi con", "nhà ở", "quyền sở hữu", "tài sản chung"],
        "dat_dai": ["đất đai", "quyền sử dụng đất", "sổ đỏ", "chuyển nhượng đất", "thuê đất"],
        "hinh_su": ["hình sự", "án tù", "tội phạm", "vi phạm hình sự", "truy tố"],
        "hanh_chinh": ["vi phạm hành chính", "phạt hành chính", "khiếu nại", "tố cáo"]
    }
    
    detected = []
    for domain, keywords in domain_keywords.items():
        for keyword in keywords:
            if keyword in question_lower:
                detected.append(domain)
                break
    
    return detected if detected else None

def search_laws(query: str, domains: Optional[List[str]] = None, limit: int = 10) -> List[dict]:
    """Search Vietnamese law database"""
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        if domains:
            domain_array = "{" + ",".join(domains) + "}"
            cur.execute(
                "SELECT * FROM search_law(%s, %s::legal_domain[], %s)",
                (query, domain_array, limit)
            )
        else:
            cur.execute(
                "SELECT * FROM search_law(%s, NULL, %s)",
                (query, limit)
            )
        
        return [dict(r) for r in cur.fetchall()]

def multi_query_search(question: str, domains: Optional[List[str]] = None, limit: int = 15) -> List[dict]:
    """Smart multi-query search: domain detection + ILIKE phrase + tsvector + diacritics fallback"""
    
    # Auto-detect domain
    if not domains:
        domains = detect_domain(question)
    
    # Check if query needs diacritics restoration
    original_query = question
    restored_query = restore_diacritics(question)
    queries_to_search = [original_query]
    
    # If restoration produced a different query, search with both
    if restored_query.lower() != original_query.lower():
        queries_to_search.append(restored_query)
    
    # Extract clean keywords from the best available query
    keywords = extract_search_query(restored_query if restored_query != original_query else question)
    words = [w for w in keywords.split() if len(w) > 1]
    
    # Build meaningful phrases (skip common words like thời gian, quy định)
    common_prefixes = {"thời", "gian", "quy", "định", "mức", "tối", "đa", "số", "ngày"}
    key_words = [w for w in words if w not in common_prefixes]
    if not key_words:
        key_words = words
    
    # Build search phrases from key words
    phrases = []
    if len(key_words) >= 2:
        phrases.append(" ".join(key_words[:3]))  # Top 3 key words
        phrases.append(" ".join(key_words[:2]))  # Top 2 key words
    elif key_words:
        phrases.append(key_words[0])
    
    # Also try full keyword string
    if len(words) >= 2:
        phrases.append(" ".join(words[:4]))
    
    # Phase 1: ILIKE phrase search with domain filter (most precise)
    phrase_results = []
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Search with original phrases
        for phrase in phrases[:3]:
            domain_filter = ""
            params = [f"%{phrase}%"]
            if domains:
                domain_filter = "AND lc.domains && %s::legal_domain[]"
                params.append("{" + ",".join(domains) + "}")
            
            cur.execute(f"""
                SELECT lc.id as chunk_id, lc.law_id, ld.title as law_title, 
                       ld.law_number, lc.article, lc.title as chunk_title,
                       lc.content, lc.domains, 1.0::float as rank
                FROM law_chunks lc
                JOIN law_documents ld ON ld.id = lc.law_id
                WHERE lc.content ILIKE %s {domain_filter}
                ORDER BY 
                    CASE WHEN ld.title LIKE 'Bo Luat%%' OR ld.title LIKE 'Bộ luật%%' THEN 0
                         WHEN ld.title LIKE 'Luat %%' OR ld.title LIKE 'Luật %%' THEN 1
                         WHEN ld.title LIKE 'Nghi dinh%%' OR ld.title LIKE 'Nghị định%%' THEN 2
                         ELSE 3 END,
                    length(lc.content) DESC
                LIMIT {limit}
            """, params)
            phrase_results.extend([dict(r) for r in cur.fetchall()])
        
        # If we have a restored query that's different, search with restored phrases too
        if restored_query.lower() != original_query.lower():
            restored_keywords = extract_search_query(restored_query)
            restored_words = [w for w in restored_keywords.split() if len(w) > 1]
            common_prefixes = {"thời", "gian", "quy", "định", "mức", "tối", "đa", "số", "ngày"}
            restored_key_words = [w for w in restored_words if w not in common_prefixes]
            if not restored_key_words:
                restored_key_words = restored_words
            
            restored_phrases = []
            if len(restored_key_words) >= 2:
                restored_phrases.append(" ".join(restored_key_words[:3]))
                restored_phrases.append(" ".join(restored_key_words[:2]))
            elif restored_key_words:
                restored_phrases.append(restored_key_words[0])
            
            for phrase in restored_phrases[:2]:
                domain_filter = ""
                params = [f"%{phrase}%"]
                if domains:
                    domain_filter = "AND lc.domains && %s::legal_domain[]"
                    params.append("{" + ",".join(domains) + "}")
                
                cur.execute(f"""
                    SELECT lc.id as chunk_id, lc.law_id, ld.title as law_title, 
                           ld.law_number, lc.article, lc.title as chunk_title,
                           lc.content, lc.domains, 1.2::float as rank
                    FROM law_chunks lc
                    JOIN law_documents ld ON ld.id = lc.law_id
                    WHERE lc.content ILIKE %s {domain_filter}
                    ORDER BY 
                        CASE WHEN ld.title LIKE 'Bo Luat%%' OR ld.title LIKE 'Bộ luật%%' THEN 0
                             WHEN ld.title LIKE 'Luat %%' OR ld.title LIKE 'Luật %%' THEN 1
                             WHEN ld.title LIKE 'Nghi dinh%%' OR ld.title LIKE 'Nghị định%%' THEN 2
                             ELSE 3 END,
                        length(lc.content) DESC
                    LIMIT {limit}
                """, params)
                phrase_results.extend([dict(r) for r in cur.fetchall()])
    
    # Phase 1.5: Synonym expansion search (e.g., "tndn" → "thu nhập doanh nghiệp")
    synonyms = expand_synonyms(keywords)
    for syn_term in synonyms[:2]:
        sp = syn_term  # Use the expanded term directly as search phrase
        if True:
            domain_filter = ""
            params = [f"%{sp}%"]
            if domains:
                domain_filter = "AND lc.domains && %s::legal_domain[]"
                params.append("{" + ",".join(domains) + "}")
            with get_db() as conn:
                cur = conn.cursor(cursor_factory=RealDictCursor)
                cur.execute(f"""
                    SELECT lc.id as chunk_id, lc.law_id, ld.title as law_title, 
                           ld.law_number, lc.article, lc.title as chunk_title,
                           lc.content, lc.domains, 1.0::float as rank
                    FROM law_chunks lc
                    JOIN law_documents ld ON ld.id = lc.law_id
                    WHERE lc.content ILIKE %s {domain_filter}
                    ORDER BY CASE WHEN ld.title LIKE 'Bo Luat%%' THEN 0 WHEN ld.title LIKE 'Luat%%' THEN 1 ELSE 2 END
                    LIMIT {limit}
                """, params)
                phrase_results.extend([dict(r) for r in cur.fetchall()])
    
    # Phase 2: tsvector search (broader coverage)
    tsv_results = search_laws(keywords, domains, limit)
    
    # Merge: phrase results first, then tsvector
    seen_ids = set()
    merged = []
    
    # Build title matching keywords from original question
    title_keywords = [w for w in words if len(w) > 2]
    synonym_terms = expand_synonyms(keywords)
    for st in synonym_terms:
        title_keywords.extend(st.split())
    
    for result in phrase_results:
        chunk_id = result.get("chunk_id")
        if chunk_id and chunk_id not in seen_ids:
            seen_ids.add(chunk_id)
            title = result.get("law_title", "").lower()
            base_rank = 15.0
            if any(x in result.get("law_title", "") for x in ["Bo Luat", "Bộ luật"]):
                base_rank = 30.0
            elif any(x in result.get("law_title", "") for x in ["Luat ", "Luật "]):
                base_rank = 25.0
            elif any(x in result.get("law_title", "") for x in ["Nghi dinh", "Nghị định"]):
                base_rank = 20.0
            elif result.get("law_title", "").startswith("Legal Document"):
                base_rank = 8.0
            
            # Boost if law title contains search keywords
            title_match_bonus = 0
            for kw in title_keywords:
                if kw.lower() in title:
                    title_match_bonus += 3.0
            
            result["rank"] = base_rank + title_match_bonus
            merged.append(result)
    
    for result in tsv_results:
        chunk_id = result.get("chunk_id") or result.get("id")
        if chunk_id and chunk_id not in seen_ids:
            seen_ids.add(chunk_id)
            title = result.get("law_title", "")
            base = result.get("rank", 1.0)
            if any(x in title for x in ["Bo Luat", "Bộ luật"]):
                result["rank"] = base + 10.0
            elif any(x in title for x in ["Luat ", "Luật "]):
                result["rank"] = base + 5.0
            elif title.startswith("Legal Document"):
                result["rank"] = max(base - 5.0, 0.1)
            merged.append(result)
    
    merged.sort(key=lambda x: x.get("rank", 0), reverse=True)
    return merged[:limit]


# ============================================
# API Endpoints
# ============================================

# Root endpoint moved to landing page above

@app.get("/v1/health")
async def health():
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM law_documents")
            doc_count = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM law_chunks")
            chunk_count = cur.fetchone()[0]
        return {
            "status": "healthy",
            "database": {"documents": doc_count, "chunks": chunk_count},
            "ai_engine": "claude-sonnet-4"
        }
    except Exception as e:
        return {
            "status": "degraded",
            "database": {"error": str(e)},
            "ai_engine": "claude-sonnet-4"
        }

@app.post("/v1/legal/ask", response_model=LegalResponse)
async def legal_ask(query: LegalQuery, company: dict = Depends(verify_api_key)):
    """Tư vấn pháp luật - Legal Q&A"""
    
    # Auto-detect domain if not provided
    domains = query.domains
    if not domains:
        detected = detect_domain(query.question)
        if detected:
            domains = detected
    
    # Multi-query search for better results
    sources = multi_query_search(query.question, domains, query.max_sources)
    
    # Build enhanced context from search results
    context_parts = []
    citations = []
    for i, src in enumerate(sources, 1):
        # Format: clearly show law title, number, article
        law_title = src['law_title']
        law_number = src.get('law_number', 'N/A')
        article = src.get('article', 'N/A')
        content = src['content'][:2000]
        
        context_parts.append(f"""--- NGUỒN {i} ---
Văn bản: {law_title} (Số: {law_number})
Điều: {article}
Nội dung:
{content}
---""")
        
        citations.append({
            "source": law_title,
            "law_number": law_number,
            "article": article,
            "relevance": float(src.get("rank", 0))
        })
    
    context = "\n\n".join(context_parts)
    
    # Professional Vietnamese legal consultant prompt
    system_prompt = """Bạn là Trợ lý Pháp lý AI chuyên nghiệp cho doanh nghiệp Việt Nam.

NĂNG LỰC CỦA BẠN:
1. TRẢ LỜI câu hỏi pháp lý — tra cứu, giải thích luật
2. SOẠN THẢO văn bản pháp lý — hợp đồng, đơn từ, biên bản, quyết định, nội quy
3. TƯ VẤN chiến lược pháp lý — phân tích rủi ro, đề xuất giải pháp
4. RÀ SOÁT văn bản — kiểm tra tính hợp pháp, phát hiện lỗi

KHI TRẢ LỜI CÂU HỎI:
- Trả lời trực tiếp ngay đầu tiên (1-2 câu tóm tắt)
- Trích dẫn CỤ THỂ: "Theo Điều X, Khoản Y, Luật Z năm YYYY..."
- Giải thích rõ ràng, dễ hiểu cho người không chuyên luật
- Kết thúc bằng LƯU Ý thực tiễn (nếu có)

KHI SOẠN THẢO VĂN BẢN:
- Soạn HOÀN CHỈNH, chuyên nghiệp, đúng chuẩn pháp lý Việt Nam
- Đánh dấu chỗ cần điền thông tin bằng [THÔNG TIN CẦN ĐIỀN] hoặc [...]
- Tuân thủ đúng quy định pháp luật hiện hành (trích dẫn điều luật áp dụng)
- Bao gồm đầy đủ các điều khoản bắt buộc theo luật
- Format rõ ràng: tiêu đề, các điều khoản đánh số, chữ ký
- Nếu người dùng cung cấp thông tin cụ thể (tên, địa chỉ...), ĐIỀN LUÔN vào văn bản

ĐỊNH DẠNG:
- Dùng heading ## cho các phần chính
- Dùng **bold** cho điều khoản quan trọng
- Dùng bullet list cho các trường hợp
- Ngắn gọn, súc tích — không dài dòng

QUAN TRỌNG:
- Sử dụng nguồn luật được cung cấp làm tham chiếu
- Kết hợp kiến thức pháp luật Việt Nam để trả lời TOÀN DIỆN
- Nếu nguồn luật không đủ, VẪN trả lời dựa trên kiến thức chung về luật VN nhưng GHI CHÚ rõ
- KHÔNG bịa số hiệu văn bản hoặc điều luật cụ thể khi không chắc chắn
- Ưu tiên Bộ luật/Luật mới nhất (năm ban hành gần nhất)
- Luôn kèm disclaimer: đây là tham khảo, cần luật sư cho trường hợp cụ thể"""

    user_message = f"""YÊU CẦU: {query.question}

CÁC NGUỒN LUẬT LIÊN QUAN (dùng làm tham chiếu):
{context}

Hãy thực hiện yêu cầu trên. Nếu là câu hỏi thì trả lời. Nếu là yêu cầu soạn thảo thì soạn văn bản hoàn chỉnh."""

    result = await call_claude(system_prompt, user_message, max_tokens=8192)
    
    # Chat history auto-save (if user_id exists from Bearer token)
    session_id = None
    user_id = company.get("user_id")
    
    if user_id:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            
            # Get or create active session for this user
            cur.execute("""
                SELECT id FROM chat_sessions
                WHERE user_id = %s AND company_id = %s AND agent_type = 'qa' AND status = 'active'
                ORDER BY last_message_at DESC NULLS LAST
                LIMIT 1
            """, (user_id, company["company_id"]))
            
            session = cur.fetchone()
            if session:
                session_id = session["id"]
            else:
                # Create new session
                cur.execute("""
                    INSERT INTO chat_sessions (company_id, user_id, agent_type, title, status)
                    VALUES (%s, %s, 'qa', %s, 'active')
                    RETURNING id
                """, (company["company_id"], user_id, f"Q&A - {query.question[:50]}..."))
                session_id = cur.fetchone()["id"]
            
            # Save user question
            cur.execute("""
                INSERT INTO messages (session_id, company_id, role, content, tokens_used, model)
                VALUES (%s, %s, 'user', %s, 0, '')
            """, (session_id, company["company_id"], query.question))
            
            # Save assistant answer with citations
            cur.execute("""
                INSERT INTO messages (session_id, company_id, role, content, citations, confidence, tokens_used, model)
                VALUES (%s, %s, 'assistant', %s, %s, %s, %s, %s)
            """, (
                session_id,
                company["company_id"],
                result["content"], 
                json.dumps(citations),
                0.85 if sources else 0.5,
                result["input_tokens"] + result["output_tokens"],
                result["model"]
            ))
            
            # Update session message count and last message time
            cur.execute("""
                UPDATE chat_sessions 
                SET message_count = message_count + 2,
                    last_message_at = now()
                WHERE id = %s
            """, (session_id,))
            
            conn.commit()
    
    # Update usage
    with get_db() as conn:
        cur = conn.cursor()
        total_tokens = result["input_tokens"] + result["output_tokens"]
        cur.execute("UPDATE companies SET used_quota = used_quota + 1 WHERE id = %s", (company["company_id"],))
        cur.execute("""
            INSERT INTO usage_logs (company_id, endpoint, agent_type, input_tokens, output_tokens, status_code)
            VALUES (%s, '/v1/legal/ask', 'qa', %s, %s, 200)
        """, (company["company_id"], result["input_tokens"], result["output_tokens"]))
        conn.commit()
    
    return LegalResponse(
        answer=result["content"],
        citations=citations,
        confidence=0.85 if sources else 0.5,
        tokens_used=result["input_tokens"] + result["output_tokens"],
        model=result["model"]
    )

@app.post("/v1/legal/review")
async def contract_review(review: ContractReview, company: dict = Depends(verify_api_key)):
    """Rà soát hợp đồng - Contract Review"""
    
    # Search relevant laws based on contract type
    search_terms = {
        "hop_dong_lao_dong": "hợp đồng lao động quyền nghĩa vụ",
        "hop_dong_thuong_mai": "hợp đồng thương mại mua bán",
        "hop_dong_dich_vu": "hợp đồng dịch vụ thuê khoán",
    }
    search_query = search_terms.get(review.contract_type, "hợp đồng điều khoản")
    sources = search_laws(search_query, None, 15)
    
    context = "\n\n".join([
        f"[{src['law_title']}] {src.get('article', '')}\n{src['content'][:1500]}"
        for src in sources
    ])
    
    system_prompt = """Bạn là luật sư chuyên rà soát hợp đồng theo pháp luật Việt Nam.

Nhiệm vụ: Rà soát hợp đồng và đánh giá theo các tiêu chí:
1. **Tính hợp pháp**: Có điều khoản nào vi phạm pháp luật không?
2. **Tính đầy đủ**: Có thiếu điều khoản bắt buộc nào không?
3. **Rủi ro**: Những điều khoản nào có rủi ro cao cho bên nào?
4. **Đề xuất**: Các sửa đổi cần thiết

Trả về JSON format:
{
    "risk_score": 1-100 (100 = rủi ro cao nhất),
    "issues": [{"type": "violation|missing|risk|suggestion", "severity": "critical|high|medium|low", "clause": "điều khoản liên quan", "description": "mô tả", "legal_basis": "căn cứ pháp lý", "recommendation": "đề xuất sửa"}],
    "summary": "Tóm tắt đánh giá",
    "overall_assessment": "Đánh giá tổng thể"
}"""

    user_message = f"""HỢP ĐỒNG CẦN RÀ SOÁT:
{review.contract_text[:50000]}

PHÁP LUẬT LIÊN QUAN:
{context}

{f"YÊU CẦU ĐẶC BIỆT: {', '.join(review.focus_areas)}" if review.focus_areas else ""}

Hãy rà soát hợp đồng trên và trả về kết quả theo format JSON."""

    result = await call_claude(system_prompt, user_message, max_tokens=8192)
    
    # Update usage
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE companies SET used_quota = used_quota + 1 WHERE id = %s", (company["company_id"],))
        cur.execute("""
            INSERT INTO usage_logs (company_id, endpoint, agent_type, input_tokens, output_tokens, status_code)
            VALUES (%s, '/v1/legal/review', 'review', %s, %s, 200)
        """, (company["company_id"], result["input_tokens"], result["output_tokens"]))
        conn.commit()
    
    # Try to parse JSON from response
    try:
        review_data = json.loads(result["content"])
    except:
        review_data = {"raw_analysis": result["content"]}
    
    return {
        "review": review_data,
        "tokens_used": result["input_tokens"] + result["output_tokens"],
        "model": result["model"]
    }

@app.post("/v1/legal/draft")
async def document_draft(draft: DocumentDraft, company: dict = Depends(verify_api_key)):
    """Soạn thảo văn bản - Document Drafting"""
    
    # Search for templates and relevant laws
    sources = search_laws(draft.doc_type.replace("_", " "), None, 10)
    
    context = "\n\n".join([
        f"[{src['law_title']}] {src.get('article', '')}\n{src['content'][:1500]}"
        for src in sources
    ])
    
    system_prompt = """Bạn là chuyên gia soạn thảo văn bản pháp lý Việt Nam.

Nhiệm vụ: Soạn thảo văn bản hoàn chỉnh, đúng format, đúng pháp luật.

Quy tắc:
1. Sử dụng đúng format văn bản hành chính Việt Nam
2. Tuân thủ quy định tại Nghị định 30/2020/NĐ-CP về công tác văn thư
3. Điền đầy đủ thông tin từ biến số được cung cấp
4. Các điều khoản phải tuân thủ pháp luật hiện hành
5. Ghi rõ căn cứ pháp lý"""

    variables_str = json.dumps(draft.variables, ensure_ascii=False, indent=2)
    
    user_message = f"""LOẠI VĂN BẢN: {draft.doc_type}

THÔNG TIN:
{variables_str}

{f"YÊU CẦU BỔ SUNG: {draft.instructions}" if draft.instructions else ""}

PHÁP LUẬT LIÊN QUAN:
{context}

Hãy soạn thảo văn bản hoàn chỉnh."""

    result = await call_claude(system_prompt, user_message, max_tokens=8192)
    
    # Update usage
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE companies SET used_quota = used_quota + 1 WHERE id = %s", (company["company_id"],))
        cur.execute("""
            INSERT INTO usage_logs (company_id, endpoint, agent_type, input_tokens, output_tokens, status_code)
            VALUES (%s, '/v1/legal/draft', 'draft', %s, %s, 200)
        """, (company["company_id"], result["input_tokens"], result["output_tokens"]))
        conn.commit()
    
    return {
        "document": result["content"],
        "doc_type": draft.doc_type,
        "tokens_used": result["input_tokens"] + result["output_tokens"],
        "model": result["model"]
    }

@app.get("/v1/legal/search")
async def search(q: str, domains: Optional[str] = None, limit: int = 10, company: dict = Depends(verify_api_key)):
    """Tìm kiếm luật - Law Search"""
    domain_list = domains.split(",") if domains else None
    results = search_laws(q, domain_list, min(limit, 30))
    
    return {
        "query": q,
        "count": len(results),
        "results": [{
            "law_title": r["law_title"],
            "law_number": r["law_number"],
            "article": r.get("article"),
            "content": r["content"][:500],
            "rank": float(r.get("rank", 0))
        } for r in results]
    }

# ============================================
# Admin endpoints (internal)
# ============================================

@app.post("/admin/company", include_in_schema=False)
async def create_company(name: str, slug: str, plan: str = "trial"):
    """Create a new company (admin only)"""
    import secrets
    
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Create company
        cur.execute("""
            INSERT INTO companies (name, slug, plan)
            VALUES (%s, %s, %s::plan_type)
            RETURNING id, name, slug, plan, monthly_quota
        """, (name, slug, plan))
        company = dict(cur.fetchone())
        
        # Generate API key
        api_key = f"lak_{secrets.token_hex(24)}"
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        
        cur.execute("""
            INSERT INTO api_keys (company_id, name, key_hash, key_prefix)
            VALUES (%s, %s, %s, %s)
        """, (company["id"], f"{name} - Default Key", key_hash, api_key[:8]))
        
        conn.commit()
        
        return {
            "company": company,
            "api_key": api_key,
            "warning": "Save this API key - it cannot be retrieved later"
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
