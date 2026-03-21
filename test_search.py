import psycopg2
import os
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

# List all functions
cur.execute("""
    SELECT proname, pg_get_functiondef(oid) as definition
    FROM pg_proc
    WHERE pronamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public')
    AND proname LIKE '%search%'
    ORDER BY proname;
""")

print("=== EXISTING SEARCH FUNCTIONS ===")
for row in cur.fetchall():
    print(f"\n{row['proname']}:")
    print(row['definition'][:500] + "..." if len(row['definition']) > 500 else row['definition'])

# Check table structure
cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name = 'law_chunks'
    ORDER BY ordinal_position;
""")

print("\n\n=== LAW_CHUNKS COLUMNS ===")
for row in cur.fetchall():
    print(f"{row['column_name']}: {row['data_type']}")

# Count chunks
cur.execute("SELECT COUNT(*) as count FROM law_chunks")
print(f"\n=== TOTAL CHUNKS: {cur.fetchone()['count']} ===")

conn.close()
