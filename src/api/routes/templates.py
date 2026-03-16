"""
Document Template Management
- List, get, generate documents from templates
- User's generated documents management
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from psycopg2.extras import RealDictCursor
import json
from datetime import datetime

from ..middleware.auth import get_db, get_current_user

router = APIRouter(prefix="/v1/templates", tags=["Templates"])

# ============================================
# Models
# ============================================

class GenerateDocumentRequest(BaseModel):
    template_id: str = Field(..., description="Template ID")
    variables: Dict[str, Any] = Field(..., description="Template variables")

# ============================================
# Default Templates Data
# ============================================

DEFAULT_TEMPLATES = [
    {
        "template_id": "hop_dong_lao_dong",
        "name": "Hợp đồng lao động",
        "category": "hop_dong",
        "description": "Mẫu hợp đồng lao động chuẩn theo BLLĐ 2019",
        "variables": {
            "company_name": {"label": "Tên công ty", "type": "text", "required": True},
            "employee_name": {"label": "Tên nhân viên", "type": "text", "required": True},
            "position": {"label": "Vị trí", "type": "text", "required": True},
            "salary": {"label": "Mức lương", "type": "number", "required": True},
            "start_date": {"label": "Ngày bắt đầu", "type": "date", "required": True},
            "contract_type": {"label": "Loại HĐ", "type": "select", "options": ["Xác định thời hạn", "Không xác định thời hạn"], "required": True},
            "duration_months": {"label": "Thời hạn (tháng)", "type": "number", "required": False},
        }
    },
    {
        "template_id": "hop_dong_dich_vu",
        "name": "Hợp đồng dịch vụ",
        "category": "hop_dong",
        "description": "Mẫu hợp đồng cung cấp dịch vụ",
        "variables": {
            "provider_name": {"label": "Bên cung cấp", "type": "text", "required": True},
            "client_name": {"label": "Bên sử dụng", "type": "text", "required": True},
            "service_description": {"label": "Mô tả dịch vụ", "type": "textarea", "required": True},
            "fee": {"label": "Phí dịch vụ", "type": "number", "required": True},
            "duration": {"label": "Thời hạn", "type": "text", "required": True},
        }
    },
    {
        "template_id": "quyet_dinh",
        "name": "Quyết định",
        "category": "hanh_chinh",
        "description": "Mẫu quyết định nội bộ công ty",
        "variables": {
            "company_name": {"label": "Tên công ty", "type": "text", "required": True},
            "decision_number": {"label": "Số quyết định", "type": "text", "required": True},
            "subject": {"label": "Nội dung quyết định", "type": "textarea", "required": True},
            "effective_date": {"label": "Ngày hiệu lực", "type": "date", "required": True},
        }
    },
    {
        "template_id": "cong_van",
        "name": "Công văn",
        "category": "hanh_chinh",
        "description": "Mẫu công văn gửi đi/nhận",
        "variables": {
            "sender": {"label": "Đơn vị gửi", "type": "text", "required": True},
            "recipient": {"label": "Đơn vị nhận", "type": "text", "required": True},
            "subject": {"label": "Trích yếu", "type": "text", "required": True},
            "content": {"label": "Nội dung", "type": "textarea", "required": True},
        }
    },
    {
        "template_id": "noi_quy",
        "name": "Nội quy lao động",
        "category": "noi_bo",
        "description": "Nội quy lao động công ty theo BLLĐ 2019",
        "variables": {
            "company_name": {"label": "Tên công ty", "type": "text", "required": True},
            "working_hours": {"label": "Giờ làm việc", "type": "text", "required": True},
            "leave_policy": {"label": "Chính sách nghỉ phép", "type": "textarea", "required": False},
        }
    },
    {
        "template_id": "bien_ban_hop",
        "name": "Biên bản họp",
        "category": "noi_bo",
        "description": "Mẫu biên bản cuộc họp",
        "variables": {
            "meeting_title": {"label": "Tiêu đề cuộc họp", "type": "text", "required": True},
            "date": {"label": "Ngày họp", "type": "date", "required": True},
            "attendees": {"label": "Thành phần tham dự", "type": "textarea", "required": True},
            "agenda": {"label": "Nội dung", "type": "textarea", "required": True},
        }
    },
    {
        "template_id": "thong_bao",
        "name": "Thông báo",
        "category": "hanh_chinh",
        "description": "Mẫu thông báo nội bộ/đối ngoại",
        "variables": {
            "company_name": {"label": "Tên công ty", "type": "text", "required": True},
            "subject": {"label": "Nội dung thông báo", "type": "textarea", "required": True},
            "effective_date": {"label": "Ngày hiệu lực", "type": "date", "required": True},
        }
    },
    {
        "template_id": "hop_dong_thue",
        "name": "Hợp đồng thuê nhà",
        "category": "hop_dong",
        "description": "Mẫu hợp đồng thuê mặt bằng/nhà ở",
        "variables": {
            "landlord": {"label": "Bên cho thuê", "type": "text", "required": True},
            "tenant": {"label": "Bên thuê", "type": "text", "required": True},
            "address": {"label": "Địa chỉ", "type": "text", "required": True},
            "rent": {"label": "Tiền thuê/tháng", "type": "number", "required": True},
            "deposit": {"label": "Tiền đặt cọc", "type": "number", "required": True},
            "duration": {"label": "Thời hạn thuê", "type": "text", "required": True},
        }
    }
]

# ============================================
# Seed Function
# ============================================

def seed_default_templates():
    """Seed default templates into database if empty"""
    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            
            # Check if templates already exist
            cur.execute("SELECT COUNT(*) as count FROM document_templates")
            result = cur.fetchone()
            
            if result["count"] > 0:
                print(f"✓ Templates already seeded ({result['count']} templates)")
                return
            
            # Insert default templates
            for template in DEFAULT_TEMPLATES:
                cur.execute("""
                    INSERT INTO document_templates 
                    (template_id, name, category, description, variables, sections)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (template_id) DO NOTHING
                """, (
                    template["template_id"],
                    template["name"],
                    template["category"],
                    template["description"],
                    json.dumps(template["variables"]),
                    json.dumps([])  # Empty sections for now
                ))
            
            conn.commit()
            print(f"✓ Seeded {len(DEFAULT_TEMPLATES)} default templates")
    
    except Exception as e:
        print(f"✗ Error seeding templates: {e}")

# ============================================
# Endpoints
# ============================================

@router.get("")
async def list_templates():
    """List all active document templates"""
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("""
            SELECT 
                id, template_id, name, category, description,
                variables, version, usage_count, created_at
            FROM document_templates
            WHERE is_active = true
            ORDER BY category, name
        """)
        
        templates = cur.fetchall()
    
    return {
        "templates": [
            {
                "id": str(t["id"]),
                "template_id": t["template_id"],
                "name": t["name"],
                "category": t["category"],
                "description": t["description"],
                "variables": t["variables"],
                "version": t["version"],
                "usage_count": t["usage_count"],
                "created_at": t["created_at"].isoformat()
            }
            for t in templates
        ],
        "count": len(templates)
    }

@router.get("/{template_id}")
async def get_template(template_id: str):
    """Get template details"""
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("""
            SELECT 
                id, template_id, name, category, description,
                variables, sections, legal_basis, version,
                sample_output, usage_count, created_at
            FROM document_templates
            WHERE template_id = %s AND is_active = true
        """, (template_id,))
        
        template = cur.fetchone()
        
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
    
    return {
        "id": str(template["id"]),
        "template_id": template["template_id"],
        "name": template["name"],
        "category": template["category"],
        "description": template["description"],
        "variables": template["variables"],
        "sections": template["sections"],
        "legal_basis": template["legal_basis"],
        "version": template["version"],
        "sample_output": template["sample_output"],
        "usage_count": template["usage_count"],
        "created_at": template["created_at"].isoformat()
    }

@router.post("/generate")
async def generate_document(
    request: GenerateDocumentRequest,
    current_user: dict = Depends(get_current_user)
):
    """Generate document from template using Claude"""
    
    # Get template
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("""
            SELECT template_id, name, category, variables, legal_basis
            FROM document_templates
            WHERE template_id = %s AND is_active = true
        """, (request.template_id,))
        
        template = cur.fetchone()
        
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
    
    # Validate required variables
    template_vars = template["variables"]
    for var_name, var_config in template_vars.items():
        if var_config.get("required") and var_name not in request.variables:
            raise HTTPException(
                status_code=400,
                detail=f"Missing required variable: {var_config['label']}"
            )
    
    # Format variables for Claude prompt
    variables_list = []
    for var_name, var_value in request.variables.items():
        if var_name in template_vars:
            label = template_vars[var_name]["label"]
            variables_list.append(f"- {label}: {var_value}")
    
    variables_str = "\n".join(variables_list)
    
    # Build Claude prompt
    system_prompt = """Bạn là chuyên gia soạn thảo văn bản pháp lý Việt Nam.

