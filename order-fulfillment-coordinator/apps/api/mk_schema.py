import os
import sqlite3
import subprocess
import sys

DB = "seed_verify.db"
SCHEMA = os.path.join(os.environ["TEMP"], "schema.sql")

env = {**os.environ, "DATABASE_URL": f"sqlite:///./{DB}"}
r = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "--sql", "head"],
                   capture_output=True, text=True, env=env)
with open(SCHEMA, "w") as f:
    f.write(r.stdout)

with open(SCHEMA) as f:
    sql = f.read()
conn = sqlite3.connect(DB)
lines = [line for line in sql.splitlines()
         if not line.startswith("INFO") and not line.startswith("BEGIN")
         and not line.startswith("COMMIT") and line.strip()]
conn.executescript("\n".join(lines))
conn.commit()
conn.close()
print("schema created")
