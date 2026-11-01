# Warehouse OS frontend

Use Node **24.22.2 LTS** (`.nvmrc`) and npm 11. CI and the Dockerfile use the
same Node release. The backend Python version is unchanged.

```powershell
npm ci --include=dev --strict-peer-deps --no-audit --no-fund
npm run lint
npx --no-install tsc --noEmit
npm test
npm run build
npm run test:auth
```

`test:auth` starts the built app and an isolated backend fixture; it does not
test production accounts or databases. Set `BACKEND_URL` for real deployments;
never put provider credentials in `NEXT_PUBLIC_*` variables.

See the [production completion report](../../order-fulfillment-coordinator/docs/production-completion-report.md)
for deployment gates, test evidence, and remaining infrastructure checks.