YÊU CẦU:
1. Tuân thủ đúng quy định pháp luật Việt Nam hiện hành
2. Sử dụng ngôn ngữ pháp lý chuẩn mực
3. Đầy đủ các điều khoản bắt buộc
4. Format: văn bản hoàn chỉnh, sẵn sàng in
5. Đánh số điều khoản rõ ràng
6. Trả về định dạng markdown với cấu trúc rõ ràng"""

    user_message = f"""Soạn thảo {template["name"]} với các thông tin:

{variables_str}

Hãy tạo văn bản hoàn chỉnh, đúng format pháp lý Việt Nam."""

    # Call Claude
    from ..main import call_claude
    result = await call_claude(system_prompt, user_message, max_tokens=4096)
    
    # Save to generated_documents
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("""
            INSERT INTO generated_documents 
            (company_id, template_id, user_id, name, variables, content, status)
            VALUES (%s, %s, %s, %s, %s, %s, 'generated')
            RETURNING id, name, created_at
        """, (
            current_user["company_id"],
            request.template_id,
            current_user["id"],
            f"{template['name']} - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            json.dumps(request.variables),
            result["content"]
        ))
        
        doc = cur.fetchone()
        
        # Update template usage count
        cur.execute("""
            UPDATE document_templates
            SET usage_count = usage_count + 1
            WHERE template_id = %s
        """, (request.template_id,))
        
        # Update company usage
        cur.execute("""
            UPDATE companies 
            SET used_quota = used_quota + 1 
            WHERE id = %s
        """, (current_user["company_id"],))
        
        # Log usage
        cur.execute("""
            INSERT INTO usage_logs 
            (company_id, user_id, endpoint, agent_type, input_tokens, output_tokens, status_code)
            VALUES (%s, %s, '/v1/templates/generate', 'draft', %s, %s, 200)
        """, (
            current_user["company_id"],
            current_user["id"],
            result["input_tokens"],
            result["output_tokens"]
        ))
        
        conn.commit()
    
    return {
        "document_id": str(doc["id"]),
        "document_name": doc["name"],
        "content": result["content"],
        "template_name": template["name"],
        "tokens_used": result["input_tokens"] + result["output_tokens"],
        "model": result["model"],
        "created_at": doc["created_at"].isoformat()
    }

@router.get("/generated/list")
async def list_generated_documents(
    current_user: dict = Depends(get_current_user)
):
    """List user's generated documents"""
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("""
            SELECT 
                gd.id, gd.name, gd.template_id, gd.status, gd.created_at,
                dt.name as template_name, dt.category
            FROM generated_documents gd
            LEFT JOIN document_templates dt ON dt.template_id = gd.template_id
            WHERE gd.company_id = %s
            ORDER BY gd.created_at DESC
            LIMIT 100
        """, (current_user["company_id"],))
        
        documents = cur.fetchall()
    
    return {
        "documents": [
            {
                "id": str(d["id"]),
                "name": d["name"],
                "template_id": d["template_id"],
                "template_name": d["template_name"],
                "category": d["category"],
                "status": d["status"],
                "created_at": d["created_at"].isoformat()
            }
            for d in documents
        ],
        "count": len(documents)
    }

