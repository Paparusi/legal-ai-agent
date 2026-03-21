"""
Run this on Windows (where you have IPv4+IPv6):
  python run_migration_windows.py
"""
import psycopg2
import os

DB_HOST = os.getenv("SUPABASE_DB_HOST", "localhost")
DB_PORT = int(os.getenv("SUPABASE_DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "postgres")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("SUPABASE_DB_PASSWORD", "")

# Read migration SQL
script_dir = os.path.dirname(os.path.abspath(__file__))
sql_file = os.path.join(script_dir, "migration_v1.sql")

with open(sql_file, "r") as f:
    sql = f.read()

print("Connecting to Supabase...")
conn = psycopg2.connect(
    host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
    user=DB_USER, password=DB_PASS, sslmode=os.getenv("DB_SSL_MODE", "require")
)
conn.autocommit = True
cur = conn.cursor()
print("Connected! Running migration...")

# Split and execute statements
for statement in sql.split(';'):
    stmt = statement.strip()
    if stmt and not stmt.startswith('--'):
        try:
            cur.execute(stmt + ';')
        except Exception as e:
            if 'already exists' in str(e) or 'duplicate' in str(e).lower():
                conn.rollback()
                conn.autocommit = True
                print(f"  ⏭️ Skipped (exists): {stmt[:50]}...")
            else:
                print(f"  ❌ Error: {e}")
                conn.rollback()
                conn.autocommit = True

print("\n✅ Migration complete!")
cur.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename;")
tables = [r[0] for r in cur.fetchall()]
print(f"Tables created: {', '.join(tables)}")
cur.close()
conn.close()
