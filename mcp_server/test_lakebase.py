import os
from pathlib import Path
from dotenv import load_dotenv
import psycopg2

load_dotenv(Path(__file__).parent / ".env")

conn = psycopg2.connect(
    host=os.environ["LAKEBASE_HOST"],
    port=os.environ["LAKEBASE_PORT"],
    dbname=os.environ["LAKEBASE_DB"],
    user=os.environ["LAKEBASE_USER"],
    password=os.environ["LAKEBASE_PASSWORD"],
    sslmode="require",
)

cur = conn.cursor()
cur.execute("SELECT * FROM job_applications;")
for row in cur.fetchall():
    print(row)
conn.close()
