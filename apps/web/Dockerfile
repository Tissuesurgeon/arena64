# Arena64 Web — production Next.js image (standalone)
# Build from this directory (Railway Root Directory = apps/web) OR:
#   docker build -f apps/web/Dockerfile apps/web
#
# Vercel: prefer the Next.js framework preset (no Docker). Use this image
# only if you containerize the frontend (e.g. Railway/Fly). Set DOCKER_BUILD=1
# so next.config enables `output: "standalone"`.

FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

FROM node:22-alpine AS builder
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1 \
    DOCKER_BUILD=1
COPY --from=deps /app/node_modules ./node_modules
COPY . .

# Build-time public env (override with --build-arg / Railway variables)
ARG NEXT_PUBLIC_API_URL
ARG NEXT_PUBLIC_WS_URL
ARG NEXT_PUBLIC_CHAIN_ID=1439
ARG NEXT_PUBLIC_CHAIN_NAME="Injective EVM Testnet"
ARG NEXT_PUBLIC_RPC_URL=https://k8s.testnet.json-rpc.injective.network/
ARG NEXT_PUBLIC_WC_PROJECT_ID
ARG NEXT_PUBLIC_WALLETCONNECT_PROJECT_ID

ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL \
    NEXT_PUBLIC_WS_URL=$NEXT_PUBLIC_WS_URL \
    NEXT_PUBLIC_CHAIN_ID=$NEXT_PUBLIC_CHAIN_ID \
    NEXT_PUBLIC_CHAIN_NAME=$NEXT_PUBLIC_CHAIN_NAME \
    NEXT_PUBLIC_RPC_URL=$NEXT_PUBLIC_RPC_URL \
    NEXT_PUBLIC_WC_PROJECT_ID=$NEXT_PUBLIC_WC_PROJECT_ID \
    NEXT_PUBLIC_WALLETCONNECT_PROJECT_ID=$NEXT_PUBLIC_WALLETCONNECT_PROJECT_ID

RUN npm run build

FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

RUN addgroup -S nodejs && adduser -S nextjs -G nodejs

# public/ may be empty (.gitkeep only) — still required for standalone layout
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs
EXPOSE 3000

CMD ["sh", "-c", "node server.js"]
