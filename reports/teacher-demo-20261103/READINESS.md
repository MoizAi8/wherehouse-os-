# Current production status

- 78b98ea deployed through OCI run 80 after CI/Docker builds passed.
- Public isolated demo, real Gemini Free-tier chat and trusted direct-IP HTTPS are live.
- All 33 live HTTP checks passed; eight containers run with dependency readiness green.
- Protected first-visit browser login exposed a CSRF-cookie race. Direct sign-in works. A tested correction awaits renewed release authorization.
- Correction: 66 frontend tests, lint/types/build, 19 built auth checks and three real first-visit browser sign-ins passed.
- Controlled 500-case evaluation: 498 passed, two local-Qwen quality failures, none blocked. No paid inference.
- Demo has no automatic expiration and remains controlled by TEACHER_DEMO_MODE.

See [live status](LIVE-RELEASE.md), [prepared correction](CSRF-CORRECTION.md),
and [full pre-release evidence](REPORT.md).
