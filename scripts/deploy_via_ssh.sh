#!/usr/bin/env bash
set -euo pipefail

#This configures strict error handling:
# -e: Exit immediately if any command returns a non‑zero status (fails).
# -u: Treat use of undefined variables as an error and exit.
# -o pipefail: In a pipeline (cmd1 | cmd2 | cmd3), the whole pipeline fails if any command fails, not just the last one.




# SideBySide: 本地构建镜像并通过 SSH 传输到远程服务器，然后用 Compose 启动
# 需求：
# - 本地 Docker（使用 docker build 构建 amd64 平台镜像）
# - 远程服务器安装 Docker 与 Compose（docker compose 或 docker-compose）
# - 已配置无密码 SSH（公钥登录）

usage() {
  cat <<'EOF'
用法：
  scripts/deploy_via_ssh.sh -r <user@host> [-d <remote_dir>] \
    -b <backend_image:tag> -f <frontend_image:tag> \
    [-p <platform>] [-e <env_file>] [--vite-api-base <path>]

参数：
  -r  远程主机（user@host 或通过 SSH 配置的别名）
  -d  远程部署目录（默认：/opt/sidebyside）
  -b  后端镜像名:标签（例如 sidebyside-backend:1.0.0）
  -f  前端镜像名:标签（例如 sidebyside-frontend:1.0.0）
  -p  目标平台，默认 linux/amd64（通过拉取 amd64 基础镜像并构建）
  -e  本地环境文件路径，用作远端 --env-file（默认：使用远端已有 .env.prod）
      注意：包含密钥/密码，谨慎分发。
  --vite-api-base  前端构建时的 API 根路径（默认：/api）

示例：
  export BACKEND_IMAGE=sidebyside-backend:1.0.0
  export FRONTEND_IMAGE=sidebyside-frontend:1.0.0
  bash scripts/deploy_via_ssh.sh -r your-user@your-server \
    -d /opt/sidebyside -b "$BACKEND_IMAGE" -f "$FRONTEND_IMAGE"

  # 使用 docker build 直接构建 amd64 平台镜像：
  bash scripts/deploy_via_ssh.sh -r your-user@your-server \
    -b "$BACKEND_IMAGE" -f "$FRONTEND_IMAGE"
EOF
}

# 验证镜像是否存在的辅助函数
verify_image_exists() {
  local image="$1"
  echo "  - 验证镜像 $image..."
  if docker image inspect "$image" >/dev/null 2>&1; then
    echo "    ✓ 镜像存在"
    return 0
  else
    echo "    ✗ 镜像不存在"
    return 1
  fi
}

REMOTE=""
REMOTE_DIR="/opt/sidebyside"
BACKEND_IMAGE=""
FRONTEND_IMAGE=""
PLATFORM="linux/amd64"
ENV_FILE=""
VITE_API_BASE="/api"

while [[ $# -gt 0 ]]; do
  case "$1" in
    -r) REMOTE="$2"; shift 2;;
    -d) REMOTE_DIR="$2"; shift 2;;
    -b) BACKEND_IMAGE="$2"; shift 2;;
    -f) FRONTEND_IMAGE="$2"; shift 2;;
    -p) PLATFORM="$2"; shift 2;;
    -e) ENV_FILE="$2"; shift 2;;
    --vite-api-base) VITE_API_BASE="$2"; shift 2;;
    -h|--help) usage; exit 0;;
    *) echo "未知参数: $1"; usage; exit 1;;
  esac
done

if [[ -z "$REMOTE" || -z "$BACKEND_IMAGE" || -z "$FRONTEND_IMAGE" ]]; then
  echo "缺少必要参数"
  usage
  exit 1
fi

echo "==> 目标平台: $PLATFORM"
echo "==> 远程主机: $REMOTE"
echo "==> 远程目录: $REMOTE_DIR"
echo "==> 后端镜像: $BACKEND_IMAGE"
echo "==> 前端镜像: $FRONTEND_IMAGE"
echo "==> 前端 API 根: $VITE_API_BASE"

echo "==> 预拉取 amd64 平台的基础镜像（用于本地构建）"
# 拉取前端构建所需的基础镜像（指定 amd64 平台）
echo "  - 拉取 node:20-alpine..."
docker pull --platform linux/amd64 node:20-alpine 2>&1 | grep -E "(Pulling|Digest|Status|Download)" || true
echo "  - 拉取 nginx:1.27-alpine..."
docker pull --platform linux/amd64 nginx:1.27-alpine 2>&1 | grep -E "(Pulling|Digest|Status|Download)" || true
# 拉取后端基础镜像（指定 amd64 平台）
echo "  - 拉取 ghcr.io/astral-sh/uv:python3.11-bookworm..."
docker pull --platform linux/amd64 ghcr.io/astral-sh/uv:python3.11-bookworm 2>&1 | grep -E "(Pulling|Digest|Status|Download)" || true
# 注意：postgres:15-alpine 镜像将由远程服务器自动拉取，无需本地传输

