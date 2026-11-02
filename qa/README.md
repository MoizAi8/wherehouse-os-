# Warehouse OS isolated evaluation

All scenario runners refuse remote targets. The fixtures bind only to loopback,
create a new disposable SQLite database under ignored `.tools/teacher-qa/`, and
seed synthetic accounts. They never load production credentials or queues.
The fixture password in these scripts is intentionally public test data and is
not valid in production.

The local runner needs the existing API virtualenv and a running local Ollama.
`local-ollama.Modelfile` reuses installed `qwen2.5:latest` weights and forces CPU
execution; it does not download weights or enable a paid service.

```powershell
ollama create warehouse-os-qa-qwen -f qa/local-ollama.Modelfile
& order-fulfillment-coordinator/apps/api/.venv/Scripts/python.exe qa/server.py
# Separate terminals, separate disposable fixtures:
& order-fulfillment-coordinator/apps/api/.venv/Scripts/python.exe qa/server.py --port 8809 --no-demo --no-llm
& order-fulfillment-coordinator/apps/api/.venv/Scripts/python.exe qa/server.py --port 8810 --no-llm --disable-global-rate-limit
& order-fulfillment-coordinator/apps/api/.venv/Scripts/python.exe qa/run500.py --sections natural,memory,warehouse,security,reliability,tools
```

Run warehouse checks before tools: tools intentionally create five disposable
orders after explicit confirmations. Targeted rechecks accept `--only T022`.
Use a fresh fixture for a repeat of baseline order-count assertions. Each JSONL
file retains all attempts; `--summary` selects the latest attempt per scenario.
Fallback answers are never counted as successful model inference. General
conversation rubrics check specified facts/language, not unrestricted accuracy.

The 500-case manifest is 150 natural, 70 memory, 100 warehouse, 50 tools,
50 security, 50 reliability and 30 browser scenarios. Automated regression tests
are additional checks and are not included in that total.

Browser evaluation uses Playwright 1.64.1 and installed Microsoft Edge. Install
Playwright in a separate tooling directory with strict peer resolution; do not
change application dependencies:

```powershell
npm install --prefix .tools/qa-browser --ignore-scripts --strict-peer-deps playwright@1.64.1
# Build frontend with BACKEND_URL pointing at the chosen disposable fixture.
# Start its production server on 127.0.0.1:3318 with a disposable NEXTAUTH_SECRET
# and NEXTAUTH_URL=http://127.0.0.1:3318, then:
node qa/browser.mjs
```

`verify_gemini.py` is a separate bounded integration check: six real conversational
requests, one real read-tool request, and three unauthenticated rejection checks.
It uses only synthetic data. It requires `GEMINI_API_KEY` in the process
environment and `GEMINI_FREE_TIER_CONFIRMED=true`; the owner must confirm no
billing account is linked. Never put the key in command arguments or source.
The GitHub `verify_gemini=true, deploy=false` workflow consumes the repository
secret directly and skips image publishing and production deployment.

Gemini uses the official OpenAI-compatible endpoint and the reviewed
`gemini-3.5-flash-lite` model. Quota exhaustion is a failure/unavailable result,
never a reason to enable billing or switch to a paid provider. No live Gemini
result may be claimed until the credential-bearing workflow actually passes.
