# AGENTS.md

> **Reference + template.** This file is a working rules file for the reference build
> (`support_worker`, a Tier-1 support Digital FTE) *and* a starter template for students.
> Anything in `<ANGLE BRACKETS>` is a fill-in. Anything marked `[STUDENT]` is teaching
> scaffolding you delete once the project is real.
>
> Built to the shape prescribed by *The AI Agent Factory*: **Brief → Project rules →
> Architecture → then scaffold code.** Do not write code before the Architecture section
> is filled in.

---

## What this is

A single-agent Tier-1 customer support worker that answers account questions from a
knowledge base, drafts replies, and escalates what it cannot resolve. Deployed as a
long-running FastAPI harness on Azure Container Apps, wrapped in Inngest for durable
execution, with agent-generated code confined to a throwaway sandbox.

**The one architectural invariant, never negotiable:**

> The harness is the control plane you own and keep running.
> The sandbox is the execution plane you create, use once, and throw away.

Deviating from the recipe is fine. Deviating from the architecture is not.

---

## Where things live

```
src/support_worker/
  agents.py         Agent definitions only. No tool bodies, no HTTP.
  tools.py          @function_tool definitions. Bodies run in the harness.
  guardrails.py     input / output / tool guardrails + classifier agents
  models.py         Pydantic schemas (all structured output + tool args)
  sessions.py       SQLAlchemySession wiring to Neon
  functions.py      Inngest functions — the operational envelope
  sandboxed.py      SandboxRunConfig / Manifest construction
  main.py           FastAPI app: GET /health, POST /runs, GET /docs
  cli.py            local driver
sandbox-bridge/     Cloudflare Worker. ONLY if using Cloudflare Sandbox, not E2B.
migrations/
  schema.sql        versioned, committed, applied to the DIRECT Neon endpoint
infra/
  deploy.sh         az acr build + az containerapp update
  containerapp.yaml ACA revision config
evals/
  golden.jsonl      committed golden dataset — the CI gate reads this
tests/              mirrors src/ exactly
.claude/skills/     SKILL.md folders (works in Claude Code AND OpenCode)
docs/               on-demand references, see bottom of this file
```

`src/` layout is non-negotiable: scaffold with `uv init --package`, never bare `uv init`.
A flat layout silently breaks every `src/...` reference in this file.

---

## Commands

```bash
make install        # uv sync --frozen
make run            # uv run uvicorn support_worker.main:app --reload
make test           # uv run pytest
make check          # uv run ruff check . && uv run pyright
make evals          # uv run deepeval test run evals/
make dev-envelope   # npx inngest-cli@latest dev   → dashboard http://127.0.0.1:8288
make migrate        # psql "$DIRECT_BRANCH_URL" -f migrations/schema.sql
make deploy         # infra/deploy.sh
```

---

## Brief

<PASTE THE PROJECT BRIEF HERE, VERBATIM. NO CODE. NO ARCHITECTURE.>

Reference brief: *Maya's support inbox receives ~400 tickets/day. Tier-1 tickets are
account lookups, billing questions, and password/access issues answerable from the help
centre. Anything involving a refund over $50, a legal threat, or an angry escalation must
reach a human. Median first response is currently 6 hours; target is under 5 minutes.*

---

## Project rules

### Stack

| Layer | Choice | Non-negotiable because |
|---|---|---|
| Language | Python 3.12 | SDK is Python-only; TypeScript support is planned but undated |
| Toolchain | `uv`, `pytest`, `pyright`, `ruff` | Pyright + Ruff are the first line of verification on generated code |
| Engine | `openai-agents>=0.17,<0.18` | pin a floor and a ceiling; probe the installed version before coding |
| Envelope | **Inngest** | durable execution, triggers, flow control — "the nervous system we ship" |
| Harness | FastAPI + `uvicorn --proxy-headers` | async-native, matches the SDK's asyncio; Pydantic native |
| Host | **Azure Container Apps** | honest scale-to-zero, first-class revisions + traffic splitting |
| State | **Neon Postgres** via `asyncpg` | serverless, branching, pgvector pre-installed |
| Vectors | **pgvector + HNSW**, `text-embedding-3-small`, `vector(1536)` | for most apps, Postgres *is* the vector database |
| Files | **Cloudflare R2** via `boto3`, `region_name="auto"` | S3-compatible, free egress |
| Sandbox | **E2B** (free path) *or* Cloudflare Sandbox + bridge Worker (paid Workers) | pick one and ship rather than surveying all of them |
| Tools | **FastMCP**, `transport="http", stateless_http=True` | streamable HTTP is the recommendation for all new remote work |
| Observability | OTel + Azure App Insights + SDK traces + **Phoenix**, tied by shared `run_id` | four surfaces, none redundant |
| Evals | **DeepEval** (CI gate) → OpenAI Agent Evals + **Ragas** (nightly) → Phoenix (inline) | adopt DeepEval first, add the rest as complexity grows |
| Identity | Better Auth as issuer; this service is a **resource server only** | you validate tokens, you never issue them |

