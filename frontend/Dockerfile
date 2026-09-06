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

# SPA routing under /gao/ + /api reverse proxy
RUN echo 'server { \
  listen 80; \
  root /usr/share/nginx/html; \
  index index.html; \
  location /api { \
    proxy_pass http://backend:8001; \
    proxy_set_header Host $host; \
    proxy_set_header X-Real-IP $remote_addr; \
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for; \
    proxy_set_header X-Forwarded-Proto $scheme; \
  } \
  location /gao/ { \
    try_files $uri $uri/ /gao/index.html; \
  } \
  location = /gao { return 302 /gao/; } \
  location = / { return 302 /gao/; } \
}' > /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://127.0.0.1/ || exit 1
