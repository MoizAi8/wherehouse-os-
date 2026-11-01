# ── Base Stage ──────────────────────────────────────────
ARG NODE_VERSION=24.22.2
FROM node:${NODE_VERSION}-alpine AS base
ENV NODE_ENV=production

FROM base AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci --omit=dev --strict-peer-deps --no-audit --no-fund

FROM base AS builder
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci --include=dev --strict-peer-deps --no-audit --no-fund
COPY . .
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
ARG BACKEND_URL
ENV BACKEND_URL=${BACKEND_URL}

# Flush out the stale Turbopack ghost cache from previous failed builds
RUN rm -rf .next

# Execute the Next.js optimized production build
RUN npm run build

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