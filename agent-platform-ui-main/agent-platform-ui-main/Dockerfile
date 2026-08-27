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

# --- THE ENVIRONMENT OVERRIDE FIX START ---
# 1. Force development mode to unlock devDependencies installation
ENV NODE_ENV=development

# 2. Run a completely clean install that explicitly INCLUDES devDependencies
RUN npm install --include=dev --legacy-peer-deps --no-audit --no-fund

# 3. Ensure the Tailwind PostCSS plugin is explicitly present
RUN npm install @tailwindcss/postcss postcss autoprefixer tailwindcss --legacy-peer-deps --no-audit --no-fund

# 4. Now execute the Next.js optimized production build (Next.js automatically applies production optimizations during build)
RUN npm run build
# --- THE ENVIRONMENT OVERRIDE FIX END ---

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