# 启用 Docker BuildKit 以提高构建性能
export DOCKER_BUILDKIT=1

echo "==> 构建后端镜像 ($BACKEND_IMAGE)"
# 使用 docker build 直接构建 amd64 平台镜像
if ! docker build \
  --platform "$PLATFORM" \
  -t "$BACKEND_IMAGE" \
  -f backend/Dockerfile backend \
  2>&1 | tee /tmp/build_backend.log; then
  echo "  ⚠️  Docker 构建失败，检查错误日志..."
  if grep -q "timeout\|DeadlineExceeded\|failed to fetch" /tmp/build_backend.log; then
    echo "  💡 检测到网络超时问题，建议："
    echo "     1. 配置 Docker 镜像加速器（推荐）"
    echo "     2. 或检查网络连接后重试"
    echo "     3. 或使用代理：export HTTP_PROXY=..."
    exit 1
  fi
  exit 1
fi

echo "==> 构建前端镜像 ($FRONTEND_IMAGE)"
# 使用 docker build 直接构建 amd64 平台镜像
if ! docker build \
  --platform "$PLATFORM" \
  -t "$FRONTEND_IMAGE" \
  -f frontend/Dockerfile frontend \
  --build-arg VITE_API_BASE="$VITE_API_BASE" \
  2>&1 | tee /tmp/build_frontend.log; then
  echo "  ⚠️  Docker 构建失败，检查错误日志..."
  if grep -q "timeout\|DeadlineExceeded\|failed to fetch" /tmp/build_frontend.log; then
    echo "  💡 检测到网络超时问题，建议："
    echo "     1. 配置 Docker 镜像加速器（推荐）"
    echo "     2. 或检查网络连接后重试"
    echo "     3. 或使用代理：export HTTP_PROXY=..."
    exit 1
  fi
  exit 1
fi

echo "==> 远程创建目录：$REMOTE_DIR"
ssh "$REMOTE" "mkdir -p '$REMOTE_DIR'"

echo "==> 传输 Compose 文件到远端"
if command -v rsync >/dev/null 2>&1; then
  rsync -avz docker-compose.yml docker-compose.prod.yml docker-compose.deploy.yml "$REMOTE:$REMOTE_DIR/"
else
  echo "rsync 未安装，改用 scp"
  scp docker-compose.yml docker-compose.prod.yml docker-compose.deploy.yml "$REMOTE:$REMOTE_DIR/"
fi

if [[ -n "$ENV_FILE" ]]; then
  echo "==> 传输环境文件：$ENV_FILE -> $REMOTE:$REMOTE_DIR/.env.prod"
  scp "$ENV_FILE" "$REMOTE:$REMOTE_DIR/.env.prod"
else
  echo "==> 未指定环境文件（-e），将使用远端已有 .env.prod"
  echo "    提示：如需更新远端环境变量，请使用 -e 参数指定本地环境文件"
  echo "    例如：-e .env.prod"
fi

echo "==> 传输并加载镜像（后端）"
docker save "$BACKEND_IMAGE" | ssh "$REMOTE" 'docker load'

echo "==> 传输并加载镜像（前端）"
docker save "$FRONTEND_IMAGE" | ssh "$REMOTE" 'docker load'

echo "==> 远端启动 Compose 服务（postgres 镜像将自动拉取）"

# 始终使用 --env-file .env.prod 以确保生产环境变量被正确加载
ssh "$REMOTE" "set -euo pipefail; \
  cd '$REMOTE_DIR'; \
  if docker compose version >/dev/null 2>&1; then C='docker compose'; \
  elif command -v docker-compose >/dev/null 2>&1; then C='docker-compose'; \
  else echo '未找到 docker compose 或 docker-compose' >&2; exit 1; fi; \
  BACKEND_IMAGE='$BACKEND_IMAGE' FRONTEND_IMAGE='$FRONTEND_IMAGE' \
    \$C -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.deploy.yml \
    --env-file .env.prod up -d --no-build --pull=missing"

echo "==> 部署完成。验证：在浏览器访问你的域名/IP；或远端执行："
echo "    ssh $REMOTE 'docker ps'"
echo "    ssh $REMOTE 'docker logs -f $(docker ps --filter name=backend -q)'"
