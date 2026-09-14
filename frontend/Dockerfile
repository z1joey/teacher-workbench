# Multi-stage build: Vue 3 + Vite frontend
FROM node:22-alpine AS builder

WORKDIR /build

# Copy package files
COPY package*.json ./

# npm 镜像源可注入：国内本地构建传
# --build-arg NPM_REGISTRY=https://registry.npmmirror.com
# CI 不传则留空，npm 走官方源，行为不变
ARG NPM_REGISTRY=""
RUN if [ -n "$NPM_REGISTRY" ]; then \
      npm --registry="$NPM_REGISTRY" ci; \
    else \
      npm ci; \
    fi

# Copy source
COPY . .

# Build production bundle
RUN npm run build

# Runtime stage: lightweight nginx
FROM nginx:alpine

# Copy built app from builder — vite base is /gao/，index.html 引用
# /gao/assets/*，因此 dist 必须伺服在 /gao/ 子路径下
COPY --from=builder /build/dist /usr/share/nginx/html/gao

# SPA routing under /gao/ + /api reverse proxy, HTTP 与 HTTPS server 块。
# 证书路径指向挂载的 /etc/letsencrypt（见 docker-compose.yml frontend volumes）。
COPY nginx/default.conf /etc/nginx/conf.d/default.conf

# 自签兜底证书：本地开发/未挂载 /etc/letsencrypt 的环境 nginx 也能起 443 块；
# 生产 compose 把真实证书挂进来后覆盖同路径文件，不受影响
RUN apk add --no-cache openssl && \
    mkdir -p /etc/letsencrypt/live/joeyzhang.me && \
    openssl req -x509 -nodes -newkey ec -pkeyopt ec_paramgen_curve:prime256v1 \
      -keyout /etc/letsencrypt/live/joeyzhang.me/privkey.pem \
      -out /etc/letsencrypt/live/joeyzhang.me/fullchain.pem \
      -days 3650 -subj "/CN=joeyzhang.me"

EXPOSE 80 443

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://127.0.0.1/ || exit 1
