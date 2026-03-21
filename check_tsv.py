import os
import psycopg2
from psycopg2.extras import RealDictCursor

DB_CONFIG = {
    "host": os.getenv("SUPABASE_DB_HOST", "localhost"),
    "port": int(os.getenv("SUPABASE_DB_PORT", "5432")),
    "dbname": os.getenv("DB_NAME", "postgres"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("SUPABASE_DB_PASSWORD", ""),
    "sslmode": os.getenv("DB_SSL_MODE", "require")
}

conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor(cursor_factory=RealDictCursor)

# Check how tsv was created
cur.execute("""
    SELECT pg_get_functiondef(oid) as definition
    FROM pg_proc
    WHERE proname LIKE '%tsv%'
    AND pronamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public')
    LIMIT 3;
""")

print("=== TSV FUNCTIONS ===")
for row in cur.fetchall():
    print(row['definition'])
    print("\n---\n")

# Sample some tsv data
cur.execute("""
    SELECT 
        article,
        content,
        tsv::text as tsv_repr,
        law_id
    FROM law_chunks
    WHERE content LIKE '%hợp đồng lao động%'
    AND article LIKE '%20%'
    LIMIT 2;
""")

print("\n=== SAMPLE TSV DATA (search for Điều 20 about HĐLĐ) ===")
for row in cur.fetchall():
    print(f"Article: {row['article']}")
    print(f"Content preview: {row['content'][:200]}...")
    print(f"TSV: {row['tsv_repr'][:300]}...")
    print("\n---\n")

# Check law documents for "Bộ Luật Lao Động"
cur.execute("""
    SELECT id, title, law_number
    FROM law_documents
    WHERE title ILIKE '%bộ luật lao động%' OR title ILIKE '%luật lao động%'
    LIMIT 5;
""")

print("\n=== LAW DOCUMENTS (Lao Động) ===")
for row in cur.fetchall():
    print(f"{row['title']} - {row['law_number']}")
    
    # Count chunks
    cur.execute("SELECT COUNT(*) as cnt FROM law_chunks WHERE law_id = %s", (row['id'],))
    chunk_count = cur.fetchone()['cnt']
    print(f"  └─ {chunk_count} chunks")
    
    # Sample article 20
    cur.execute("""
        SELECT article, content
        FROM law_chunks
        WHERE law_id = %s AND article LIKE '%20%'
        LIMIT 2
    """, (row['id'],))
    
    for chunk in cur.fetchall():
        print(f"     Article {chunk['article']}: {chunk['content'][:150]}...")

conn.close()
