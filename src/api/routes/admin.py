"""
Platform Admin Panel - Super Admin Only
Dashboard, company management, user management, usage analytics, logs
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional, List, Dict
from pydantic import BaseModel
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import RealDictCursor
import json
from ..middleware.auth import get_current_user, get_db

router = APIRouter(prefix="/v1/admin", tags=["admin"])

# ============================================
# Auth Helper
# ============================================

async def require_superadmin(current_user: Dict = Depends(get_current_user)):
    """Ensure user is superadmin - FIX 4: Double-verify superadmin role"""
    # Double-check role (defense in depth)
    if current_user.get("role") != "superadmin":
        raise HTTPException(
            status_code=403, 
            detail="Access denied. Superadmin role required."
        )
    
    # Optional: Add IP whitelist check for extra security
    # ALLOWED_ADMIN_IPS = os.getenv("ADMIN_IP_WHITELIST", "").split(",")
    # if ALLOWED_ADMIN_IPS and request.client.host not in ALLOWED_ADMIN_IPS:
    #     raise HTTPException(403, "IP not whitelisted for admin access")
    
    return current_user

# ============================================
# Models
# ============================================

class CompanyUpdate(BaseModel):
    plan: Optional[str] = None
    monthly_quota: Optional[int] = None
    status: Optional[str] = None
    notes: Optional[str] = None

class UserUpdate(BaseModel):
    role: Optional[str] = None
    is_active: Optional[bool] = None

class Announcement(BaseModel):
    title: str
    content: str
    target: str = "all"
    type: str = "info"  # info, warning, urgent

# ============================================
# Dashboard
# ============================================

@router.get("/dashboard")
async def get_dashboard(admin: Dict = Depends(require_superadmin)):
    """Platform overview statistics"""
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Total companies
        cur.execute("SELECT COUNT(*) as count FROM companies")
        total_companies = cur.fetchone()["count"]
        
        # Total users
        cur.execute("SELECT COUNT(*) as count FROM users WHERE is_active = true")
        total_users = cur.fetchone()["count"]
        
        # Requests today
        cur.execute("""
            SELECT COUNT(*) as count 
            FROM usage_logs 
            WHERE created_at >= CURRENT_DATE
        """)
        requests_today = cur.fetchone()["count"]
        
        # Requests this month
        cur.execute("""
            SELECT COUNT(*) as count 
            FROM usage_logs 
            WHERE created_at >= date_trunc('month', CURRENT_DATE)
        """)
        requests_month = cur.fetchone()["count"]
        
        # Plan breakdown
        cur.execute("""
            SELECT plan, COUNT(*) as count
            FROM companies
            GROUP BY plan
            ORDER BY count DESC
        """)
        plans = [dict(r) for r in cur.fetchall()]
        
        # Token usage
        cur.execute("""
            SELECT 
                SUM(input_tokens) as total_input,
                SUM(output_tokens) as total_output
            FROM usage_logs
            WHERE created_at >= date_trunc('month', CURRENT_DATE)
        """)
        tokens = dict(cur.fetchone())
        
        # Recent activity (last 24h)
        cur.execute("""
            SELECT 
                DATE_TRUNC('hour', created_at) as hour,
                COUNT(*) as requests
            FROM usage_logs
            WHERE created_at >= NOW() - INTERVAL '24 hours'
            GROUP BY hour
            ORDER BY hour DESC
        """)
        activity = [dict(r) for r in cur.fetchall()]
        
        # Active sessions (estimate based on recent activity)
        cur.execute("""
            SELECT COUNT(DISTINCT COALESCE(user_id::text, ip_address)) as count
            FROM platform_logs
            WHERE created_at >= NOW() - INTERVAL '30 minutes'
        """)
        active_sessions_row = cur.fetchone()
        active_sessions = active_sessions_row["count"] if active_sessions_row else 0
        
        # Revenue estimate (placeholder calculation)
        revenue_estimate = total_companies * 29  # Simple estimate
        
        return {
            "total_companies": total_companies,
            "total_users": total_users,
            "requests_today": requests_today,
            "requests_month": requests_month,
            "active_sessions": active_sessions,
            "revenue_estimate": revenue_estimate,
            "plans_breakdown": plans,
            "tokens_month": {
                "input": tokens["total_input"] or 0,
                "output": tokens["total_output"] or 0,
                "total": (tokens["total_input"] or 0) + (tokens["total_output"] or 0)
            },
            "activity_24h": activity
        }

# ============================================
# Company Management
# ============================================

@router.get("/companies")
async def list_companies(
    search: Optional[str] = None,
    plan: Optional[str] = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
    admin: Dict = Depends(require_superadmin)
):
    """List all companies with usage stats"""
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        query = """
            SELECT 
                c.id, c.name, c.slug, c.plan, c.monthly_quota, c.used_quota,
                c.created_at, c.metadata,
                COUNT(DISTINCT u.id) as user_count,
                COUNT(DISTINCT ak.id) as api_key_count
            FROM companies c
            LEFT JOIN users u ON u.company_id = c.id AND u.is_active = true
            LEFT JOIN api_keys ak ON ak.company_id = c.id AND ak.is_active = true
            WHERE 1=1
        """
        params = []
        
        if search:
            query += " AND (c.name ILIKE %s OR c.slug ILIKE %s)"
            params.extend([f"%{search}%", f"%{search}%"])
        
        if plan:
            query += " AND c.plan = %s"
            params.append(plan)
        
        query += """
            GROUP BY c.id
            ORDER BY c.created_at DESC
            LIMIT %s OFFSET %s
        """
        params.extend([limit, offset])
        
        cur.execute(query, params)
        companies = [dict(r) for r in cur.fetchall()]
        
        # Get total count
        count_query = "SELECT COUNT(*) as count FROM companies WHERE 1=1"
        count_params = []
        if search:
            count_query += " AND (name ILIKE %s OR slug ILIKE %s)"
            count_params.extend([f"%{search}%", f"%{search}%"])
        if plan:
            count_query += " AND plan = %s"
            count_params.append(plan)
        
        cur.execute(count_query, count_params)
        total = cur.fetchone()["count"]
        
        return {
            "companies": companies,
            "total": total,
            "limit": limit,
            "offset": offset
        }

@router.get("/companies/{company_id}")
async def get_company_detail(company_id: str, admin: Dict = Depends(require_superadmin)):
    """Get detailed company info"""
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Company info
        cur.execute("SELECT * FROM companies WHERE id = %s", (company_id,))
        company = cur.fetchone()
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")
        company = dict(company)
        
        # Members
        cur.execute("""
            SELECT id, email, full_name, role, last_login_at, created_at, is_active
            FROM users
            WHERE company_id = %s
            ORDER BY created_at ASC
        """, (company_id,))
        company["members"] = [dict(r) for r in cur.fetchall()]
        
        # API Keys
        cur.execute("""
            SELECT id, name, key_prefix, permissions, rate_limit, 
                   last_used_at, created_at, is_active
            FROM api_keys
            WHERE company_id = %s
            ORDER BY created_at DESC
        """, (company_id,))
        company["api_keys"] = [dict(r) for r in cur.fetchall()]
        
        # Usage history (last 30 days)
        cur.execute("""
            SELECT 
                DATE(created_at) as date,
                COUNT(*) as requests,
                SUM(input_tokens) as input_tokens,
                SUM(output_tokens) as output_tokens
            FROM usage_logs
            WHERE company_id = %s
              AND created_at >= CURRENT_DATE - INTERVAL '30 days'
            GROUP BY DATE(created_at)
            ORDER BY date DESC
        """, (company_id,))
        company["usage_history"] = [dict(r) for r in cur.fetchall()]
        
        return company

@router.put("/companies/{company_id}")
async def update_company(
    company_id: str, 
    update: CompanyUpdate,
    admin: Dict = Depends(require_superadmin)
):
    """Update company settings - FIX 2: Parameterized queries with column whitelist"""
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # FIX 2: Use parameterized queries with whitelisted columns
        # Only allow updating specific safe columns
        updates = []
        params = []
        
        if update.plan is not None:
            updates.append("plan = %s::plan_type")
            params.append(update.plan)
        
        if update.monthly_quota is not None:
            updates.append("monthly_quota = %s")
            params.append(update.monthly_quota)
        
        if update.notes is not None:
            updates.append("metadata = metadata || %s::jsonb")
            params.append(json.dumps({"admin_notes": update.notes}))
        
        if not updates:
            raise HTTPException(status_code=400, detail="No updates provided")
        
        # Safe: column names are hardcoded, not user input
        query = f"UPDATE companies SET {', '.join(updates)} WHERE id = %s RETURNING *"
        params.append(company_id)
        
        cur.execute(query, params)
        updated = cur.fetchone()
        
        if not updated:
            raise HTTPException(status_code=404, detail="Company not found")
        
        conn.commit()
        return dict(updated)

# ============================================
# User Management
# ============================================

@router.get("/users")
async def list_users(
    search: Optional[str] = None,
    role: Optional[str] = None,
    company_id: Optional[str] = None,
    limit: int = Query(100, le=500),
    offset: int = 0,
    admin: Dict = Depends(require_superadmin)
):
    """List all users"""
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        query = """
            SELECT 
                u.id, u.email, u.full_name, u.role, u.company_id,
                u.last_login_at, u.created_at, u.is_active,
                c.name as company_name, c.plan as company_plan
            FROM users u
            LEFT JOIN companies c ON c.id = u.company_id
            WHERE 1=1
        """
        params = []
        
        if search:
            query += " AND (u.email ILIKE %s OR u.full_name ILIKE %s)"
            params.extend([f"%{search}%", f"%{search}%"])
        
        if role:
            query += " AND u.role = %s"
            params.append(role)
        
        if company_id:
            query += " AND u.company_id = %s"
            params.append(company_id)
        
        query += " ORDER BY u.created_at DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])
        
        cur.execute(query, params)
        users = [dict(r) for r in cur.fetchall()]
        
        return {"users": users}

@router.put("/users/{user_id}")
async def update_user(
    user_id: str,
    update: UserUpdate,
    admin: Dict = Depends(require_superadmin)
):
    """Update user (change role, ban/unban)"""
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        updates = []
        params = []
        
        if update.role is not None:
            updates.append("role = %s::user_role")
            params.append(update.role)
        
        if update.is_active is not None:
            updates.append("is_active = %s")
            params.append(update.is_active)
        
        if not updates:
            raise HTTPException(status_code=400, detail="No updates provided")
        
        query = f"UPDATE users SET {', '.join(updates)} WHERE id = %s RETURNING *"
        params.append(user_id)
        
        cur.execute(query, params)
        updated = cur.fetchone()
        
        if not updated:
            raise HTTPException(status_code=404, detail="User not found")
        
        conn.commit()
        return dict(updated)

# ============================================
# Usage Analytics
# ============================================

@router.get("/usage")
async def get_usage_analytics(
    period: str = Query("7d", pattern="^(24h|7d|30d|90d)$"),
    group_by: str = Query("hour", pattern="^(hour|day|endpoint|company)$"),
    admin: Dict = Depends(require_superadmin)
):
    """Platform-wide usage analytics"""
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Determine time interval
        intervals = {
            "24h": "24 hours",
            "7d": "7 days",
            "30d": "30 days",
            "90d": "90 days"
        }
        interval = intervals[period]
        
        if group_by == "hour":
            cur.execute(f"""
                SELECT 
                    DATE_TRUNC('hour', created_at) as period,
                    COUNT(*) as requests,
                    SUM(input_tokens) as input_tokens,
                    SUM(output_tokens) as output_tokens
                FROM usage_logs
                WHERE created_at >= NOW() - INTERVAL '{interval}'
                GROUP BY period
                ORDER BY period DESC
            """)
        elif group_by == "day":
            cur.execute(f"""
                SELECT 
                    DATE(created_at) as period,
                    COUNT(*) as requests,
                    SUM(input_tokens) as input_tokens,
                    SUM(output_tokens) as output_tokens
                FROM usage_logs
                WHERE created_at >= NOW() - INTERVAL '{interval}'
                GROUP BY period
                ORDER BY period DESC
            """)
        elif group_by == "endpoint":
            cur.execute(f"""
                SELECT 
                    endpoint,
                    COUNT(*) as requests,
                    SUM(input_tokens) as input_tokens,
                    SUM(output_tokens) as output_tokens,
                    AVG(CASE WHEN input_tokens > 0 THEN input_tokens END) as avg_input_tokens
                FROM usage_logs
                WHERE created_at >= NOW() - INTERVAL '{interval}'
                GROUP BY endpoint
                ORDER BY requests DESC
            """)
        else:  # company
            cur.execute(f"""
                SELECT 
                    c.name as company_name,
                    c.id as company_id,
                    c.plan,
                    COUNT(*) as requests,
                    SUM(ul.input_tokens) as input_tokens,
                    SUM(ul.output_tokens) as output_tokens
                FROM usage_logs ul
                LEFT JOIN companies c ON c.id = ul.company_id
                WHERE ul.created_at >= NOW() - INTERVAL '{interval}'
                GROUP BY c.id, c.name, c.plan
                ORDER BY requests DESC
            """)
        
        results = [dict(r) for r in cur.fetchall()]
        return {
            "period": period,
            "group_by": group_by,
            "data": results
        }

# ============================================
# API Logs
# ============================================

@router.get("/logs")
async def get_api_logs(
    limit: int = Query(100, le=1000),
    company_id: Optional[str] = None,
    endpoint: Optional[str] = None,
    status_code: Optional[int] = None,
    admin: Dict = Depends(require_superadmin)
):
    """Recent API logs with filters"""
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        query = """
            SELECT 
                pl.id, pl.created_at, pl.endpoint, pl.method, pl.status_code,
                pl.response_time_ms, pl.input_tokens, pl.output_tokens, pl.ip_address,
                c.name as company_name, c.plan,
                u.email as user_email
            FROM platform_logs pl
            LEFT JOIN companies c ON c.id = pl.company_id
            LEFT JOIN users u ON u.id = pl.user_id
            WHERE 1=1
        """
        params = []
        
        if company_id:
            query += " AND pl.company_id = %s"
            params.append(company_id)
        
        if endpoint:
            query += " AND pl.endpoint ILIKE %s"
            params.append(f"%{endpoint}%")
        
        if status_code:
            query += " AND pl.status_code = %s"
            params.append(status_code)
        
        query += " ORDER BY pl.created_at DESC LIMIT %s"
        params.append(limit)
        
        cur.execute(query, params)
        logs = [dict(r) for r in cur.fetchall()]
        
        return {"logs": logs}

# ============================================
# Announcements
# ============================================

@router.post("/announce")
async def send_announcement(
    announcement: Announcement,
    admin: Dict = Depends(require_superadmin)
):
    """Send announcement to all companies"""
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Check if announcements table has type column, if not use metadata
        cur.execute("""
            INSERT INTO announcements (title, content, author_id, target, metadata)
            VALUES (%s, %s, %s, %s, %s::jsonb)
            RETURNING *
        """, (announcement.title, announcement.content, admin["id"], announcement.target, 
              json.dumps({"type": announcement.type})))
        
        result = dict(cur.fetchone())
        result["type"] = announcement.type
        conn.commit()
        
        # TODO: Send email/notification to targeted companies
        
        return {
            "announcement": result,
            "status": "sent",
            "message": f"Announcement sent to {announcement.target}"
        }

@router.get("/announcements")
async def list_announcements(
    limit: int = 50,
    admin: Dict = Depends(require_superadmin)
):
    """List all announcements"""
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("""
            SELECT a.*, u.full_name as author_name, u.email as author_email
            FROM announcements a
            LEFT JOIN users u ON u.id = a.author_id
            ORDER BY a.created_at DESC
            LIMIT %s
        """, (limit,))
        
        announcements = []
        for row in cur.fetchall():
            ann = dict(row)
            # Extract type from metadata if exists
            if ann.get("metadata") and isinstance(ann["metadata"], dict):
                ann["type"] = ann["metadata"].get("type", "info")
            else:
                ann["type"] = "info"
            announcements.append(ann)
        
        return {"announcements": announcements}

@router.delete("/announcements/{announcement_id}")
async def delete_announcement(
    announcement_id: str,
    admin: Dict = Depends(require_superadmin)
):
    """Delete an announcement"""
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("""
            DELETE FROM announcements WHERE id = %s RETURNING id
        """, (announcement_id,))
        
        deleted = cur.fetchone()
        
        if not deleted:
            raise HTTPException(status_code=404, detail="Announcement not found")
        
        conn.commit()
        return {"status": "deleted", "id": announcement_id}
