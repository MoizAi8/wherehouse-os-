# ── Base Stage ──────────────────────────────────────────
FROM node:20-alpine AS base
ENV NODE_ENV=production

FROM base AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install --no-audit --no-fund --legacy-peer-deps --only=production

FROM base AS builder
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install --no-audit --no-fund --legacy-peer-deps
COPY . .
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
ARG BACKEND_URL
ENV BACKEND_URL=${BACKEND_URL}

# =====================================================================
# ⚡ OMNI-TIER BRUTE FORCE INJECTION START ⚡
# 1. Force install compilation dependencies to completely bypass NODE_ENV=production pruning
# Using silent flags (--no-audit, --no-fund, --loglevel=error) to prevent CI log bloat
RUN npm install @tailwindcss/postcss postcss autoprefixer tailwindcss \
    --no-save \
    --legacy-peer-deps \
    --no-audit \
    --no-fund \
    --loglevel=error

# 2. Annihilate any corrupted Turbopack cache from previous failed runs
RUN rm -rf .next

# 3. Execute the Next.js optimized production build
RUN npm run build
# ⚡ OMNI-TIER BRUTE FORCE INJECTION END ⚡
# =====================================================================

FROM base AS runner
WORKDIR /app
RUN addgroup -g 1001 -S nodejs && \
    adduser -S nextjs -u 1001
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
USER nextjs
EXPOSE 3000
ENV PORT=3000 HOSTNAME=0.0.0.0
CMD ["node", "server.js"]