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

JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "your-super-secret-jwt-key-change-in-production")

# Import new routes
from .routes import auth, company, keys, usage, chats, documents

app = FastAPI(
    title="Legal AI Agent API",
    description="AI-powered Vietnamese Legal Assistant - Tư vấn pháp luật, soạn thảo văn bản, rà soát hợp đồng",
    version="2.0.0"
)

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
CLAUDE_API_URL = "https://api.anthropic.com/v1/messages"

async def call_claude(system_prompt: str, user_message: str, max_tokens: int = 4096) -> dict:
    """Call Claude via OAuth token"""
    headers = {
        "Authorization": f"Bearer {CLAUDE_OAUTH_TOKEN}",
        "anthropic-beta": "oauth-2025-04-20",
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    
    payload = {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": max_tokens,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_message}]
    }
    
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(CLAUDE_API_URL, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        
        return {
            "content": data["content"][0]["text"],
            "input_tokens": data["usage"]["input_tokens"],
            "output_tokens": data["usage"]["output_tokens"],
            "model": data["model"]
        }

# ============================================
# Law Search
# ============================================

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

# ============================================
# API Endpoints
# ============================================

# Root endpoint moved to landing page above

@app.get("/v1/health")
async def health():
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

@app.post("/v1/legal/ask", response_model=LegalResponse)
async def legal_ask(query: LegalQuery, company: dict = Depends(verify_api_key)):
    """Tư vấn pháp luật - Legal Q&A"""
    
    # Search relevant law chunks
    sources = search_laws(query.question, query.domains, query.max_sources)
    
    # Build context from search results
    context_parts = []
    citations = []
    for i, src in enumerate(sources):
        context_parts.append(f"[Nguồn {i+1}] {src['law_title']} - {src.get('article', 'N/A')}\n{src['content'][:2000]}")
        citations.append({
            "source": src["law_title"],
            "law_number": src["law_number"],
            "article": src.get("article"),
            "relevance": float(src.get("rank", 0))
        })
    
    context = "\n\n---\n\n".join(context_parts)
    
    system_prompt = """Bạn là chuyên gia tư vấn pháp luật Việt Nam. Trả lời câu hỏi dựa trên các nguồn luật được cung cấp.

Quy tắc:
1. CHỈ trả lời dựa trên thông tin từ các nguồn luật được cung cấp
2. Trích dẫn cụ thể: Điều, Khoản, Điểm của luật nào
3. Nếu không có đủ thông tin, nói rõ và đề xuất tìm thêm
4. Sử dụng ngôn ngữ dễ hiểu, tránh thuật ngữ phức tạp không cần thiết
5. Nếu có nhiều cách hiểu, trình bày tất cả các góc nhìn
6. Cảnh báo nếu luật có thể đã được sửa đổi"""

    user_message = f"""CÂU HỎI: {query.question}

CÁC NGUỒN LUẬT LIÊN QUAN:
{context}

Hãy trả lời câu hỏi trên, trích dẫn cụ thể các điều luật."""

    result = await call_claude(system_prompt, user_message)
    
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
