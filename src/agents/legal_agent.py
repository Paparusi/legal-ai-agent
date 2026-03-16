"""
Legal AI Agent — Tool-Use Architecture
Uses Claude's native tool_use to autonomously decide which tools to call
based on user questions. Replaces hardcoded Q&A flow.
"""
import json
import httpx
import os
from typing import Optional, List, AsyncGenerator
from psycopg2.extras import RealDictCursor
from .company_memory import get_company_memory, update_company_memory, init_memory

# ============================================
# Shared DB & Claude config (imported from main)
# ============================================

# These will be set by init_agent() called from main.py
_get_db = None
_multi_query_search = None
_search_laws = None
_detect_domain = None
_fetch_company_context = None

CLAUDE_API_URL = "https://api.anthropic.com/v1/messages"


def init_agent(get_db_fn, multi_query_search_fn, search_laws_fn, detect_domain_fn, fetch_company_context_fn):
    """Initialize agent with shared functions from main.py"""
    global _get_db, _multi_query_search, _search_laws, _detect_domain, _fetch_company_context
    _get_db = get_db_fn
    _multi_query_search = multi_query_search_fn
    _search_laws = search_laws_fn
    _detect_domain = detect_domain_fn
    _fetch_company_context = fetch_company_context_fn
    # Initialize company memory with same DB function
    init_memory(get_db_fn)


# ============================================
# Tool Definitions
# ============================================

TOOLS = [
    {
        "name": "search_law",
        "description": "Tìm kiếm văn bản pháp luật Việt Nam theo từ khóa. Dùng khi cần tra cứu luật, nghị định, thông tư, quyết định. LUÔN dùng tool này trước khi trả lời câu hỏi pháp lý.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Từ khóa tìm kiếm pháp luật"},
                "domains": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Lĩnh vực: lao_dong, thue, doanh_nghiep, dan_su, dat_dai, hinh_su, hanh_chinh"
                },
                "limit": {"type": "integer", "default": 10, "description": "Số kết quả tối đa"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "read_contract",
        "description": "Đọc nội dung hợp đồng đã upload. Dùng khi người dùng hỏi về hợp đồng cụ thể hoặc cần rà soát.",
        "input_schema": {
            "type": "object",
            "properties": {
                "contract_id": {"type": "string", "description": "ID hợp đồng (UUID)"}
            },
            "required": ["contract_id"]
        }
    },
    {
        "name": "list_contracts",
        "description": "Liệt kê tất cả hợp đồng của công ty. Dùng khi cần tổng quan về hợp đồng hoặc khi người dùng hỏi 'hợp đồng nào', 'danh sách hợp đồng'.",
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "search_company_docs",
        "description": "Tìm kiếm trong tài liệu nội bộ của công ty (documents đã upload). Dùng khi cần tìm nội quy, quy chế, tài liệu nội bộ.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Từ khóa tìm kiếm trong tài liệu công ty"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "analyze_contract_risk",
        "description": "Phân tích rủi ro pháp lý chi tiết cho hợp đồng. Dùng khi được yêu cầu rà soát, đánh giá rủi ro, hoặc kiểm tra tính hợp pháp của hợp đồng.",
        "input_schema": {
            "type": "object",
            "properties": {
                "contract_id": {"type": "string", "description": "ID hợp đồng cần phân tích"}
            },
            "required": ["contract_id"]
        }
    },
    {
        "name": "draft_document",
        "description": "Soạn thảo văn bản pháp lý mới (hợp đồng, đơn từ, quyết định, biên bản, công văn, nội quy). Dùng khi người dùng yêu cầu soạn/tạo văn bản.",
        "input_schema": {
            "type": "object",
            "properties": {
                "doc_type": {
                    "type": "string",
                    "description": "Loại văn bản: hop_dong, don_tu, quyet_dinh, bien_ban, cong_van, noi_quy, hop_dong_lao_dong, hop_dong_dich_vu"
                },
                "requirements": {
                    "type": "string",
                    "description": "Yêu cầu chi tiết cho văn bản cần soạn"
                },
                "template_id": {
                    "type": "string",
                    "description": "ID template mẫu (optional)"
                }
            },
            "required": ["doc_type", "requirements"]
        }
    },
    {
        "name": "get_company_profile",
        "description": "Lấy thông tin công ty: tên, loại hình, ngành nghề, số nhân sự, hợp đồng đang có, tài liệu. Dùng khi cần context về công ty.",
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "compare_contracts",
        "description": "So sánh 2 hoặc nhiều hợp đồng. Tìm điểm khác biệt, không nhất quán, và đánh giá hợp đồng nào có lợi hơn.",
        "input_schema": {
            "type": "object",
            "properties": {
                "contract_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Danh sách ID hợp đồng cần so sánh (tối thiểu 2)"
                }
            },
            "required": ["contract_ids"]
        }
    },
    {
        "name": "summarize_contract",
        "description": "Tạo tóm tắt ngắn gọn hợp đồng: các bên, giá trị, thời hạn, điều khoản chính. Dùng khi người dùng muốn tóm tắt nhanh.",
        "input_schema": {
            "type": "object",
            "properties": {
                "contract_id": {"type": "string", "description": "ID hợp đồng"}
            },
            "required": ["contract_id"]
        }
    },
    {
        "name": "check_legal_compliance",
        "description": "Kiểm tra hợp đồng có tuân thủ các yêu cầu pháp lý cơ bản không (điều khoản bắt buộc, thời hạn, chế tài...). Dùng khi cần kiểm tra compliance.",
        "input_schema": {
            "type": "object",
            "properties": {
                "contract_id": {"type": "string"},
                "check_type": {"type": "string", "enum": ["labor", "commercial", "service", "all"], "description": "Loại kiểm tra: labor=lao động, commercial=thương mại, service=dịch vụ, all=tất cả"}
            },
            "required": ["contract_id"]
        }
    },
    {
        "name": "generate_clause",
        "description": "Tạo/soạn một điều khoản pháp lý cụ thể. Dùng khi người dùng yêu cầu soạn điều khoản bảo mật, phạt vi phạm, chấm dứt HĐ, v.v.",
        "input_schema": {
            "type": "object",
            "properties": {
                "clause_type": {"type": "string", "description": "Loại điều khoản: bao_mat, phat_vi_pham, cham_dut, boi_thuong, bao_hanh, thanh_toan, tranh_chap, bat_kha_khang"},
                "context": {"type": "string", "description": "Bối cảnh/yêu cầu cụ thể"}
            },
            "required": ["clause_type"]
        }
    }
]

