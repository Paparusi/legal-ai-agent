import os
"""Generate embeddings for law_chunks using local GPU model"""
import psycopg2
import numpy as np
from sentence_transformers import SentenceTransformer
import time

DB_CONFIG = {
    "host": os.getenv("SUPABASE_DB_HOST", "localhost"),
    "port": int(os.getenv("SUPABASE_DB_PORT", "5432")),
    "dbname": os.getenv("DB_NAME", "postgres"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("SUPABASE_DB_PASSWORD", ""),
    "sslmode": os.getenv("DB_SSL_MODE", "require")
}

# Use multilingual model that supports Vietnamese well
# paraphrase-multilingual-MiniLM-L12-v2: 384 dims, fast, good for Vietnamese
# But our DB uses 1536 dims... let's check

print("Loading model...")
# intfloat/multilingual-e5-large: 1024 dims
# BAAI/bge-m3: 1024 dims  
# We need 1536 (OpenAI compatible) OR we change the DB column

# Let's use a model and adjust the DB vector dimension
model = SentenceTransformer('BAAI/bge-m3', device='cuda')
test = model.encode(["test"])
print(f"Model dim: {test.shape[1]}")

# Update DB vector column if needed
conn = psycopg2.connect(**DB_CONFIG)
conn.autocommit = True
cur = conn.cursor()

dim = test.shape[1]
if dim != 1536:
    print(f"Updating vector dimension from 1536 to {dim}...")
    # Drop old index, alter column, recreate index
    cur.execute("DROP INDEX IF EXISTS idx_law_chunks_embedding;")
    cur.execute("DROP INDEX IF EXISTS idx_company_chunks_embedding;")
    cur.execute(f"ALTER TABLE law_chunks ALTER COLUMN embedding TYPE vector({dim});")
    cur.execute(f"ALTER TABLE company_chunks ALTER COLUMN embedding TYPE vector({dim});")
    cur.execute(f"CREATE INDEX idx_law_chunks_embedding ON law_chunks USING hnsw (embedding vector_cosine_ops);")
    cur.execute(f"CREATE INDEX idx_company_chunks_embedding ON company_chunks USING hnsw (embedding vector_cosine_ops);")
    print(f"  ✅ Updated to {dim} dimensions")

# Get chunks without embeddings
cur.execute("SELECT COUNT(*) FROM law_chunks WHERE embedding IS NULL")
total = cur.fetchone()[0]
print(f"\n📊 Chunks to embed: {total}")

BATCH_SIZE = 256
offset = 0
embedded = 0
start_time = time.time()

while offset < total:
    cur.execute("""
        SELECT id, content FROM law_chunks 
        WHERE embedding IS NULL 
        ORDER BY id 
        LIMIT %s
    """, (BATCH_SIZE,))
    rows = cur.fetchall()
    if not rows:
        break
    
    ids = [r[0] for r in rows]
    texts = [r[1][:2000] for r in rows]  # Limit text length
    
    # Generate embeddings
    embeddings = model.encode(texts, batch_size=64, show_progress_bar=False, normalize_embeddings=True)
    
    # Update DB
    for chunk_id, emb in zip(ids, embeddings):
        cur.execute(
            "UPDATE law_chunks SET embedding = %s WHERE id = %s",
            (emb.tolist(), str(chunk_id))
        )
    
    embedded += len(rows)
    elapsed = time.time() - start_time
    rate = embedded / elapsed
    remaining = (total - embedded) / rate if rate > 0 else 0
    
    if embedded % 1024 == 0 or embedded == total:
        print(f"  📊 {embedded}/{total} ({embedded*100//total}%) | {rate:.0f} chunks/s | ETA: {remaining:.0f}s")
    
    offset += BATCH_SIZE

cur.execute("SELECT COUNT(*) FROM law_chunks WHERE embedding IS NOT NULL")
final = cur.fetchone()[0]
print(f"\n🏆 DONE! {final} chunks with embeddings")
print(f"⏱️ Total time: {time.time()-start_time:.0f}s")

cur.close()
conn.close()
