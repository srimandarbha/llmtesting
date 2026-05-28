import psycopg2
from agents.config import DATABASE_TARGET

conn = psycopg2.connect(**DATABASE_TARGET)
cur = conn.cursor()
cur.execute("SELECT id, status FROM incidents_v2 WHERE id = '000e7066-24d4-4877-8a98-4923635e94f0'")
print(cur.fetchone())
cur.close()
conn.close()