Model strings are placeholders that will change. What is stable is the swap mechanism:
base-URL swap for OpenAI-compatible providers, `LitellmModel` for everything else.

### Layout

- Every parameter and return is annotated. Pydantic `BaseModel` for all structured data.
- `Literal[...]` for constrained tool args — becomes a JSON-schema enum the SDK validates
  against. A real guardrail at zero runtime cost.
- Money is `Decimal`. Never `float`.
- Tests mirror source structure. `load_dotenv()` runs before any project import that
  reads env vars.

### Critical rules

Each rule carries what it prevents. A rule without a "prevents" is a preference, not a rule.

1. **Never run agent-generated code in the harness.** `exec(model_output)` is worse than
   SQL injection — the attack surface is the whole model's reasoning.
   *Prevents:* remote code execution with the harness's live credentials.
2. **Only presigned URLs and short-lived tokens cross into the sandbox Manifest.**
   Database strings and API keys stay in the harness.
   *Prevents:* root credential exfiltration through anything in the Manifest.
3. **Schema-qualify every SQL statement** — `public.runs`, `public.sessions`.
   *Prevents:* silent breakage; Neon's pooled endpoint drops `search_path` settings.
4. **Migrations run against `DIRECT_BRANCH_URL`; the app uses the pooled URL.**
   *Prevents:* schema changes applied through a connection that discards session state.
5. **Every `Runner.run()` gets an explicit `max_turns`** (25 default; some tasks 50; very
   few 100). Hitting the cap is a signal to investigate, not a number to raise.
   *Prevents:* an unbounded ReAct loop burning tokens on solved work.
6. **`run_in_parallel=False` on any guardrail protecting an irreversible action** —
   charges, deletes, outbound email. Text output can stay parallel.
   *Prevents:* the side effect landing before the tripwire's cancel does.
7. **Identity comes from `auth.verified_claims`, never from a tool argument.**
   *Prevents:* the model being talked into impersonating another user.
8. **One `step.run` per agent loop.** Do not decompose per-tool-call unless you have a
   named reason — that requires lifting the loop out of `Runner.run()` and is fragile.
   *Prevents:* brittle envelope code that breaks on every SDK update.
9. **Every Inngest step must be safe to re-run.** Event-level idempotency keys come from a
   stable business key (order id, Stripe event id) — never a timestamp.
   *Prevents:* duplicate refunds and duplicate emails on retry.
10. **Rate limit every public endpoint** — 429 with `Retry-After` at the middleware layer.
    Generous limits are fine; no limit is the dangerous setting.
    *Prevents:* one viral mention becoming a five-figure model bill overnight.
11. **The app must import and boot with only `OPENAI_API_KEY` set** — SQLite when
    `DATABASE_URL` is unset, a local directory when R2 keys are absent.
    *Prevents:* undebuggable startup failures where four backends fail at once.
12. **Wire observability before you need it.** Traces produced before it is wired are gone.
    *Prevents:* debugging the first production incident with no data.
13. **Commit `uv.lock`.** *Prevents:* container builds that are not reproducible.
14. **Never let the agent turn a red test green by editing the test.** You write the
    failing test; it is the spec. Stop the agent if it edits the spec.
    *Prevents:* the TDG loop inverting into theatre.
15. **Verify fast-moving SDK symbols against live docs or Context7 before coding.**
    *When the brief and the live docs disagree, the live docs win.*
    *Prevents:* a day lost to an API shape that changed two releases ago.
16. **Fail closed.** With the database down, the tool refuses. It does not improvise.
    *Prevents:* confident answers built on nothing.

---

## Architecture

### Pattern selection — answer these before writing a line

