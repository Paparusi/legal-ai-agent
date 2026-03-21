import os
import psycopg2
from psycopg2.extras import RealDictCursor
import time
import json

DB_CONFIG = {
    "host": os.getenv("SUPABASE_DB_HOST", "localhost"),
    "port": int(os.getenv("SUPABASE_DB_PORT", "5432")),
    "dbname": os.getenv("DB_NAME", "postgres"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("SUPABASE_DB_PASSWORD", ""),
    "sslmode": os.getenv("DB_SSL_MODE", "require")
}

test_queries = [
    {
        "query": "hợp đồng lao động có thời hạn tối đa bao lâu",
        "expected": "Bộ Luật Lao Động Điều 20"
    },
    {
        "query": "thuế thu nhập doanh nghiệp",
        "expected": "Luật Thuế TNDN"
    },
    {
        "query": "sa thải trái pháp luật",
        "expected": "Bộ Luật Lao Động (Điều 41, 42)"
    },
    {
        "query": "thành lập công ty cổ phần",
        "expected": "Luật Doanh Nghiệp"
    },
    {
        "query": "quyền của người lao động",
        "expected": "Bộ Luật Lao Động Điều 5"
    }
]

conn = psycopg2.connect(**DB_CONFIG)

print("=" * 80)
print("SEARCH PERFORMANCE TEST")
print("=" * 80)

total_time = 0
results_summary = []

for i, test in enumerate(test_queries, 1):
    query = test["query"]
    expected = test["expected"]
    
    print(f"\n[Test {i}/5] Query: \"{query}\"")
    print(f"Expected: {expected}")
    print("-" * 80)
    
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Measure search time
    start = time.time()
    cur.execute("SELECT * FROM search_law(%s, NULL, 5)", (query,))
    results = cur.fetchall()
    elapsed = time.time() - start
    total_time += elapsed
    
    print(f"⏱️  Time: {elapsed*1000:.1f}ms")
    print(f"📊 Results: {len(results)} chunks found")
    
    # Display top 3 results
    for j, r in enumerate(results[:3], 1):
        article_info = f" - {r['article']}" if r.get('article') else ""
        law_title = r.get('law_title') or '(no title)'
        law_number = r.get('law_number') or '(no number)'
        rank_val = r.get('rank', 0)
        content = r.get('content', '')[:150]
        print(f"\n  {j}. {law_title}{article_info} (rank: {rank_val:.2f})")
        print(f"     {law_number}")
        print(f"     {content}...")
    
    # Check if expected result is in top 5
    found_expected = any(
        expected.lower() in r['law_title'].lower() or 
        (r['article'] and expected.lower().find(r['article'].lower()) >= 0)
        for r in results
    )
    
    results_summary.append({
        "query": query,
        "time_ms": round(elapsed * 1000, 1),
        "results_count": len(results),
        "found_expected": found_expected,
        "top_law": results[0]['law_title'] if results else None,
        "top_article": results[0].get('article') if results else None,
        "top_rank": round(float(results[0]['rank']), 2) if results else 0
    })
    
    if found_expected:
        print(f"\n  ✅ Expected result found!")
    else:
        print(f"\n  ⚠️  Expected result NOT in top 5")

avg_time = (total_time / len(test_queries)) * 1000

print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
print(f"Average search time: {avg_time:.1f}ms")
print(f"Target: <1000ms ({'✅ PASS' if avg_time < 1000 else '❌ FAIL'})")
print(f"Tests passed: {sum(1 for r in results_summary if r['found_expected'])}/{len(test_queries)}")

print("\n" + json.dumps(results_summary, ensure_ascii=False, indent=2))

conn.close()
