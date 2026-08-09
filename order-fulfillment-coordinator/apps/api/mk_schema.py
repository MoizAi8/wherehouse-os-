import os, sqlite3, subprocess, sys

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
lines = [l for l in sql.splitlines()
         if not l.startswith("INFO") and not l.startswith("BEGIN")
         and not l.startswith("COMMIT") and l.strip()]
conn.executescript("\n".join(lines))
conn.commit()
conn.close()
print("schema created")
