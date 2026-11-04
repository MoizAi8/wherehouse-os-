"""Generate a small operational ledger from actual acceptance artifacts."""

import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

directory = Path(sys.argv[1])
worker_file = directory / "warehouse-celery-evidence.json"
worker = json.loads(worker_file.read_text()) if worker_file.exists() else {}
scenarios = []
for name, conditions, expected in (
    ("normal", "Queued monitor task with an overdue shipment", "Persist monitor results and recommendations"),
    ("duplicate", "Same task ID published after removing its Redis result", "Return the original PostgreSQL cycle"),
    ("retry", "Shipment table temporarily unavailable", "Enter RETRY and complete after database repair"),
    ("recovery", "Kill the worker process group while a task is blocked", "Redeliver and complete the same task"),
    ("scheduled", "Run Celery Beat with the accelerated acceptance schedule", "Persist a new scheduled cycle"),
    ("exhausted", "Hold the database fault through all retries", "Reach FAILURE with no completion receipt"),
    ("after_exhaustion", "Restore the shipment table and queue a new job", "Complete the new job"),
    ("notification_worker", "Queue a notification intent with provider access disabled in the worker", "Persist one failure without a provider ID"),
    ("redis_restart", "Restart the isolated Redis container", "Existing worker reconnects and completes a new job"),
):
    result = worker.get(name)
    scenarios.append({
        "id": f"worker-{name}", "capability": "worker recovery and delivery",
        "conditions": conditions, "expected": expected, "actual": result,
        "evidence": worker_file.name if result is not None else None,
        "status": "PASS" if result is not None else "BLOCKED",
    })

test_file = directory / "backend-regression.xml"
if test_file.exists():
    for case in ET.parse(test_file).iter("testcase"):
        name = case.attrib["name"]
        if not name.startswith((
            "test_inventory_order_lifecycle[", "test_notification_sdk_contract[",
            "test_configured_route_survives_monitor_and_duplicate_dispatch[",
        )):
            continue
        issue = next((node for node in case if node.tag in {"failure", "error", "skipped"}), None)
        status = "PASS" if issue is None else "SKIPPED" if issue.tag == "skipped" else "FAIL"
        scenarios.append({
            "id": name, "capability": case.attrib["classname"].removeprefix("tests."),
            "conditions": name.partition("[")[2].rstrip("]"),
            "expected": "All asserted business transitions and persisted results match the fixture",
            "actual": "Assertions passed" if issue is None else issue.attrib.get("message"),
            "evidence": test_file.name, "status": status,
        })
directory.mkdir(parents=True, exist_ok=True)
(directory / "operational-scenarios.json").write_text(json.dumps(scenarios, indent=2) + "\n")
