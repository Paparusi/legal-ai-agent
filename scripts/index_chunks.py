#!/usr/bin/env python3
"""
Index all unindexed chunks in law_chunks table
"""
import psycopg2
import os

DB_CONFIG = {
    "host": os.getenv("SUPABASE_DB_HOST", "localhost"),
    "port": int(os.getenv("SUPABASE_DB_PORT", "5432")),
    "dbname": os.getenv("DB_NAME", "postgres"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("SUPABASE_DB_PASSWORD", ""),
    "sslmode": os.getenv("DB_SSL_MODE", "require")
}

def main():
    print("Connecting to database...")
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    # Check how many chunks need indexing
    cur.execute("SELECT COUNT(*) FROM law_chunks WHERE tsv IS NULL")
    count_before = cur.fetchone()[0]
    print(f"Found {count_before} unindexed chunks")
    
    if count_before == 0:
        print("✅ All chunks are already indexed!")
        conn.close()
        return
    
    # Index them
    print("Indexing chunks...")
    cur.execute("""
        UPDATE law_chunks 
        SET tsv = to_tsvector('simple', coalesce(title, '') || ' ' || content) 
        WHERE tsv IS NULL
    """)
    conn.commit()
    
    # Verify
    cur.execute("SELECT COUNT(*) FROM law_chunks WHERE tsv IS NULL")
    count_after = cur.fetchone()[0]
    
    print(f"✅ Indexed {count_before - count_after} chunks")
    print(f"Remaining unindexed: {count_after}")
    
    conn.close()

if __name__ == "__main__":
    main()
