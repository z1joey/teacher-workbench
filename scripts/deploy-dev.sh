#!/usr/bin/env bash
# =============================================================================
# Teacher Workbench — 开发环境本地部署脚本
# =============================================================================
# 目标为内网开发服务器（懒猫微服容器，无公网出入：GitHub Actions 进不来，
# 服务器也无法自行拉取镜像），因此部署从本机发起：
#   本机构建 linux/amd64 镜像 → docker save 经 SSH 灌入服务器 → scp compose
#   → 远程滚动更新(--wait 健康门禁) → curl 端到端验证
#
# 用法:
#   ./deploy-dev.sh              # 以标签 dev-local 部署
#   ./deploy-dev.sh <tag>        # 自定义标签；重复执行=重新部署
#   ./deploy-dev.sh <旧tag>      # 回滚到服务器上仍在的历史镜像
#
# 配置（按优先级：环境变量 > docs/deploy-dev.conf）:
#   SERVER         SSH 目标（必填，如 user@host）
#   REMOTE_DIR     服务器部署目录（必填）
#   KEY            SSH 私钥路径（默认 ~/.ssh/github_actions_key）
#   REGISTRY_USER  镜像命名空间（默认 z1joey）
# 数据库口令从仓库根目录 .env 读取（POSTGRES_USER/PASSWORD/DB）。
# =============================================================================
set -euo pipefail

# 本地配置文件（docs/ 整体不入库），环境变量可覆盖其中的值
CONF="$(cd "$(dirname "$0")" && pwd)/docs/deploy-dev.conf"
if [[ -f "$CONF" ]]; then
  # shellcheck source=/dev/null
  source "$CONF"
fi

: "${SERVER:?未配置 SERVER —— 在 docs/deploy-dev.conf 中设置（参考 DEPLOY.md），或用环境变量传入}"
KEY="${KEY:-$HOME/.ssh/github_actions_key}"
: "${REMOTE_DIR:?未配置 REMOTE_DIR —— 在 docs/deploy-dev.conf 中设置}"
REGISTRY_USER="${REGISTRY_USER:-z1joey}"
TAG="${1:-dev-local}"
# 国内网络下官方源常超时，默认走国内镜像源；有代理可改回官方源
PIP_INDEX_URL="${PIP_INDEX_URL:-https://pypi.tuna.tsinghua.edu.cn/simple}"
NPM_REGISTRY="${NPM_REGISTRY:-https://registry.npmmirror.com}"

q() { printf '%q' "$1"; }
sshcmd() { ssh -i "$KEY" -o BatchMode=yes -o ConnectTimeout=15 "$SERVER" "$@"; }

echo "==> ① 检查服务器连通性: $SERVER"
sshcmd 'echo "    OK: $(hostname)"'

echo "==> ② 检查 .env（数据库口令）"
if [[ ! -f .env ]]; then
  echo "错误: 缺少 .env（需要 POSTGRES_USER / POSTGRES_PASSWORD / POSTGRES_DB）" >&2
  echo "       复制仓库里的 .env.example 并填写后重试" >&2
  exit 1
fi
set -a; source ./.env; set +a
: "${POSTGRES_USER:?POSTGRES_USER 未设置}"
: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD 未设置}"
: "${POSTGRES_DB:?POSTGRES_DB 未设置}"

echo "==> ③ 本机构建 linux/amd64 镜像 (tag: $TAG) —— Apple Silicon 上走模拟，稍慢"
docker buildx build --platform linux/amd64 --load \
  --build-arg PIP_INDEX_URL="$PIP_INDEX_URL" \
  -t "$REGISTRY_USER/teacher-workbench-backend:$TAG" ./backend
docker buildx build --platform linux/amd64 --load \
  --build-arg NPM_REGISTRY="$NPM_REGISTRY" \
  -t "$REGISTRY_USER/teacher-workbench-frontend:$TAG" ./frontend

echo "==> ④ 经 SSH 传输镜像到服务器（首次约几百 MB）"
docker save "$REGISTRY_USER/teacher-workbench-backend:$TAG" | gzip \
  | sshcmd 'gunzip | docker load'
docker save "$REGISTRY_USER/teacher-workbench-frontend:$TAG" | gzip \
  | sshcmd 'gunzip | docker load'

echo "==> ⑤ 确保服务器上有 postgres:17（服务器无法自行拉取）"
if ! sshcmd 'docker image inspect postgres:17 >/dev/null 2>&1'; then
  echo "    服务器缺少 postgres:17，从本机搬运…"
  docker pull --platform linux/amd64 postgres:17
  docker save postgres:17 | gzip | sshcmd 'gunzip | docker load'
fi

echo "==> ⑥ 上传 docker-compose.yml 与 .env"
scp -i "$KEY" -o BatchMode=yes docker-compose.yml \
  "$SERVER:$REMOTE_DIR/docker-compose.yml"
# 服务器上的 .env 与最近一次部署保持一致，服务器手动 docker compose 时可用
sshcmd "umask 177; cat > '$REMOTE_DIR/.env'" <<ENVFILE
DOCKERHUB_USERNAME=$REGISTRY_USER
IMAGE_TAG=$TAG
POSTGRES_USER=$POSTGRES_USER
POSTGRES_PASSWORD=$POSTGRES_PASSWORD
POSTGRES_DB=$POSTGRES_DB
ENVFILE

# compose 通过进程环境变量做插值（镜像名/数据库口令），${VAR} 经 printf %q 安全转义
ENV_PREFIX="DOCKERHUB_USERNAME=$(q "$REGISTRY_USER") IMAGE_TAG=$(q "$TAG") \
POSTGRES_USER=$(q "$POSTGRES_USER") POSTGRES_PASSWORD=$(q "$POSTGRES_PASSWORD") \
POSTGRES_DB=$(q "$POSTGRES_DB")"

echo "==> ⑦ 滚动更新（--wait 等待容器通过自身 healthcheck）"
sshcmd "cd '$REMOTE_DIR' && $ENV_PREFIX docker compose up -d --wait --wait-timeout 120 db"
sshcmd "cd '$REMOTE_DIR' && $ENV_PREFIX docker compose up -d --wait --wait-timeout 300 --no-deps backend frontend"

echo "==> ⑧ 服务状态"
sshcmd "cd '$REMOTE_DIR' && $ENV_PREFIX docker compose ps"

echo "==> ⑨ 端到端验证 /api/health"
sshcmd 'curl -fsS --max-time 10 http://127.0.0.1:8001/api/health'
echo ""
echo "✅ 部署完成  tag=$TAG  server=$SERVER"
