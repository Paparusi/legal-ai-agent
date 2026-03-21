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

cur.execute("""
    SELECT pg_get_functiondef(oid) as definition
    FROM pg_proc
    WHERE proname = 'search_law'
    AND pronamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public');
""")

result = cur.fetchone()
print(result['definition'])

# Check if tsv column has data
cur.execute("SELECT COUNT(*) as total, COUNT(tsv) as with_tsv FROM law_chunks")
stats = cur.fetchone()
print(f"\n\nTotal chunks: {stats['total']}")
print(f"Chunks with tsv: {stats['with_tsv']}")

# Check indexes
cur.execute("""
    SELECT indexname, indexdef
    FROM pg_indexes
    WHERE tablename = 'law_chunks'
    AND indexname LIKE '%tsv%' OR indexname LIKE '%trgm%';
""")
print("\n\n=== INDEXES ===")
for row in cur.fetchall():
    print(f"{row['indexname']}: {row['indexdef']}")

conn.close()
