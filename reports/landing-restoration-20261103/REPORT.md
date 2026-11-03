# Original landing restored — pending approval

The original warehouse landing source was never removed or redesigned, but the public root redirect in the teacher-demo changes hid it. This correction restores src/app/page.tsx exactly to pre-demo commit 00ecaa9. LazyWarehouseHero, WarehouseHero and LandingSections also match that reference with no differences.

The intended public entry is `/`: the original Three.js warehouse racks, Enterprise Multi-Agent OS badge, Intelligence orchestrating your warehouse heading, original descriptive copy, animation and information sections. The button in the actual Git version is labelled **Launch Dashboard**, not Start Your Demo. Its original wording, styling and /dashboard action are preserved.

A fresh private Edge context opened the restored landing, rendered the actual warehouse scene, clicked Launch Dashboard and reached the original full dashboard with no email/password prompt. All original sidebar pages were browsed. The separate Teacher Demonstration frontend remains removed: /demo redirects to /dashboard, while / remains the original landing. No replacement landing was created.

Guest sessions, isolated sample data, Gemini, owner login, private authorization and all existing dashboard components from candidate 47cfd6d remain intact. This correction changes only the root page and its outdated redirect regression; all other application changes in the new checkpoint are the previously tested guest correction. No production or repository settings were changed.

Validation: 29 browser checks, 74 frontend tests, 26 built authentication checks including three fresh-browser owner sign-ins, ESLint and production build/types passed. Backend code is unchanged from the 1,221-test passing candidate. The prior real Gemini browser test and actual production HTTPS/private-API security tests remain recorded in reports/original-ui-guest-20261103 and .tools/final-visual-47cfd6d. The original dashboard pages and style sources remain unchanged. The previously documented narrow-screen clipping remains unchanged.

Screenshots: original-landing.png shows the actual original warehouse scene; original-landing-full.png includes the information sections; dashboard-desktop.png shows the full original dashboard with isolated guest records. These are local candidate screenshots, not a claim that production has been updated.

The new checkpoint supersedes 47cfd6d for release. Explicit approval is required to push the complete corrected candidate to main, set DEMO_GUEST_ENABLED=true and TEACHER_DEMO_MODE=false, and deploy exactly once after CI and Docker builds pass. Existing Gemini secrets, TLS, database/volumes and infrastructure stay intact. Current production remains b726603/run 82 until that approved release.