| Q | Question | Answer | Consequence |
|---|---|---|---|
| Q1 | Can the solution path be defined in advance? | **No** | agentic reasoning needed → Q3 |
| Q2 | Is the workflow fixed and stable across runs? | n/a | — |
| Q3 | Is the task structure articulable before execution? | **No** — a billing question and an access question diverge after turn one | **Single agent + ReAct + tools** |
| Q4 | Quality > speed AND criteria checkable? | **No** — "a good support reply" is not writable as 5–10 checkable bullets | no reflection layer |
| Q5 | Specialization, context, or scale bottleneck? | **Not yet** — trigger recorded below | stay single-agent |

> The discipline is not "always pick the simplest pattern." It is: pick the simplest
> pattern that matches what the task actually requires, and add complexity only when you
> can name the specific task property that demands it.

### Agents

| Agent | Model | Tools | Handoffs | Budget |
|---|---|---|---|---|
| `support_agent` | mid-tier reasoning model | `lookup_account`, `search_knowledge` (MCP), `draft_reply`, `issue_refund`, `escalate_to_human` | none | `max_turns=25` |
| `safety_classifier` | cheap fast model, `output_type=SafetyVerdict` | none | none | 1 call |

One classifier reused across checks. Do **not** create a guardrail agent per check.

### Guardrails

| Where | Mechanism | Mode | Behaviour |
|---|---|---|---|
| Input | `@input_guardrail` → abuse / off-topic / PII | `run_in_parallel=True` | raises `InputGuardrailTripwireTriggered` |
| Tool input on `issue_refund` | `@function_tool(tool_input_guardrails=[...])` — zero-token policy check | `run_in_parallel=False` | `reject_content()` for correctable args; raise for policy violations |
| Approval | `needs_approval` as a **callable** on `issue_refund` (policy-as-code: amount > $50) | — | `result.interruptions` → `state.approve()` / `state.reject()` |
| Output | none day 1 | — | an output guardrail *is* reflection; Q4 said no |
| MCP surface | `begin_session()` returns rules + persona + signed session token; every other tool is token-gated | — | 401 on unauthenticated call — a doorbell, not a crash |

Four layers, not one: guardrails → tracing → approval → sandbox isolation.
Sandboxing limits *where*. Approval decides *whether*.

MCP rules are phrased as **cooperation, never override** — bossy phrasing gets discounted
by the same anti-prompt-injection defences that protect the model.

### Session strategy

`SQLAlchemySession` on Neon over `postgresql+asyncpg://`, creating `agent_sessions` and
`agent_messages`. `OpenAIResponsesCompactionSession` for threads that outgrow the window.

Two gotchas: the `[sqlalchemy]` extra does not pull `greenlet`; and the Neon pooler closes
idle connections, so any blocking `input()` must go through `asyncio.to_thread` or you get
"connection was closed in the middle of operation".

### Deployment topology

| Surface | Component | Config |
|---|---|---|
| Control plane | FastAPI on ACA | `--ingress external --target-port 8000 --min-replicas 0 --max-replicas 3` |
| Envelope | Inngest functions wrapping `Runner.run()` | one `step.run` per agent loop |
| Durable state | Neon | `sessions, runs, traces, artifacts, audit_log` |
| Artifacts | R2 | prefixes `inputs/ outputs/ knowledge/`; 30-day lifecycle on `outputs/` only |
| Execution plane | E2B sandbox | provisioned per run, destroyed on completion |

`GET /health` is the build ladder. It starts as:

```json
{"status":"ok","model":"<model>","backends":{"postgres":false,"sandbox":false,"r2":false}}
```

Each deployment step flips exactly one flag to `true`. Never two at once.

Secrets are ACA named secrets referenced as `secretref:` — never baked into the image.
Rotation: add the new credential beside the old, redeploy, verify, then revoke the old.

Release: new revision at 0% traffic → check `/health` on it → 10% and watch App Insights →
100%, keeping the old revision one day. **Rollback is a traffic change, not a redeploy.**

Sandbox construction has three shapes people get wrong. `Manifest(entries={...})` is
entries-only — there is no `base_image=`, `mounts=[]`, or `MountSpec`. Capabilities are
additive by hand: `Capabilities.default() + [Memory()]`, because a bare list *replaces* the
default. And the sandbox attaches via `RunConfig(sandbox=...)` — there is no
`Runner.run(..., sandbox=...)` parameter.

