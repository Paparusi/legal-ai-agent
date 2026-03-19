"""
Document management endpoints
- Upload, list, get, delete documents
- OCR/Text extraction (PDF, DOCX)
- AI document analysis and comparison
"""
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Query, Request
from pydantic import BaseModel
from typing import Optional, List
from psycopg2.extras import RealDictCursor
import os
import uuid
import json
from pathlib import Path
from datetime import datetime
# FIX 15: Use pypdf instead of PyPDF2
import pypdf as PyPDF2
import docx

from ..middleware.auth import get_db, get_current_user, require_role

# FIX 3, FIX 5: Import security utilities
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from security_utils import (
    sanitize_filename, validate_file_path, check_content_length, 
    MAX_FILE_SIZE, ALLOWED_EXTENSIONS
)

router = APIRouter(prefix="/v1/documents", tags=["Documents"])

# Configuration
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "/tmp/legal-ai-agent-uploads"))
UPLOAD_DIR.mkdir(exist_ok=True, parents=True)

# ============================================
# Models
# ============================================

class UpdateDocumentRequest(BaseModel):
    name: Optional[str] = None
    doc_type: Optional[str] = None
    status: Optional[str] = None

# ============================================
# Helper Functions
# ============================================

def save_upload_file(upload_file: UploadFile, company_id: str, unique_name: str = None) -> tuple[str, int]:
    """Save uploaded file and return (file_path, file_size) - FIX 3, FIX 5: Security hardened"""
    # Create company directory
    company_dir = UPLOAD_DIR / company_id
    company_dir.mkdir(exist_ok=True, parents=True)
    
    # FIX 3: Use pre-sanitized unique filename
    if not unique_name:
        unique_name, _ = sanitize_filename(upload_file.filename or "document.pdf")
    
    file_path = company_dir / unique_name
    
    # FIX 3: Validate that file_path is within company_dir (prevent path traversal)
    validated_path = validate_file_path(file_path, company_dir)
    
    # FIX 5: Also check size during read as backup
    file_size = 0
    with open(validated_path, "wb") as f:
        while chunk := upload_file.file.read(8192):
            file_size += len(chunk)
            if file_size > MAX_FILE_SIZE:
                validated_path.unlink()  # Delete partial file
                raise HTTPException(
                    status_code=413,
                    detail=f"File too large. Maximum size: {MAX_FILE_SIZE / 1024 / 1024}MB"
                )
            f.write(chunk)
    
    return str(validated_path.relative_to(UPLOAD_DIR)), file_size

def extract_text_from_pdf(file_path: Path) -> tuple[str, int]:
    """Extract text from PDF and return (text, page_count)"""
    try:
        with open(file_path, 'rb') as f:
            pdf_reader = PyPDF2.PdfReader(f)
            page_count = len(pdf_reader.pages)
            
            text_parts = []
            for page in pdf_reader.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)
            
            extracted_text = "\n\n".join(text_parts)
            return extracted_text, page_count
    except Exception as e:
        print(f"PDF extraction error: {e}")
        return "", 0

def extract_text_from_docx(file_path: Path) -> str:
    """Extract text from DOCX file"""
    try:
        doc = docx.Document(file_path)
        text_parts = []
        for paragraph in doc.paragraphs:
            if paragraph.text.strip():
                text_parts.append(paragraph.text)
        
        return "\n\n".join(text_parts)
    except Exception as e:
        print(f"DOCX extraction error: {e}")
        return ""

# ============================================
# Endpoints
# ============================================

