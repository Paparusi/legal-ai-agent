"""
Context Builder — Dynamic system prompt injection like OpenClaw.

Injects per-request context into the AI system prompt:
- User identity (name, role, company)
- Company profile (industry, size, plan)
- Document & contract inventory
- Recent activity
- Time context
- User preferences

Makes the AI contextually aware without needing to call tools.
"""
import json
from datetime import date, datetime, timezone, timedelta
from psycopg2.extras import RealDictCursor

_get_db = None


def init_context(get_db_fn):
    global _get_db
    _get_db = get_db_fn


async def build_user_context(company_id: str, user_id: str = None) -> str:
    """
    Build rich context string for system prompt injection.
    Returns Vietnamese context ready to append to system prompt.
    """
    if not _get_db:
        return ""

    sections = []
    now = datetime.now(timezone(timedelta(hours=7)))  # Vietnam timezone

    try:
        with _get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)

            # ─── 1. User & Company Info ───
            user_info = None
            if user_id:
                cur.execute("""
                    SELECT u.email, u.role, u.full_name, u.created_at as user_since,
                           c.name as company_name, c.plan, c.monthly_quota, c.used_quota,
                           c.metadata
                    FROM users u
                    JOIN companies c ON c.id = u.company_id
                    WHERE u.id = %s
                """, (user_id,))
                user_info = cur.fetchone()

            if not user_info:
                # Fallback: get company info only
                cur.execute("SELECT name, plan, metadata FROM companies WHERE id = %s", (company_id,))
                company = cur.fetchone()
                if company:
                    sections.append(f"## Công ty: {company['name']} (gói {company.get('plan', 'free')})")
            else:
                user_name = user_info.get('full_name') or user_info.get('email', '').split('@')[0]
                sections.append(f"## Người dùng: {user_name}")
                sections.append(f"- Vai trò: {_role_label(user_info.get('role', 'user'))}")
                sections.append(f"- Công ty: {user_info['company_name']} (gói {user_info.get('plan', 'free')})")
                
                # Usage stats
                used = user_info.get('used_quota', 0)
                quota = user_info.get('monthly_quota', 100)
                remaining = max(0, quota - used)
                sections.append(f"- Lượt dùng tháng này: {used}/{quota} (còn {remaining})")

                # Company metadata
                metadata = user_info.get('metadata') or {}
                if isinstance(metadata, str):
                    try:
                        metadata = json.loads(metadata)
                    except:
                        metadata = {}
                if metadata.get('industry'):
                    sections.append(f"- Ngành nghề: {metadata['industry']}")
                if metadata.get('notes'):
                    sections.append(f"- Ghi chú: {metadata['notes']}")

            # ─── 2. Document Inventory ───
            cur.execute("""
                SELECT doc_type, COUNT(*) as cnt 
                FROM documents 
                WHERE company_id = %s AND deleted_at IS NULL
                GROUP BY doc_type
            """, (company_id,))
            doc_types = cur.fetchall()
            if doc_types:
                total = sum(d['cnt'] for d in doc_types)
                type_summary = ", ".join(f"{d['doc_type']}: {d['cnt']}" for d in doc_types)
                sections.append(f"\n## Kho tài liệu: {total} files ({type_summary})")

            # Recent documents (last 5)
            cur.execute("""
                SELECT name, doc_type, created_at, status
                FROM documents 
                WHERE company_id = %s AND deleted_at IS NULL
                ORDER BY created_at DESC
                LIMIT 5
            """, (company_id,))
            recent_docs = cur.fetchall()
            if recent_docs:
                sections.append("### Tài liệu gần đây:")
                for d in recent_docs:
                    created = d['created_at'].strftime('%d/%m') if d.get('created_at') else ''
                    sections.append(f"  • {d['name']} ({d.get('doc_type', 'other')}, {created})")

            # ─── 3. Contract Summary ───
            cur.execute("""
                SELECT name, contract_type, start_date, end_date, status, parties, notes
                FROM contracts 
                WHERE company_id = %s AND status != 'deleted'
                ORDER BY created_at DESC
                LIMIT 10
            """, (company_id,))
            contracts = cur.fetchall()
            if contracts:
                active = [c for c in contracts if c.get('status') == 'active']
                expiring_soon = []
                for c in contracts:
                    if c.get('end_date'):
                        end = c['end_date']
                        if isinstance(end, datetime):
                            end = end.date()
                        if isinstance(end, date):
                            days_left = (end - date.today()).days
                            if 0 <= days_left <= 30:
                                expiring_soon.append((c['name'], days_left))

                sections.append(f"\n## Hợp đồng: {len(contracts)} tổng, {len(active)} đang hiệu lực")
                if expiring_soon:
                    sections.append("⚠️ Sắp hết hạn:")
                    for name, days in expiring_soon:
                        sections.append(f"  • {name} — còn {days} ngày!")

                for c in contracts[:3]:
                    parties = _format_parties(c.get('parties'))
                    sections.append(f"  • {c['name']}{parties}")

            # ─── 4. Folders ───
            cur.execute("""
                SELECT name, (SELECT COUNT(*) FROM documents WHERE folder_id = f.id) as doc_count
                FROM folders f
                WHERE company_id = %s
                ORDER BY name
            """, (company_id,))
            folders = cur.fetchall()
            if folders:
                folder_list = ", ".join(f"{f['name']} ({f['doc_count']})" for f in folders)
                sections.append(f"\n## Thư mục: {folder_list}")

            # ─── 5. Recent Chat Topics ───
            cur.execute("""
                SELECT title, last_message_at, message_count
                FROM chat_sessions
                WHERE company_id = %s AND status = 'active'
                ORDER BY last_message_at DESC NULLS LAST
                LIMIT 3
            """, (company_id,))
            sessions = cur.fetchall()
            if sessions:
                topics = []
                for s in sessions:
                    title = s.get('title', '')
                    if title and len(title) > 5:
                        clean = title.replace("Q&A - ", "").strip()
                        if len(clean) > 50:
                            clean = clean[:50] + "..."
                        topics.append(clean)
                if topics:
                    sections.append(f"\n## Chủ đề gần đây: {'; '.join(topics)}")

            # ─── 6. Time Context ───
            sections.append(f"\n## Thời gian: {now.strftime('%H:%M %d/%m/%Y')} (GMT+7)")
            hour = now.hour
            if 6 <= hour < 12:
                sections.append("Buổi sáng — chào buổi sáng nếu là tin nhắn đầu tiên")
            elif 12 <= hour < 14:
                sections.append("Giờ trưa — ngắn gọn, người dùng có thể đang nghỉ trưa")
            elif 14 <= hour < 18:
                sections.append("Buổi chiều — thời gian làm việc chính")
            elif 18 <= hour < 22:
                sections.append("Buổi tối — có thể đang làm thêm giờ")
            else:
                sections.append("Khuya — trả lời ngắn gọn, không hỏi nhiều")

    except Exception as e:
        print(f"Error building user context: {e}")
        import traceback
        traceback.print_exc()
        return ""

    if not sections:
        return ""

    return "\n".join(sections)


def _role_label(role: str) -> str:
    labels = {
        'owner': 'Chủ sở hữu',
        'admin': 'Quản trị viên',
        'editor': 'Biên tập viên',
        'viewer': 'Người xem',
        'user': 'Người dùng'
    }
    return labels.get(role, role)


def _format_parties(parties) -> str:
    if not parties:
        return ""
    try:
        if isinstance(parties, str):
            parties = json.loads(parties)
        if isinstance(parties, list) and parties:
            names = []
            for p in parties[:2]:
                if isinstance(p, dict):
                    names.append(p.get('name', str(p)))
                else:
                    names.append(str(p))
            return f" (các bên: {', '.join(names)})"
    except:
        pass
    return ""