---

## The multi-agent upgrade — not built, and not yet earned

> Multi-agent is rarely the wrong endpoint; it's almost always the wrong starting point.

Multi-agent costs 5–20× a sequential workflow and is roughly an order of magnitude harder
to debug. Removing one that has been in production six months is not a refactor, it is a
rewrite. So it ships only when a trigger below actually fires in production data.

### Upgrade triggers (measured, not felt)

| Claim | Trigger |
|---|---|
| Specialization | Tool-routing errors concentrated in one query category — on the order of a third of runs in that category, calibrated to our own baseline — **and** written specialist role specs that overlap under 40% |
| Context overflow | ~10-point accuracy drop across a 15K → 45K token sweep on `evals/golden.jsonl` |
| Scale (latency) | >5 independent sub-tasks per run **and** latency exceeding budget by >2× |
| Scale (throughput) | Volume >10× a single-agent design's rate-limit ceiling with no per-tenant cap that preserves fairness |

Evidence hierarchy, strongest to weakest: production traces → holdout measurements →
written role specs → **"feels like specialists" (insufficient — this is where overshoot lives)**.

Kill test: if multi-agent costs over 3× single-agent and quality improves under 20%, the
architecture is not earning its overhead. Remove it.

### Try these first — fix at the smallest scope that works

| Signal | Cheapest fix | Then | Architectural, last |
|---|---|---|---|
| Loops / revisits solved work | explicit stop conditions + tighter tool contracts | improve tool contracts | add a planning layer |
| Routing errors | LLM → deterministic routing for known cases | structured Pydantic handoff contracts, not free text | merge overlapping specialists; collapse to single agent |
| Complex but not better | remove the topmost layer and measure | remove the next | rebuild only with evidence |

Prompt tightening is cheaper than tool-contract changes; tool contracts are cheaper than
architecture; architecture is cheaper than a rewrite. Don't reach for the architecture knob
first. But distinguish *"I can keep patching this"* from *"I keep patching this and it
keeps failing in new ways."*

### If a trigger fires — the target design

**Topology.** Composition is in-process via SDK primitives. The unit of horizontal scaling
is an **Inngest function, not a container.** Do not give each agent its own service.

| Primitive | Use when | Start here? |
|---|---|---|
| `Agent.as_tool()` | coordinator stays in charge and composes specialist outputs | **yes — the simpler one** |
| `handoff()` | the specialist must take over the user-facing conversation | only if that's literally true |
| parallel `Runner.run()` + `asyncio.gather()` | specialists work in isolation, a synthesizer joins them | for fan-out |

The SDK manages context-passing across handoffs. Do not hand-roll routing logic.

**Schema additions (mandatory, day one of the upgrade):**

- `parent_run_id` and `agent_role` columns — each specialist is its own run; the system is
  a parent run referencing children.
- A `routing_decisions` audit table. Multi-agent failures show up as wrong-routing or
  lost-context-on-handoff; without explicit routing logs, debugging is nearly impossible.
- Per-specialist cost attribution, so a runaway specialist cannot hide inside an aggregate.

**Envelope additions:** coordinator fires N specialist events; each specialist is its own
`@inngest_client.create_function` with its own `TriggerEvent`. Per-key concurrency is the
load-bearing pattern: `concurrency=[Concurrency(limit=5, key="event.data.tenant_id")]`.
Priority expressions for tier fairness. `step.wait_for_event` for HITL gates between
specialists. Replay so that when 3 of 5 specialists fail, the 2 that succeeded stay
memoized. Without this envelope you hand-write 2,000–7,000 lines of routing, retry,
approval-queue, rate-limiting, and replay code.

**Handoff contracts are Pydantic schemas, not free text.** The predictable failure is
specialists producing excellent individual briefs the aggregator cannot synthesise because
the formats disagree.

**Three separate eval scoreboards — never one aggregate:**

| Scoreboard | Measures | Needs |
|---|---|---|
| Specialist quality | each specialist as if standalone | per-role golden sets |
| Routing accuracy | did the task reach the right specialist | **labelled routing examples** in the golden dataset |
| Integration quality | end-to-end after composition | full-system golden set |

95% × 90% × 80% ≈ 68% end-to-end. Conflate the three and you cannot tell which layer to fix.