@router.get("/generated/{doc_id}")
async def get_generated_document(
    doc_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get generated document details"""
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("""
            SELECT 
                gd.id, gd.name, gd.template_id, gd.variables, gd.content,
                gd.status, gd.created_at,
                dt.name as template_name, dt.category
            FROM generated_documents gd
            LEFT JOIN document_templates dt ON dt.template_id = gd.template_id
            WHERE gd.id = %s AND gd.company_id = %s
        """, (doc_id, current_user["company_id"]))
        
        doc = cur.fetchone()
        
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
    
    return {
        "id": str(doc["id"]),
        "name": doc["name"],
        "template_id": doc["template_id"],
        "template_name": doc["template_name"],
        "category": doc["category"],
        "variables": doc["variables"],
        "content": doc["content"],
        "status": doc["status"],
        "created_at": doc["created_at"].isoformat()
    }

@router.get("/generated/{doc_id}/download")
async def download_generated_document(
    doc_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get document content for download"""
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("""
            SELECT id, name, content
            FROM generated_documents
            WHERE id = %s AND company_id = %s
        """, (doc_id, current_user["company_id"]))
        
        doc = cur.fetchone()
        
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
    
    return {
        "document_id": str(doc["id"]),
        "name": doc["name"],
        "content": doc["content"],
        "format": "markdown",
        "note": "Copy content or implement DOCX/PDF generation"
    }

@router.delete("/generated/{doc_id}")
async def delete_generated_document(
    doc_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete a generated document"""
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Check ownership
        cur.execute("""
            SELECT id, name
            FROM generated_documents
            WHERE id = %s AND company_id = %s
        """, (doc_id, current_user["company_id"]))
        
        doc = cur.fetchone()
        
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Delete
        cur.execute("DELETE FROM generated_documents WHERE id = %s", (doc_id,))
        conn.commit()
    
    return {
        "message": f"Document '{doc['name']}' deleted successfully"
    }