# ============================================
# System Prompt
# ============================================

AGENT_SYSTEM_PROMPT = """Bạn là trợ lý pháp lý AI thông minh. Bạn chat tự nhiên như một người bạn am hiểu luật, KHÔNG phải robot.

## Cách chat:
- **Chat bình thường** — Nếu người dùng chào, hỏi thăm, nói chuyện phiếm → trả lời tự nhiên, thân thiện. KHÔNG dùng tool, KHÔNG format báo cáo.
- **Chat pháp lý** — Khi người dùng hỏi về luật, hợp đồng, văn bản → lúc đó mới dùng tools và trả lời chuyên sâu.
- **Đọc không khí** — Câu ngắn, casual → trả lời ngắn. Câu nghiêm túc, chi tiết → trả lời đầy đủ.
- **Giọng điệu** — Thân thiện, dễ hiểu, như đang nói chuyện. Tránh quá formal hay dùng quá nhiều emoji/header.

## Khi nào dùng tools:
- Hỏi về luật cụ thể → search_law
- Hỏi về hợp đồng → list_contracts / read_contract  
- Cần soạn văn bản → draft_document
- Cần tìm tài liệu → search_company_docs
- Cần rà soát → analyze_contract_risk
- Cần info công ty → get_company_profile
- So sánh hợp đồng → compare_contracts
- Tóm tắt hợp đồng → summarize_contract
- Kiểm tra tuân thủ pháp lý → check_legal_compliance
- Soạn điều khoản cụ thể → generate_clause
- **KHÔNG dùng tool** cho chào hỏi, nói chuyện, câu hỏi đơn giản

## Khi trả lời pháp lý:
- Trích dẫn cụ thể: "Theo Điều X, Khoản Y của Luật Z"
- Không bịa số hiệu — nếu không chắc, nói thẳng
- Đưa lời khuyên thực tế, không chỉ lý thuyết
- Chỉ dùng format có cấu trúc (headers, bullets) khi câu hỏi phức tạp
- Câu hỏi đơn giản → trả lời 2-3 câu là đủ
- Chỉ thêm disclaimer khi tư vấn vụ việc nghiêm trọng

## Upload file:
Khi người dùng upload file trong chat (format [Người dùng đã upload file: ...]), đọc và phân tích trực tiếp nội dung đó. Không cần tìm trong database.

## Nhớ: Bạn là trợ lý THÔNG MINH, không phải máy tìm kiếm. Chat tự nhiên trước, dùng tool khi cần.
"""

# ============================================
# Claude API helpers (with tool_use support)
# ============================================

def _get_claude_headers():
    """Build headers for Claude API"""
    oauth_token = os.getenv("CLAUDE_OAUTH_TOKEN", "")
    api_key = os.getenv("ANTHROPIC_API_KEY", "")

    headers = {
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }

    if oauth_token:
        headers["Authorization"] = f"Bearer {oauth_token}"
        headers["anthropic-beta"] = "oauth-2025-04-20"
    elif api_key:
        headers["x-api-key"] = api_key
    else:
        raise ValueError("No Claude API key or OAuth token configured")

    return headers