**Anti-patterns to reject in review:** mirroring the org chart ("three teams, so three
agents"); building multi-agent to demonstrate sophistication; specialists whose
responsibilities overlap; one giant agent with a 4,000-token prompt spanning four domains
(that's the *undershoot* failure — more dangerous, because it seems to work until it doesn't).

---

## [STUDENT] Pattern reference — all five, and what each one bets

Delete this section from a real project's AGENTS.md.

| Pattern | Q-path | SDK shape | Cost | The bet it makes | Envelope mapping |
|---|---|---|---|---|---|
| **Sequential workflow** | Q1 yes, Q2 yes | `Agent(output_type=...)` per LLM step, plain Python between. No tools, no handoffs. | 1× | steps are known and identical every run | one `step.run` per step. **Workflow + Inngest is the simplest production-ready agentic deployment in the curriculum.** |
| **Single agent + ReAct + tools** | Q1 no, Q3 no | one `Agent(tools=[...])`, `Runner.run(max_turns=25)` | 3–10× | the path is unknown and the agent will figure it out | one `step.run` for the whole loop |
| **Planning + ReAct** | Q1 no, Q3 yes | `Agent(output_type=Plan)` with no tools, then one `Runner.run` per stage | 5–15× | the *shape* is known, the *content* isn't | `step.run("plan")` then one per stage — plan persistence becomes free |
| **Reflection** | Q4 yes (layer, not a peer) | `@output_guardrail`, or a separate critic + refiner loop | +2–3× on top | quality > speed **and** wrongness is definable | separate generate / critique / refine steps |
| **Multi-agent specialist** | Q5 yes (layer) | `as_tool()` / `handoff()` / parallel `gather()` | 5–20× | no single agent has the expertise, context, or capacity | every primitive: fan-out, per-key concurrency, priority, HITL, replay |

Notes worth stating out loud in class:

- Not every use of `Agent` is agentic. `Agent` with `output_type=` and no tools is the
  idiomatic way to call an LLM with a typed response — the SDK without the agent loop.
- **Don't reach for ReAct when a workflow works.** This is the most important discipline
  the decision tree teaches. Watch for the reverse over time: workflows start stable and
  gradually become adaptive.
- Reflection needs *independence* to work: a different model for the critic, a genuinely
  different framing, or explicit checking tools. Same model, same prompt = rubber-stamping,
  and it is the hardest failure to detect because the dashboards look healthy.
- Reflection works where wrongness is defined (SQL that won't parse, code that won't
  compile). It works poorly where "good" is subjective — that wants human review instead.
- Multi-agent is a *composition* of the other four, not a replacement for them.
- Model API is 90–98% of total spend at every scale. Infrastructure stays under 5%.
  **Optimise the model, not the infrastructure.**

---

## On-demand references

Load only when the task touches them.

- `@docs/deployment.md` — ACA commands, revisions, secrets, blue/green, on-call runbook
- `@docs/envelope.md` — Inngest triggers, steps, idempotency, flow control, replay
- `@docs/mcp.md` — FastMCP server shape, session-init contract, `JWTVerifier`, 401 flow
- `@docs/rag.md` — pgvector HNSW, `ef_search`, hybrid search, RLS, read-only DB role
- `@docs/evals.md` — DeepEval CI gate, nightly job, Phoenix promotion ritual
- `@docs/identity.md` — Better Auth issuer, RS256 for humans / EdDSA for agents

In Claude Code `@docs/foo.md` auto-loads. In OpenCode, list these in the `instructions`
array in `opencode.json`. Keep this file *stable* — churning rules re-bills the prompt
cache every turn.

---

## Verification before any merge

- [ ] `make check` clean — Ruff and Pyright
- [ ] `make test` green, and no test was edited to make it pass
- [ ] Every `Runner.run()` has an explicit `max_turns`
- [ ] Every guardrail on an irreversible action has `run_in_parallel=False`
- [ ] Nothing in the Manifest but presigned URLs and short-lived tokens
- [ ] All SQL schema-qualified; migrations ran against the direct endpoint
- [ ] DeepEval gate passes against `evals/golden.jsonl`
- [ ] `/health` reflects reality — no flag reads `true` that isn't wired
- [ ] Rate limiting is on
- [ ] If this PR adds an architectural layer: removing it measurably degrades output

---

## What changed since the brief

<Run the drift probe before coding. Confirm every SDK symbol this file depends on against
the version actually installed. Record differences here. The live docs win.>
