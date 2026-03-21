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

# Find Bộ Luật Lao Động
cur.execute("""
    SELECT id, title, law_number
    FROM law_documents
    WHERE title ILIKE '%bộ luật lao động%'
    ORDER BY created_at DESC
    LIMIT 1;
""")

law = cur.fetchone()
if law:
    print(f"Found: {law['title']} ({law['law_number']})")
    print(f"Law ID: {law['id']}\n")
    
    # Find Điều 20
    cur.execute("""
        SELECT article, title, content
        FROM law_chunks
        WHERE law_id = %s
        AND article = 'Điều 20'
        LIMIT 5;
    """, (law['id'],))
    
    dieu_20 = cur.fetchall()
    
    if dieu_20:
        print(f"=== Found {len(dieu_20)} chunks for Điều 20 ===\n")
        for chunk in dieu_20:
            print(f"Article: {chunk['article']}")
            print(f"Title: {chunk['title']}")
            print(f"Content:\n{chunk['content']}\n")
            print("-" * 80 + "\n")
    else:
        print("Điều 20 not found! Let me check what articles exist...")
        cur.execute("""
            SELECT DISTINCT article
            FROM law_chunks
            WHERE law_id = %s
            AND article LIKE 'Điều%'
            ORDER BY article
            LIMIT 30;
        """, (law['id'],))
        
        articles = cur.fetchall()
        print(f"Available articles: {[a['article'] for a in articles]}")

# Also check what our search returns for the exact query
print("\n" + "=" * 80)
print("TESTING: hợp đồng lao động có thời hạn")
print("=" * 80)

cur.execute("""
    SELECT 
        lc.article,
        ld.title,
        ld.law_number,
        lc.content,
        ts_rank(lc.tsv, to_tsquery('simple', 'hop | dong | lao | dong | thoi | han')) AS rank_simple,
        similarity(lc.content, 'hợp đồng lao động có thời hạn') AS sim_score
    FROM law_chunks lc
    JOIN law_documents ld ON ld.id = lc.law_id
    WHERE lc.content ILIKE '%hợp đồng lao động%'
    AND lc.content ILIKE '%thời hạn%'
    ORDER BY sim_score DESC
    LIMIT 10;
""")

results = cur.fetchall()
print(f"\nFound {len(results)} results:")
for i, r in enumerate(results, 1):
    print(f"\n{i}. {r['title']} - {r['article']}")
    print(f"   Similarity: {r['sim_score']:.4f}, TS Rank: {r['rank_simple']:.6f}")
    print(f"   {r['content'][:200]}...")

conn.close()