async def _call_claude_with_tools(messages: list, tools: list, system: str = AGENT_SYSTEM_PROMPT, max_tokens: int = 8192, model: str = "claude-sonnet-4-20250514") -> dict:
    """Call Claude API with tool definitions, return raw response dict"""
    headers = _get_claude_headers()

    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": messages,
        "tools": tools
    }

    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(CLAUDE_API_URL, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()


# Fast path detection — skip agent loop for simple questions
SIMPLE_PATTERNS = [
    "xin chào", "hello", "hi", "chào", "cảm ơn", "thank", 
    "bạn là ai", "giới thiệu", "bạn có thể làm gì",
    "ok", "được", "tốt", "vâng", "ừ"
]

def is_simple_question(question: str) -> bool:
    """Check if question is simple enough to skip agent loop.
    Only skip for very obvious non-legal greetings/acknowledgments.
    Let Claude decide for everything else — trust the AI."""
    q = question.strip().lower()
    # Only skip for very short, clearly non-legal messages
    if len(q) < 15:
        for p in SIMPLE_PATTERNS:
            if q == p or q.startswith(p + " ") or q.endswith(" " + p):
                return True
    return False


def is_followup_question(question: str, chat_history: list = None) -> bool:
    """Check if this is a follow-up that doesn't need tools"""
    q = question.strip().lower()
    followup_markers = [
        "giải thích thêm", "chi tiết hơn", "ý bạn là gì",
        "ví dụ", "ngoại lệ", "trường hợp", "còn gì nữa",
        "tóm tắt lại", "ngắn gọn hơn", "dịch sang tiếng anh",
        "có gì khác", "so sánh", "tại sao", "cụ thể hơn",
        "nói rõ hơn", "ý nghĩa", "hiểu thế nào", "áp dụng",
        "thực tế", "ví dụ cụ thể", "giải thích", "nghĩa là gì"
    ]
    if any(m in q for m in followup_markers) and chat_history and len(chat_history) >= 2:
        return True
    return False


def generate_quick_replies(question: str, answer: str, tools_used: list) -> list:
    """Generate contextual quick reply suggestions based on tools used and context"""
    suggestions = []

    if 'search_law' in tools_used:
        suggestions.extend([
            {"text": "Phân tích chi tiết hơn", "icon": "📊"},
            {"text": "Điều khoản liên quan", "icon": "🔗"},
            {"text": "So sánh với luật trước đó", "icon": "⚖️"}
        ])
    elif 'read_contract' in tools_used or 'analyze_contract_risk' in tools_used:
        suggestions.extend([
            {"text": "Đề xuất sửa đổi cụ thể", "icon": "✏️"},
            {"text": "Xuất báo cáo rà soát", "icon": "📥"},
            {"text": "So sánh với hợp đồng khác", "icon": "🔄"}
        ])
    elif 'list_contracts' in tools_used:
        suggestions.extend([
            {"text": "Phân tích rủi ro tổng thể", "icon": "⚠️"},
            {"text": "Hợp đồng nào sắp hết hạn?", "icon": "📅"},
            {"text": "So sánh tất cả hợp đồng", "icon": "📊"}
        ])
    elif 'draft_document' in tools_used:
        suggestions.extend([
            {"text": "Chỉnh sửa nội dung", "icon": "✏️"},
            {"text": "Thêm điều khoản bảo mật", "icon": "🔒"},
            {"text": "Xuất ra Word", "icon": "📄"}
        ])
    elif 'search_company_docs' in tools_used:
        suggestions.extend([
            {"text": "Phân tích tài liệu này", "icon": "📊"},
            {"text": "Tìm tài liệu liên quan", "icon": "🔍"},
            {"text": "So sánh với quy định pháp luật", "icon": "⚖️"}
        ])
    else:
        # General/greeting
        suggestions.extend([
            {"text": "Tra cứu luật lao động", "icon": "🔍"},
            {"text": "Rà soát hợp đồng", "icon": "📄"},
            {"text": "Soạn văn bản mới", "icon": "✍️"}
        ])

    return suggestions[:4]  # Max 4 suggestions


def extract_inline_actions(answer_text: str, tools_used: list, tool_results: list) -> list:
    """Extract actionable items from agent response and tool results"""
    actions = []

    for result in tool_results:
        tool_name = result.get("tool", "")
        data = result.get("data", {})

        if tool_name == "list_contracts":
            contracts = data.get("contracts", [])
            for contract in contracts[:3]:
                actions.append({
                    "type": "view_contract",
                    "id": str(contract.get("id", "")),
                    "label": f"📄 {str(contract.get('name', ''))[:40]}"
                })
        elif tool_name == "read_contract" or tool_name == "analyze_contract_risk":
            contract = data.get("contract", {})
            if contract.get("id"):
                actions.append({
                    "type": "view_contract",
                    "id": str(contract["id"]),
                    "label": f"📄 {str(contract.get('name', ''))[:40]}"
                })
        elif tool_name == "search_company_docs":
            docs = data.get("documents", [])
            for doc in docs[:3]:
                actions.append({
                    "type": "view_document",
                    "id": str(doc.get("id", "")),
                    "label": f"📋 {str(doc.get('name', ''))[:40]}"
                })

    return actions


async def quick_answer(question: str, chat_history: list = None) -> dict:
    """Direct Claude call without tools — for simple questions"""
    headers = _get_claude_headers()
    messages = []
    if chat_history:
        for msg in chat_history:
            messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": question})
    
    payload = {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 2048,
        "system": AGENT_SYSTEM_PROMPT,
        "messages": messages
    }
    
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(CLAUDE_API_URL, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
    
    text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
    usage = data.get("usage", {})
    return {
        "answer": text,
        "citations": [],
        "input_tokens": usage.get("input_tokens", 0),
        "output_tokens": usage.get("output_tokens", 0),
        "model": data.get("model", ""),
        "tool_calls_made": 0
    }


async def _call_claude_with_tools_stream(messages: list, tools: list, system: str = AGENT_SYSTEM_PROMPT, max_tokens: int = 8192):
    """Call Claude API with tools + streaming. Yields raw SSE events."""
    headers = _get_claude_headers()

    payload = {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": max_tokens,
        "system": system,
        "messages": messages,
        "tools": tools,
        "stream": True
    }

    async with httpx.AsyncClient(timeout=180) as client:
        async with client.stream("POST", CLAUDE_API_URL, headers=headers, json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str.strip() == "[DONE]":
                        break
                    try:
                        yield json.loads(data_str)
                    except json.JSONDecodeError:
                        continue


async def _stream_final_text(messages: list, system: str = AGENT_SYSTEM_PROMPT) -> AsyncGenerator[str, None]:
    """Stream Claude response without tools — for fast path"""
    headers = _get_claude_headers()
    payload = {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 4096,
        "system": system,
        "messages": messages,
        "stream": True
    }
    async with httpx.AsyncClient(timeout=120) as client:
        async with client.stream("POST", CLAUDE_API_URL, headers=headers, json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str.strip() == "[DONE]":
                        break
                    try:
                        event = json.loads(data_str)
                        if event.get("type") == "content_block_delta":
                            delta = event.get("delta", {})
                            if delta.get("type") == "text_delta":
                                text = delta.get("text", "")
                                if text:
                                    yield f"data: {json.dumps({'type': 'delta', 'text': text}, ensure_ascii=False)}\n\n"
                    except json.JSONDecodeError:
                        continue


# ============================================
# Tool Execution
# ============================================

async def execute_tool(tool_name: str, tool_input: dict, company_id: str) -> dict:
    """Execute a tool and return result dict"""

    if tool_name == "search_law":
        return await _tool_search_law(tool_input, company_id)
    elif tool_name == "read_contract":
        return await _tool_read_contract(tool_input, company_id)
    elif tool_name == "list_contracts":
        return await _tool_list_contracts(company_id)
    elif tool_name == "search_company_docs":
        return await _tool_search_company_docs(tool_input, company_id)
    elif tool_name == "analyze_contract_risk":
        return await _tool_analyze_contract_risk(tool_input, company_id)
    elif tool_name == "draft_document":
        return await _tool_draft_document(tool_input, company_id)
    elif tool_name == "get_company_profile":
        return await _tool_get_company_profile(company_id)
    elif tool_name == "compare_contracts":
        return await _tool_compare_contracts(tool_input, company_id)
    elif tool_name == "summarize_contract":
        contract_id = tool_input.get("contract_id")
        with _get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SELECT name, content, parties, start_date, end_date, contract_type, metadata FROM contracts WHERE id = %s AND company_id = %s AND status != 'deleted'", (contract_id, company_id))
            contract = cur.fetchone()
        if not contract:
            return {"error": "Không tìm thấy hợp đồng"}
        content = contract.get("content", "")[:5000]
        return {
            "name": contract["name"],
            "type": contract.get("contract_type", "N/A"),
            "parties": contract.get("parties", []),
            "start_date": str(contract.get("start_date", "N/A")),
            "end_date": str(contract.get("end_date", "N/A")),
            "content_preview": content,
            "notes": (contract.get("metadata") or {}).get("notes", [])
        }
    elif tool_name == "check_legal_compliance":
        contract_id = tool_input.get("contract_id")
        check_type = tool_input.get("check_type", "all")
        with _get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SELECT name, content, contract_type FROM contracts WHERE id = %s AND company_id = %s AND status != 'deleted'", (contract_id, company_id))
            contract = cur.fetchone()
        if not contract:
            return {"error": "Không tìm thấy hợp đồng"}
        content = contract.get("content", "")[:10000]
        checks = {
            "labor": [
                {"item": "Thông tin người lao động", "keywords": ["họ tên", "ngày sinh", "CMND", "CCCD", "số căn cước"]},
                {"item": "Loại hợp đồng lao động", "keywords": ["xác định thời hạn", "không xác định thời hạn", "thời vụ"]},
                {"item": "Công việc phải làm", "keywords": ["công việc", "nhiệm vụ", "chức danh", "vị trí"]},
                {"item": "Thời giờ làm việc", "keywords": ["giờ làm việc", "thời gian làm việc", "ca làm"]},
                {"item": "Tiền lương", "keywords": ["lương", "tiền công", "thù lao", "mức lương"]},
                {"item": "Bảo hiểm xã hội", "keywords": ["bảo hiểm xã hội", "BHXH", "bảo hiểm y tế", "BHYT"]},
                {"item": "Điều kiện chấm dứt", "keywords": ["chấm dứt", "đơn phương", "thôi việc", "sa thải"]},
            ],
            "commercial": [
                {"item": "Thông tin các bên", "keywords": ["bên A", "bên B", "đại diện", "mã số thuế"]},
                {"item": "Đối tượng hợp đồng", "keywords": ["đối tượng", "hàng hóa", "dịch vụ", "sản phẩm"]},
                {"item": "Giá trị hợp đồng", "keywords": ["giá", "giá trị", "thanh toán", "số tiền"]},
                {"item": "Thời hạn thực hiện", "keywords": ["thời hạn", "ngày giao", "thời gian"]},
                {"item": "Quyền và nghĩa vụ", "keywords": ["quyền", "nghĩa vụ", "trách nhiệm"]},
                {"item": "Phạt vi phạm", "keywords": ["phạt", "vi phạm", "bồi thường"]},
                {"item": "Giải quyết tranh chấp", "keywords": ["tranh chấp", "trọng tài", "tòa án"]},
            ],
            "service": [
                {"item": "Phạm vi dịch vụ", "keywords": ["phạm vi", "nội dung", "dịch vụ"]},
                {"item": "Tiêu chuẩn chất lượng", "keywords": ["chất lượng", "tiêu chuẩn", "KPI"]},
                {"item": "Thời hạn và gia hạn", "keywords": ["thời hạn", "gia hạn", "kéo dài"]},
                {"item": "Bảo mật thông tin", "keywords": ["bảo mật", "thông tin", "confidential"]},
                {"item": "Điều khoản chấm dứt", "keywords": ["chấm dứt", "hủy bỏ", "kết thúc"]},
            ]
        }
        content_lower = content.lower()
        check_types = [check_type] if check_type != "all" else ["labor", "commercial", "service"]
        results = []
        for ct in check_types:
            for check in checks.get(ct, []):
                found = any(kw in content_lower for kw in check["keywords"])
                results.append({
                    "category": ct,
                    "item": check["item"],
                    "status": "pass" if found else "missing",
                    "keywords_found": [kw for kw in check["keywords"] if kw in content_lower]
                })
        passed = sum(1 for r in results if r["status"] == "pass")
        total = len(results)
        return {
            "contract_name": contract["name"],
            "check_type": check_type,
            "score": f"{passed}/{total}",
            "percentage": round(passed/total*100) if total > 0 else 0,
            "results": results,
            "missing_items": [r["item"] for r in results if r["status"] == "missing"]
        }
    elif tool_name == "generate_clause":
        clause_type = tool_input.get("clause_type", "")
        context = tool_input.get("context", "")
        clause_templates = {
            "bao_mat": "ĐIỀU KHOẢN BẢO MẬT THÔNG TIN\n1. Các bên cam kết bảo mật mọi thông tin liên quan đến Hợp đồng này.\n2. Thông tin bảo mật bao gồm nhưng không giới hạn: thông tin kỹ thuật, tài chính, kinh doanh, dữ liệu khách hàng.\n3. Nghĩa vụ bảo mật có hiệu lực trong suốt thời hạn Hợp đồng và [X] năm sau khi chấm dứt.\n4. Bên vi phạm phải bồi thường toàn bộ thiệt hại trực tiếp và gián tiếp.",
            "phat_vi_pham": "ĐIỀU KHOẢN PHẠT VI PHẠM\n1. Bên vi phạm nghĩa vụ hợp đồng phải chịu phạt vi phạm bằng [X]% giá trị hợp đồng.\n2. Mức phạt tối đa không vượt quá 8% giá trị phần nghĩa vụ bị vi phạm (theo Luật Thương mại 2005).\n3. Ngoài tiền phạt, bên vi phạm còn phải bồi thường thiệt hại thực tế phát sinh.\n4. Bên bị vi phạm có quyền yêu cầu phạt vi phạm mà không cần chứng minh thiệt hại.",
            "cham_dut": "ĐIỀU KHOẢN CHẤM DỨT HỢP ĐỒNG\n1. Hợp đồng chấm dứt khi: (a) hết thời hạn, (b) hoàn thành nghĩa vụ, (c) các bên thỏa thuận.\n2. Đơn phương chấm dứt: bên muốn chấm dứt phải thông báo bằng văn bản trước [X] ngày.\n3. Bên đơn phương chấm dứt trái pháp luật phải bồi thường thiệt hại.\n4. Các điều khoản về bảo mật, phạt vi phạm vẫn có hiệu lực sau khi chấm dứt.",
            "boi_thuong": "ĐIỀU KHOẢN BỒI THƯỜNG THIỆT HẠI\n1. Bên gây thiệt hại phải bồi thường đầy đủ, kịp thời.\n2. Thiệt hại được bồi thường bao gồm: thiệt hại trực tiếp, lợi ích bị mất, chi phí hợp lý.\n3. Mức bồi thường tối đa không vượt quá [X]% giá trị hợp đồng.\n4. Bên yêu cầu bồi thường phải chứng minh thiệt hại bằng chứng từ hợp lệ.",
            "thanh_toan": "ĐIỀU KHOẢN THANH TOÁN\n1. Giá trị hợp đồng: [số tiền] VNĐ (bằng chữ: ...).\n2. Phương thức: chuyển khoản ngân hàng.\n3. Tiến độ: (a) Tạm ứng [X]% khi ký, (b) [X]% khi nghiệm thu, (c) [X]% khi hoàn thành.\n4. Thời hạn thanh toán: trong vòng [X] ngày làm việc kể từ ngày nhận hóa đơn hợp lệ.\n5. Chậm thanh toán chịu lãi suất [X]%/tháng trên số tiền chậm.",
            "tranh_chap": "ĐIỀU KHOẢN GIẢI QUYẾT TRANH CHẤP\n1. Mọi tranh chấp phát sinh được giải quyết trước hết bằng thương lượng, hòa giải.\n2. Nếu không thương lượng được trong [X] ngày, tranh chấp sẽ được giải quyết tại [Tòa án/Trọng tài].\n3. Luật áp dụng: pháp luật Việt Nam.\n4. Phán quyết của [Tòa án/Trọng tài] là quyết định cuối cùng, ràng buộc các bên.",
            "bat_kha_khang": "ĐIỀU KHOẢN BẤT KHẢ KHÁNG\n1. Bất khả kháng là sự kiện xảy ra khách quan, không thể lường trước và không thể khắc phục (thiên tai, dịch bệnh, chiến tranh, thay đổi pháp luật...).\n2. Bên gặp bất khả kháng phải thông báo bằng văn bản trong vòng [X] ngày.\n3. Thời hạn thực hiện hợp đồng được gia hạn tương ứng thời gian bất khả kháng.\n4. Nếu bất khả kháng kéo dài quá [X] ngày, các bên có quyền chấm dứt hợp đồng."
        }
        template = clause_templates.get(clause_type, f"Không tìm thấy mẫu cho loại '{clause_type}'. Các loại có sẵn: {', '.join(clause_templates.keys())}")
        return {
            "clause_type": clause_type,
            "template": template,
            "context": context,
            "note": "Đây là mẫu tham khảo. AI sẽ tùy chỉnh theo bối cảnh cụ thể."
        }
    else:
        return {"error": f"Unknown tool: {tool_name}"}


async def _tool_search_law(tool_input: dict, company_id: str) -> dict:
    """Search Vietnamese law database"""
    query = tool_input.get("query", "")
    domains = tool_input.get("domains", None)
    limit = tool_input.get("limit", 10)

    if not domains:
        domains = _detect_domain(query)

    results = _multi_query_search(query, domains, min(limit, 8))

    citations = []
    formatted_results = []
    for i, src in enumerate(results, 1):
        law_title = src.get("law_title", "")
        law_number = src.get("law_number", "N/A")
        article = src.get("article", "N/A")
        content = src.get("content", "")[:1500]

        formatted_results.append({
            "index": i,
            "law_title": law_title,
            "law_number": law_number,
            "article": article,
            "content": content
        })

        citations.append({
            "source": law_title,
            "law_number": law_number,
            "article": article,
            "relevance": float(src.get("rank", 0))
        })

    return {
        "results": formatted_results,
        "total": len(formatted_results),
        "citations": citations
    }


async def _tool_read_contract(tool_input: dict, company_id: str) -> dict:
    """Read a specific contract"""
    contract_id = tool_input.get("contract_id", "")

    with _get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT id, name, contract_type, extracted_text, parties,
                   start_date, end_date, value, status, notes, created_at
            FROM contracts
            WHERE id::text = %s AND company_id = %s AND status != 'deleted'
        """, (contract_id, company_id))
        contract = cur.fetchone()

    if not contract:
        return {"error": f"Không tìm thấy hợp đồng với ID: {contract_id}"}

    result = dict(contract)
    # Convert dates to strings
    for key in ["start_date", "end_date", "created_at"]:
        if result.get(key):
            result[key] = str(result[key])
    # Parse parties JSON
    if result.get("parties"):
        try:
            if isinstance(result["parties"], str):
                result["parties"] = json.loads(result["parties"])
        except:
            pass

    return {
        "contract": result,
        "text_length": len(result.get("extracted_text", "") or "")
    }


async def _tool_list_contracts(company_id: str) -> dict:
    """List all contracts for a company"""
    with _get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT id, name, contract_type, parties, start_date, end_date,
                   value, status, created_at
            FROM contracts
            WHERE company_id = %s AND status != 'deleted'
            ORDER BY created_at DESC
            LIMIT 50
        """, (company_id,))
        contracts = cur.fetchall()

    results = []
    for c in contracts:
        item = dict(c)
        for key in ["start_date", "end_date", "created_at"]:
            if item.get(key):
                item[key] = str(item[key])
        if item.get("parties"):
            try:
                if isinstance(item["parties"], str):
                    item["parties"] = json.loads(item["parties"])
            except:
                pass
        results.append(item)

    return {
        "contracts": results,
        "total": len(results)
    }


async def _tool_search_company_docs(tool_input: dict, company_id: str) -> dict:
    """Search company's uploaded documents"""
    query = tool_input.get("query", "")

    with _get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT id, name, doc_type, extracted_text, analysis, created_at
            FROM documents
            WHERE company_id = %s
              AND extracted_text IS NOT NULL
              AND length(extracted_text) > 50
            ORDER BY created_at DESC
            LIMIT 20
        """, (company_id,))
        docs = cur.fetchall()

    # Filter by relevance
    query_words = [w.lower() for w in query.split() if len(w) > 2]
    relevant = []
    for doc in docs:
        text = (doc.get("extracted_text") or "").lower()
        name = (doc.get("name") or "").lower()
        score = sum(1 for w in query_words if w in text or w in name)
        if score > 0 or not query_words:
            relevant.append({
                "id": str(doc["id"]),
                "name": doc["name"],
                "doc_type": doc.get("doc_type"),
                "excerpt": (doc.get("extracted_text") or "")[:1500],
                "relevance_score": score,
                "created_at": str(doc["created_at"]) if doc.get("created_at") else None
            })

    relevant.sort(key=lambda x: x["relevance_score"], reverse=True)
    return {
        "documents": relevant[:10],
        "total": len(relevant)
    }


async def _tool_analyze_contract_risk(tool_input: dict, company_id: str) -> dict:
    """Analyze contract risk — reads contract + searches relevant laws"""
    contract_id = tool_input.get("contract_id", "")

    # Read the contract
    contract_data = await _tool_read_contract({"contract_id": contract_id}, company_id)
    if "error" in contract_data:
        return contract_data

    contract = contract_data["contract"]
    contract_text = contract.get("extracted_text", "")
    contract_type = contract.get("contract_type", "hợp đồng")

    if not contract_text or len(contract_text) < 50:
        return {"error": "Hợp đồng chưa có nội dung text để phân tích. Vui lòng upload lại file hợp đồng."}

    # Search relevant laws for this contract type
    search_query = f"{contract_type} điều khoản quyền nghĩa vụ"
    law_results = _multi_query_search(search_query, None, 10)

    law_context = []
    for src in law_results:
        law_context.append({
            "law_title": src.get("law_title", ""),
            "law_number": src.get("law_number", ""),
            "article": src.get("article", ""),
            "content": src.get("content", "")[:1000]
        })

    return {
        "contract_name": contract.get("name", ""),
        "contract_type": contract_type,
        "contract_text": contract_text[:15000],
        "parties": contract.get("parties"),
        "relevant_laws": law_context,
        "instruction": "Hãy phân tích rủi ro pháp lý của hợp đồng này dựa trên nội dung và các luật liên quan. Đánh giá: tính hợp pháp, điều khoản thiếu, rủi ro cho các bên, đề xuất sửa đổi."
    }


async def _tool_draft_document(tool_input: dict, company_id: str) -> dict:
    """Prepare context for document drafting"""
    doc_type = tool_input.get("doc_type", "")
    requirements = tool_input.get("requirements", "")
    template_id = tool_input.get("template_id")

    # Search relevant laws for this doc type
    search_query = doc_type.replace("_", " ") + " mẫu quy định"
    law_results = _search_laws(search_query, None, 8)

    law_context = []
    for src in law_results:
        law_context.append({
            "law_title": src.get("law_title", ""),
            "article": src.get("article", ""),
            "content": src.get("content", "")[:1000]
        })

    # Check for template
    template_data = None
    if template_id:
        with _get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("""
                SELECT template_id, name, category, description, template_content
                FROM document_templates
                WHERE template_id = %s
                LIMIT 1
            """, (template_id,))
            row = cur.fetchone()
            if row:
                template_data = dict(row)

    return {
        "doc_type": doc_type,
        "requirements": requirements,
        "relevant_laws": law_context,
        "template": template_data,
        "instruction": f"Soạn thảo văn bản loại '{doc_type}' theo yêu cầu: {requirements}. Tuân thủ Nghị định 30/2020/NĐ-CP về công tác văn thư. Dùng [THÔNG TIN CẦN ĐIỀN] cho phần thiếu."
    }


async def _tool_get_company_profile(company_id: str) -> dict:
    """Get company profile with stats"""
    with _get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Company info
        cur.execute("""
            SELECT id, name, slug, plan, monthly_quota, used_quota, created_at
            FROM companies WHERE id = %s
        """, (company_id,))
        company = cur.fetchone()
        if not company:
            return {"error": "Không tìm thấy thông tin công ty"}

        # Contract stats
        cur.execute("""
            SELECT COUNT(*) as total,
                   COUNT(*) FILTER (WHERE status = 'active') as active,
                   COUNT(*) FILTER (WHERE status = 'expired') as expired
            FROM contracts WHERE company_id = %s AND status != 'deleted'
        """, (company_id,))
        contract_stats = cur.fetchone()

        # Document stats
        cur.execute("""
            SELECT COUNT(*) as total,
                   COUNT(DISTINCT doc_type) as doc_types
            FROM documents WHERE company_id = %s
        """, (company_id,))
        doc_stats = cur.fetchone()

        # User count
        cur.execute("SELECT COUNT(*) as total FROM users WHERE company_id = %s", (company_id,))
        user_stats = cur.fetchone()

    result = dict(company)
    result["created_at"] = str(result["created_at"]) if result.get("created_at") else None
    result["contracts"] = dict(contract_stats) if contract_stats else {}
    result["documents"] = dict(doc_stats) if doc_stats else {}
    result["users"] = dict(user_stats) if user_stats else {}

    return result


async def _tool_compare_contracts(tool_input: dict, company_id: str) -> dict:
    """Compare multiple contracts side-by-side"""
    contract_ids = tool_input.get("contract_ids", [])
    if len(contract_ids) < 2:
        return {"error": "Cần ít nhất 2 hợp đồng để so sánh"}

    contracts_data = []
    for cid in contract_ids[:5]:
        contract_data = await _tool_read_contract({"contract_id": cid}, company_id)
        if "error" in contract_data:
            return {"error": f"Không thể đọc hợp đồng {cid}: {contract_data['error']}"}
        contracts_data.append(contract_data["contract"])

    comparison = []
    for c in contracts_data:
        comparison.append({
            "id": str(c.get("id", "")),
            "name": c.get("name", ""),
            "contract_type": c.get("contract_type", ""),
            "parties": c.get("parties"),
            "start_date": c.get("start_date"),
            "end_date": c.get("end_date"),
            "value": c.get("value"),
            "text_excerpt": (c.get("extracted_text") or "")[:5000]
        })

    return {
        "contracts": comparison,
        "count": len(comparison),
        "instruction": "Hãy so sánh chi tiết các hợp đồng này. Tìm điểm khác biệt, điểm không nhất quán, và đánh giá hợp đồng nào có lợi hơn cho công ty."
    }


# ============================================
# Agent Loop (non-streaming)
# ============================================

async def run_agent(
    question: str,
    company_id: str,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    chat_history: Optional[list] = None
) -> dict:
    """
    Agent loop with fast path for simple questions.
    Includes company memory injection.
    """
    # Build system prompt with company memory
    system_prompt = AGENT_SYSTEM_PROMPT
    try:
        memory_context = await get_company_memory(company_id)
        if memory_context:
            system_prompt = system_prompt + "\n\n" + memory_context
    except Exception:
        pass

    # Fast path — skip tool loop for simple greetings/acknowledgments
    if is_simple_question(question):
        return await quick_answer(question, chat_history)

    # Follow-up fast path
    if is_followup_question(question, chat_history):
        return await quick_answer(question, chat_history)
    
    messages = []
    if chat_history:
        for msg in chat_history:
            messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": question})

    all_citations = []
    total_input_tokens = 0
    total_output_tokens = 0
    max_iterations = 5

    for i in range(max_iterations):
        response = await _call_claude_with_tools(messages, TOOLS, system=system_prompt)

        usage = response.get("usage", {})
        total_input_tokens += usage.get("input_tokens", 0)
        total_output_tokens += usage.get("output_tokens", 0)

        content_blocks = response.get("content", [])
        stop_reason = response.get("stop_reason", "")

        # Check for tool_use blocks
        tool_uses = [b for b in content_blocks if b.get("type") == "tool_use"]

        if not tool_uses or stop_reason == "end_turn":
            # Final text response — no more tool calls
            if not tool_uses:
                text_parts = [b.get("text", "") for b in content_blocks if b.get("type") == "text"]
                final_text = "".join(text_parts)
                return {
                    "answer": final_text,
                    "citations": all_citations,
                    "input_tokens": total_input_tokens,
                    "output_tokens": total_output_tokens,
                    "model": response.get("model", "claude-sonnet-4-20250514"),
                    "tool_calls_made": i
                }

        # Execute tools and feed results back
        messages.append({"role": "assistant", "content": content_blocks})

        tool_results = []
        for tool_use in tool_uses:
            tool_name = tool_use.get("name", "")
            tool_input = tool_use.get("input", {})
            tool_id = tool_use.get("id", "")

            try:
                result = await execute_tool(tool_name, tool_input, company_id)
            except Exception as e:
                result = {"error": f"Tool execution failed: {str(e)}"}

            # Collect citations from search_law
            if tool_name == "search_law" and "citations" in result:
                all_citations.extend(result["citations"])

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tool_id,
                "content": json.dumps(result, ensure_ascii=False, default=str)[:12000]
            })

        messages.append({"role": "user", "content": tool_results})

    # Max iterations reached
    return {
        "answer": "Xin lỗi, tôi không thể xử lý yêu cầu này trong số bước cho phép. Vui lòng thử lại với câu hỏi cụ thể hơn.",
        "citations": all_citations,
        "input_tokens": total_input_tokens,
        "output_tokens": total_output_tokens,
        "model": "claude-sonnet-4-20250514",
        "tool_calls_made": max_iterations
    }


# ============================================
# Agent Loop (streaming with SSE)
# ============================================

TOOL_STATUS_LABELS = {
    "search_law": "🔍 Đang tra cứu văn bản pháp luật...",
    "read_contract": "📋 Đang đọc hợp đồng...",
    "list_contracts": "📋 Đang liệt kê hợp đồng...",
    "search_company_docs": "📄 Đang tìm kiếm tài liệu nội bộ...",
    "analyze_contract_risk": "⚖️ Đang phân tích rủi ro hợp đồng...",
    "draft_document": "✍️ Đang chuẩn bị soạn thảo văn bản...",
    "get_company_profile": "🏢 Đang lấy thông tin công ty...",
    "compare_contracts": "⚖️ Đang so sánh hợp đồng...",
    "summarize_contract": "📋 Đang tóm tắt hợp đồng...",
    "check_legal_compliance": "✅ Đang kiểm tra tuân thủ...",
    "generate_clause": "✍️ Đang soạn điều khoản..."
}


async def run_agent_stream(
    question: str,
    company_id: str,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    chat_history: Optional[list] = None
) -> AsyncGenerator[str, None]:
    """
    Streaming agent loop. Yields SSE events:
    - {"type": "tool_status", "tool": "search_law", "status": "running", "label": "🔍 Đang tra cứu..."}
    - {"type": "tool_status", "tool": "search_law", "status": "done"}
    - {"type": "citations", "citations": [...]}
    - {"type": "delta", "text": "chunk"}
    - {"type": "done", "session_id": "...", "citations": [...]}
    - {"type": "error", "message": "..."}
    """
    messages = []
    if chat_history:
        for msg in chat_history:
            messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": question})

    all_citations = []
    max_iterations = 5
    full_response_text = []

    for iteration in range(max_iterations):
        # For non-final iterations, use non-streaming to get tool calls
        # For final iteration (text response), use streaming
        response = await _call_claude_with_tools(messages, TOOLS)
        content_blocks = response.get("content", [])
        stop_reason = response.get("stop_reason", "")

        tool_uses = [b for b in content_blocks if b.get("type") == "tool_use"]

        if not tool_uses:
            # Final text response — now re-call with streaming for the text
            # Actually, we already have the text from non-streaming call
            text_parts = [b.get("text", "") for b in content_blocks if b.get("type") == "text"]
            final_text = "".join(text_parts)

            # Send citations first
            if all_citations:
                yield f"data: {json.dumps({'type': 'citations', 'citations': all_citations}, ensure_ascii=False)}\n\n"

            # Stream the text in chunks for smooth UX
            chunk_size = 20
            for i in range(0, len(final_text), chunk_size):
                chunk = final_text[i:i+chunk_size]
                yield f"data: {json.dumps({'type': 'delta', 'text': chunk}, ensure_ascii=False)}\n\n"
                full_response_text.append(chunk)

            # Done
            yield f"data: {json.dumps({'type': 'done', 'session_id': session_id, 'citations': all_citations}, ensure_ascii=False)}\n\n"
            return

        # Tool calls needed — execute them
        messages.append({"role": "assistant", "content": content_blocks})

        tool_results = []
        for tool_use in tool_uses:
            tool_name = tool_use.get("name", "")
            tool_input = tool_use.get("input", {})
            tool_id = tool_use.get("id", "")

            # Notify frontend
            label = TOOL_STATUS_LABELS.get(tool_name, f"🔧 Đang xử lý {tool_name}...")
            yield f"data: {json.dumps({'type': 'tool_status', 'tool': tool_name, 'status': 'running', 'label': label}, ensure_ascii=False)}\n\n"

            try:
                result = await execute_tool(tool_name, tool_input, company_id)
            except Exception as e:
                result = {"error": str(e)}

            if tool_name == "search_law" and "citations" in result:
                all_citations.extend(result["citations"])

            yield f"data: {json.dumps({'type': 'tool_status', 'tool': tool_name, 'status': 'done'}, ensure_ascii=False)}\n\n"

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tool_id,
                "content": json.dumps(result, ensure_ascii=False, default=str)[:12000]
            })

        messages.append({"role": "user", "content": tool_results})

    # Max iterations
    yield f"data: {json.dumps({'type': 'error', 'message': 'Đã vượt quá số bước xử lý cho phép'}, ensure_ascii=False)}\n\n"


async def run_agent_stream_final_text(
    question: str,
    company_id: str,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    chat_history: Optional[list] = None
) -> AsyncGenerator[str, None]:
    """
    Enhanced streaming: tool calls use non-streaming, final text uses true streaming.
    Fast path for simple questions and follow-ups.
    Includes: company memory, contextual suggestions, inline actions.
    """
    # Build system prompt with company memory
    system_prompt = AGENT_SYSTEM_PROMPT
    try:
        memory_context = await get_company_memory(company_id)
        if memory_context:
            system_prompt = system_prompt + "\n\n" + memory_context
    except Exception as e:
        print(f"Error loading company memory: {e}")

    # Fast path — simple questions skip tools entirely
    if is_simple_question(question):
        messages = []
        if chat_history:
            for msg in chat_history:
                messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": question})
        
        async for event in _stream_final_text(messages, system=system_prompt):
            yield event
        # Emit suggestions for simple/greeting messages
        suggestions = generate_quick_replies(question, "", [])
        yield f"data: {json.dumps({'type': 'suggestions', 'items': suggestions}, ensure_ascii=False)}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"
        return

    # Follow-up fast path — skip tools for conversational follow-ups
    if is_followup_question(question, chat_history):
        messages = []
        if chat_history:
            for msg in chat_history:
                messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": question})

        full_text_parts = []
        async for event in _stream_final_text(messages, system=system_prompt):
            yield event
            # Collect text for suggestions
            if event.startswith("data: "):
                try:
                    evt = json.loads(event[6:].strip())
                    if evt.get("type") == "delta":
                        full_text_parts.append(evt.get("text", ""))
                except:
                    pass

        answer_text = "".join(full_text_parts)
        suggestions = generate_quick_replies(question, answer_text, [])
        yield f"data: {json.dumps({'type': 'suggestions', 'items': suggestions}, ensure_ascii=False)}\n\n"
        yield f"data: {json.dumps({'type': 'done', 'session_id': session_id})}\n\n"
        return

    messages = []
    if chat_history:
        for msg in chat_history:
            messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": question})

    all_citations = []
    all_tools_used = []
    all_tool_results_data = []  # For inline actions extraction
    max_iterations = 5
    full_response_parts = []

    for iteration in range(max_iterations):
        response = await _call_claude_with_tools(messages, TOOLS, system=system_prompt)
        content_blocks = response.get("content", [])

        tool_uses = [b for b in content_blocks if b.get("type") == "tool_use"]

        if not tool_uses:
            # Final iteration — use the text we already got (no double-call!)
            # Send citations
            if all_citations:
                yield f"data: {json.dumps({'type': 'citations', 'citations': all_citations}, ensure_ascii=False)}\n\n"

            # Consulted laws
            seen_laws = set()
            consulted = []
            for c in all_citations:
                key = f"{c.get('source', '')} ({c.get('law_number', '')})"
                if key not in seen_laws:
                    seen_laws.add(key)
                    consulted.append(key)
            if consulted:
                yield f"data: {json.dumps({'type': 'sources', 'laws_consulted': consulted[:15]}, ensure_ascii=False)}\n\n"

            # Use the text from the non-streaming response directly (avoid double API call)
            text_parts = [b.get("text", "") for b in content_blocks if b.get("type") == "text"]
            final_text = "".join(text_parts)
            
            # Stream it in small chunks for smooth UX
            chunk_size = 15
            for ci in range(0, len(final_text), chunk_size):
                chunk = final_text[ci:ci+chunk_size]
                full_response_parts.append(chunk)
                yield f"data: {json.dumps({'type': 'delta', 'text': chunk}, ensure_ascii=False)}\n\n"

            # Emit inline actions from tool results
            answer_text = "".join(full_response_parts)
            inline_actions = extract_inline_actions(answer_text, all_tools_used, all_tool_results_data)
            if inline_actions:
                yield f"data: {json.dumps({'type': 'inline_actions', 'actions': inline_actions}, ensure_ascii=False)}\n\n"

            # Emit contextual quick reply suggestions
            suggestions = generate_quick_replies(question, answer_text, all_tools_used)
            yield f"data: {json.dumps({'type': 'suggestions', 'items': suggestions}, ensure_ascii=False)}\n\n"

            yield f"data: {json.dumps({'type': 'done', 'session_id': session_id, 'citations': all_citations}, ensure_ascii=False)}\n\n"
            return

        # Tool calls — execute
        messages.append({"role": "assistant", "content": content_blocks})

        tool_results = []
        for tool_use in tool_uses:
            tool_name = tool_use.get("name", "")
            tool_input = tool_use.get("input", {})
            tool_id = tool_use.get("id", "")

            # Track tools used
            if tool_name not in all_tools_used:
                all_tools_used.append(tool_name)

            label = TOOL_STATUS_LABELS.get(tool_name, f"🔧 Đang xử lý {tool_name}...")
            yield f"data: {json.dumps({'type': 'tool_status', 'tool': tool_name, 'status': 'running', 'label': label}, ensure_ascii=False)}\n\n"

            try:
                result = await execute_tool(tool_name, tool_input, company_id)
            except Exception as e:
                result = {"error": str(e)}

            if tool_name == "search_law" and "citations" in result:
                all_citations.extend(result["citations"])

            # Store tool result data for inline actions extraction
            all_tool_results_data.append({"tool": tool_name, "data": result})

            yield f"data: {json.dumps({'type': 'tool_status', 'tool': tool_name, 'status': 'done'}, ensure_ascii=False)}\n\n"

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tool_id,
                "content": json.dumps(result, ensure_ascii=False, default=str)[:12000]
            })

        messages.append({"role": "user", "content": tool_results})

    yield f"data: {json.dumps({'type': 'error', 'message': 'Đã vượt quá số bước xử lý cho phép'}, ensure_ascii=False)}\n\n"
