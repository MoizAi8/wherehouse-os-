"""Rehearse the additive approval migration with synthetic pre-existing records."""
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]
API=ROOT/"order-fulfillment-coordinator/apps/api"
STATE=ROOT/".tools/migration-rehearsal"/uuid4().hex
STATE.mkdir(parents=True)
database=STATE/"fixture.sqlite3"
env={**os.environ,"DATABASE_URL":"sqlite+aiosqlite:///"+database.as_posix(),
    "DATABASE_SYNC_URL":"sqlite:///"+database.as_posix(),"OPENAI_API_KEY":"","CHAT_API_KEY":"",
    "JWT_SECRET":"isolated-migration-fixture","WEBHOOK_SECRET":"isolated-migration-fixture"}


def upgrade(revision):
    result=subprocess.run([sys.executable,"-m","alembic","upgrade",revision],cwd=API,env=env,
        capture_output=True,text=True,timeout=60)
    if result.returncode:raise RuntimeError("Isolated migration failed: "+result.stderr[-1000:])


def snapshot(connection):
    result={}
    for name,sql in connection.execute("SELECT name,sql FROM sqlite_master WHERE type='table' AND name NOT IN ('alembic_version','sqlite_sequence','chat_approvals') ORDER BY name"):
        rows=connection.execute('SELECT * FROM "'+name.replace('"','""')+'" ORDER BY rowid').fetchall()
        result[name]={"schema":sql,"rows":len(rows),"sha256":hashlib.sha256(repr(rows).encode()).hexdigest()}
    return result


upgrade("c4d7e9f0a1b2")
with sqlite3.connect(database) as connection:
    connection.execute("""INSERT INTO orders(id,customer_email,shipping_address,shipping_zip,shipping_city,
        shipping_state,shipping_country,items_json,total_weight_kg,status)
        VALUES ('migration-preserved-order','migration@example.com','Synthetic fixture','54000','Lahore','QA','PK','[]',1,'pending')""")
    connection.commit();before=snapshot(connection)
upgrade("head")
with sqlite3.connect(database) as connection:
    after=snapshot(connection)
    assert before==after,"Pre-existing schema or records changed"
    assert connection.execute("SELECT version_num FROM alembic_version").fetchone()[0]=="d5e8f1a2b3c4"
    assert connection.execute("SELECT COUNT(*) FROM chat_approvals").fetchone()[0]==0
report={"synthetic_only":True,"previous_revision":"c4d7e9f0a1b2","new_revision":"d5e8f1a2b3c4",
    "existing_tables_preserved":len(before),"existing_data_and_schemas_identical":True,
    "production_database_touched":False,"new_approval_table_empty":True}
(ROOT/"reports/teacher-demo-20261103/migration-rehearsal.json").write_text(json.dumps(report,indent=2),encoding="utf8")
print(json.dumps(report))