@router.post("")
async def upload_document(
    request: Request,  # FIX 5: Need request to check Content-Length
    file: UploadFile = File(...),
    doc_type: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Upload a document with automatic text extraction - FIX 3, FIX 5: Security hardened"""
    
    # FIX 5: Check Content-Length FIRST before reading file
    check_content_length(request, MAX_FILE_SIZE)
    
    # FIX 3: Sanitize filename to prevent path traversal
    unique_name, file_ext = sanitize_filename(file.filename or "document.pdf")
    
    # Validate file type
    allowed_types = [
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/plain",
        "image/jpeg",
        "image/png",
        "image/jpg"
    ]
    
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"File type not supported. Allowed: PDF, DOC, DOCX, TXT, JPG, PNG"
        )
    
    try:
        # FIX 3: Pass sanitized unique_name to save_upload_file
        file_path, file_size = save_upload_file(file, str(current_user["company_id"]), unique_name)
        full_path = UPLOAD_DIR / file_path
        
        # Extract text based on file type
        extracted_text = None
        page_count = None
        status = 'uploaded'
        
        if file.content_type == "application/pdf":
            extracted_text, page_count = extract_text_from_pdf(full_path)
            status = 'analyzed'
        
        elif file.content_type in ["application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/msword"]:
            extracted_text = extract_text_from_docx(full_path)
            status = 'analyzed'
        
        elif file.content_type == "text/plain":
            with open(full_path, 'r', encoding='utf-8') as f:
                extracted_text = f.read()
            status = 'analyzed'
        
        elif file.content_type in ["image/jpeg", "image/png", "image/jpg"]:
            # Image files need OCR (Tesseract not available in production)
            status = 'pending_ocr'
            extracted_text = "⚠️ OCR requires Tesseract (not available in production yet). Image file saved but text extraction pending."
        
        # Insert into database
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            
            cur.execute("""
                INSERT INTO documents 
                (company_id, uploaded_by, name, file_path, file_size, mime_type, doc_type, status, extracted_text, page_count)
                VALUES (%s, %s, %s, %s, %s, %s, %s::doc_type, %s::doc_status, %s, %s)
                RETURNING id, name, file_path, file_size, mime_type, doc_type, status, page_count, created_at
            """, (
                current_user["company_id"],
                current_user["id"],
                file.filename,
                file_path,
                file_size,
                file.content_type,
                doc_type,
                status,
                extracted_text,
                page_count
            ))
            
            document = dict(cur.fetchone())
            conn.commit()
        
        return {
            "message": "Document uploaded and processed successfully",
            "document": {
                "id": str(document["id"]),
                "name": document["name"],
                "file_size": document["file_size"],
                "mime_type": document["mime_type"],
                "doc_type": document["doc_type"],
                "status": document["status"],
                "page_count": document["page_count"],
                "created_at": document["created_at"].isoformat()
            }
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@router.get("")
async def list_documents(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    doc_type: Optional[str] = None,
    status: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """List documents for the company"""
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Build query
        base_query = """
            SELECT 
                d.id, d.name, d.file_size, d.mime_type, d.doc_type, d.status,
                d.page_count, d.risk_score, d.issues_count, d.created_at, d.analyzed_at,
                u.full_name as uploaded_by_name
            FROM documents d
            LEFT JOIN users u ON u.id = d.uploaded_by
            WHERE d.company_id = %s
        """
        params = [current_user["company_id"]]
        
        if doc_type:
            base_query += " AND d.doc_type = %s::doc_type"
            params.append(doc_type)
        
        if status:
            base_query += " AND d.status = %s::doc_status"
            params.append(status)
        
        base_query += " ORDER BY d.created_at DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])
        
        cur.execute(base_query, params)
        documents = cur.fetchall()
        
        # Get total count
        count_query = "SELECT COUNT(*) FROM documents WHERE company_id = %s"
        count_params = [current_user["company_id"]]
        if doc_type:
            count_query += " AND doc_type = %s::doc_type"
            count_params.append(doc_type)
        if status:
            count_query += " AND status = %s::doc_status"
            count_params.append(status)
        
        cur.execute(count_query, count_params)
        total = cur.fetchone()["count"]
    
    return {
        "documents": [
            {
                "id": str(d["id"]),
                "name": d["name"],
                "file_size": d["file_size"],
                "mime_type": d["mime_type"],
                "doc_type": d["doc_type"],
                "status": d["status"],
                "page_count": d["page_count"],
                "risk_score": d["risk_score"],
                "issues_count": d["issues_count"],
                "uploaded_by": d["uploaded_by_name"],
                "created_at": d["created_at"].isoformat(),
                "analyzed_at": d["analyzed_at"].isoformat() if d["analyzed_at"] else None
            }
            for d in documents
        ],
        "pagination": {
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": (offset + limit) < total
        }
    }

@router.get("/{document_id}")
async def get_document(
    document_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get document details - FIX 6: Verify company ownership"""
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # FIX 6: ALWAYS verify company_id ownership
        cur.execute("""
            SELECT 
                d.id, d.name, d.file_path, d.file_size, d.mime_type, d.doc_type,
                d.status, d.extracted_text, d.page_count, d.analysis, d.risk_score,
                d.issues_count, d.created_at, d.analyzed_at, d.company_id,
                u.full_name as uploaded_by_name, u.email as uploaded_by_email
            FROM documents d
            LEFT JOIN users u ON u.id = d.uploaded_by
            WHERE d.id = %s
        """, (document_id,))
        
        document = cur.fetchone()
        
        # FIX 6: Check ownership BEFORE returning data
        if not document or str(document["company_id"]) != str(current_user["company_id"]):
            raise HTTPException(status_code=404, detail="Document not found")
    
    return {
        "id": str(document["id"]),
        "name": document["name"],
        "file_size": document["file_size"],
        "mime_type": document["mime_type"],
        "doc_type": document["doc_type"],
        "status": document["status"],
        "page_count": document["page_count"],
        "extracted_text": document["extracted_text"][:1000] if document["extracted_text"] else None,  # Preview only
        "analysis": document["analysis"],
        "risk_score": document["risk_score"],
        "issues_count": document["issues_count"],
        "uploaded_by": {
            "name": document["uploaded_by_name"],
            "email": document["uploaded_by_email"]
        },
        "created_at": document["created_at"].isoformat(),
        "analyzed_at": document["analyzed_at"].isoformat() if document["analyzed_at"] else None
    }

@router.put("/{document_id}")
async def update_document(
    document_id: str,
    data: UpdateDocumentRequest,
    current_user: dict = Depends(get_current_user)
):
    """Update document metadata"""
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Verify ownership
        cur.execute(
            "SELECT id FROM documents WHERE id = %s AND company_id = %s",
            (document_id, current_user["company_id"])
        )
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Build update query
        update_fields = []
        params = []
        
        if data.name:
            update_fields.append("name = %s")
            params.append(data.name)
        if data.doc_type:
            update_fields.append("doc_type = %s::doc_type")
            params.append(data.doc_type)
        if data.status:
            update_fields.append("status = %s::doc_status")
            params.append(data.status)
        
        if not update_fields:
            raise HTTPException(status_code=400, detail="No fields to update")
        
        params.append(document_id)
        query = f"UPDATE documents SET {', '.join(update_fields)} WHERE id = %s RETURNING *"
        
        cur.execute(query, params)
        updated_doc = dict(cur.fetchone())
        conn.commit()
    
    return {
        "message": "Document updated successfully",
        "document": {
            "id": str(updated_doc["id"]),
            "name": updated_doc["name"],
            "doc_type": updated_doc["doc_type"],
            "status": updated_doc["status"]
        }
    }

@router.delete("/{document_id}")
async def delete_document(
    document_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete a document"""
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get document info
        cur.execute("""
            SELECT id, name, file_path
            FROM documents
            WHERE id = %s AND company_id = %s
        """, (document_id, current_user["company_id"]))
        
        document = cur.fetchone()
        
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Delete file from disk
        try:
            file_path = UPLOAD_DIR / document["file_path"]
            if file_path.exists():
                file_path.unlink()
        except Exception as e:
            print(f"Warning: Could not delete file {document['file_path']}: {e}")
        
        # Delete from database
        cur.execute("DELETE FROM documents WHERE id = %s", (document_id,))
        conn.commit()
    
    return {
        "message": f"Document '{document['name']}' deleted successfully"
    }

@router.get("/{document_id}/download")
async def download_document(
    document_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get download URL for a document"""
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("""
            SELECT id, name, file_path, mime_type
            FROM documents
            WHERE id = %s AND company_id = %s
        """, (document_id, current_user["company_id"]))
        
        document = cur.fetchone()
        
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        file_path = UPLOAD_DIR / document["file_path"]
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File not found on disk")
    
    # In production, you'd return a signed URL or use FileResponse
    return {
        "document_id": str(document["id"]),
        "name": document["name"],
        "download_url": f"/uploads/{document['file_path']}",  # Configure nginx/static serving
        "mime_type": document["mime_type"],
        "note": "In production, use signed URLs or direct file serving"
    }

@router.post("/{document_id}/analyze")
async def analyze_document(
    document_id: str,
    current_user: dict = Depends(get_current_user)
):
    """AI Document Analysis - analyze document and extract key information"""
    # Get document and its extracted text
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("""
            SELECT id, name, extracted_text, mime_type, status
            FROM documents
            WHERE id = %s AND company_id = %s
        """, (document_id, current_user["company_id"]))
        
        document = cur.fetchone()
        
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        if not document["extracted_text"]:
            raise HTTPException(
                status_code=400, 
                detail="Document has no extracted text. Please upload a text-based document (PDF, DOCX, TXT)."
            )
        
        # Claude prompt for analysis
        system_prompt = "Bạn là chuyên gia phân tích văn bản pháp lý Việt Nam."
        
        user_message = f"""Phân tích văn bản sau và trả về JSON với các trường:
{{
  "doc_type": "loại văn bản (hợp đồng/quyết định/công văn/biên bản/...)",
  "summary": "tóm tắt ngắn gọn (2-3 câu)",
  "parties": ["các bên liên quan"],
  "key_dates": [{{"label": "mô tả", "date": "ngày"}}],
  "key_amounts": [{{"label": "mô tả", "amount": "số tiền"}}],
  "key_terms": ["các điều khoản quan trọng"],
  "risks": [{{"level": "high/medium/low", "description": "mô tả rủi ro"}}],
  "risk_score": 0-100,
  "recommendations": ["khuyến nghị"]
}}

CHỈ trả về JSON, không giải thích thêm.

VĂN BẢN:
{document['extracted_text'][:30000]}"""
        
        # Call Claude for analysis
        try:
            from ..main import call_claude
            result = await call_claude(system_prompt, user_message, max_tokens=4096)
            
            # Parse JSON response
            try:
                analysis = json.loads(result["content"])
            except:
                # If Claude didn't return pure JSON, try to extract it
                content = result["content"]
                if "```json" in content:
                    json_str = content.split("```json")[1].split("```")[0].strip()
                    analysis = json.loads(json_str)
                elif "{" in content and "}" in content:
                    # Extract JSON from response
                    start = content.find("{")
                    end = content.rfind("}") + 1
                    analysis = json.loads(content[start:end])
                else:
                    analysis = {"error": "Could not parse analysis", "raw": content}
            
            # Update document with analysis
            cur.execute("""
                UPDATE documents
                SET analysis = %s,
                    risk_score = %s,
                    issues_count = %s,
                    analyzed_at = now(),
                    status = 'analyzed'::doc_status
                WHERE id = %s
            """, (
                json.dumps(analysis),
                analysis.get("risk_score", 0),
                len(analysis.get("risks", [])),
                document_id
            ))
            conn.commit()
            
            return {
                "message": "Document analyzed successfully",
                "analysis": analysis,
                "tokens_used": result["input_tokens"] + result["output_tokens"],
                "model": result["model"]
            }
        
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

@router.post("/compare")
async def compare_documents(
    doc1_id: str = Query(..., description="First document ID"),
    doc2_id: str = Query(..., description="Second document ID"),
    current_user: dict = Depends(get_current_user)
):
    """Compare two documents and identify similarities, differences, and risk changes"""
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get both documents
        cur.execute("""
            SELECT id, name, extracted_text
            FROM documents
            WHERE id IN (%s, %s) AND company_id = %s
        """, (doc1_id, doc2_id, current_user["company_id"]))
        
        docs = cur.fetchall()
        
        if len(docs) != 2:
            raise HTTPException(status_code=404, detail="One or both documents not found")
        
        doc1 = docs[0] if str(docs[0]["id"]) == doc1_id else docs[1]
        doc2 = docs[1] if str(docs[1]["id"]) == doc2_id else docs[0]
        
        if not doc1["extracted_text"] or not doc2["extracted_text"]:
            raise HTTPException(status_code=400, detail="Both documents must have extracted text")
        
        # Claude prompt for comparison
        system_prompt = "Bạn là chuyên gia so sánh văn bản pháp lý Việt Nam."
        
        user_message = f"""So sánh hai văn bản sau và trả về JSON với các trường:
{{
  "similarities": ["các điểm giống nhau"],
  "differences": [{{"aspect": "khía cạnh", "doc1": "nội dung văn bản 1", "doc2": "nội dung văn bản 2", "significance": "high/medium/low"}}],
  "risk_changes": [{{"change": "thay đổi", "risk_impact": "tăng/giảm/không đổi", "description": "mô tả"}}],
  "recommendation": "Nên chọn văn bản nào và tại sao",
  "summary": "Tóm tắt so sánh"
}}

CHỈ trả về JSON, không giải thích thêm.

VĂN BẢN 1 ({doc1['name']}):
{doc1['extracted_text'][:15000]}

VĂN BẢN 2 ({doc2['name']}):
{doc2['extracted_text'][:15000]}"""
        
        try:
            from ..main import call_claude
            result = await call_claude(system_prompt, user_message, max_tokens=4096)
            
            # Parse JSON response
            try:
                comparison = json.loads(result["content"])
            except:
                content = result["content"]
                if "```json" in content:
                    json_str = content.split("```json")[1].split("```")[0].strip()
                    comparison = json.loads(json_str)
                elif "{" in content and "}" in content:
                    start = content.find("{")
                    end = content.rfind("}") + 1
                    comparison = json.loads(content[start:end])
                else:
                    comparison = {"error": "Could not parse comparison", "raw": content}
            
            return {
                "message": "Documents compared successfully",
                "documents": {
                    "doc1": {"id": str(doc1["id"]), "name": doc1["name"]},
                    "doc2": {"id": str(doc2["id"]), "name": doc2["name"]}
                },
                "comparison": comparison,
                "tokens_used": result["input_tokens"] + result["output_tokens"],
                "model": result["model"]
            }
        
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Comparison failed: {str(e)}")
