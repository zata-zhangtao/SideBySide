SideBySide 部署指南（FastAPI + React）

概览
- 技术栈：后端 FastAPI + SQLModel，前端 Vite + React + TS。
- 推荐部署：Docker Compose（开发/生产均已提供编排）。
- 可选能力：LLM（DashScope/Qwen）用于图片抽词与语义判分。
- 健康检查：`/health` 接口可用于存活探测（参考 `backend/app/main.py:93`）。

目录结构
- `backend/` 后端服务（Uvicorn 启动，`backend/Dockerfile:1`）。
- `frontend/` 前端（Vite 构建 + Nginx 托管，`frontend/Dockerfile:13`）。
- 根目录 Compose：`docker-compose.yml:1`、`docker-compose.override.yml:1`、`docker-compose.prod.yml:1`。
- 环境模板：`.env.example:1`，预置开发/生产示例：`.env.dev:1`、`.env.prod:1`。

开发环境（本机快速启动）
- 先决条件：Docker 24+ 与 Docker Compose v2。
- 启动（热更新 + SQLite + 前后端本机端口映射）：
  - `docker compose --env-file .env.dev up`（或 `cp .env.dev .env && docker compose up`）。
  - 访问：前端 http://localhost:5173 ，后端 http://localhost:8000 ，API 文档 http://localhost:8000/docs 。
- 说明：
  - `docker-compose.override.yml:2` 为开发模式（后端 `--reload`，前端 Vite dev server）。
  - 默认 CORS 允许 `http://localhost:5173`（参见 `backend/app/main.py:59`）。

生产部署（Docker Compose）
- 先决条件：
  - Linux 主机（建议 x86_64），Docker 24+，Docker Compose v2。
  - 开放 80/443 端口（如需 HTTPS）。
- 配置：
  - 复制模板：`cp .env.prod .env` 或直接使用 `--env-file .env.prod`。
  - 必改项：
    - `SECRET_KEY`（强随机串，`.env.prod:9`）。
    - `POSTGRES_PASSWORD`（强密码，`.env.prod:21`）。
    - 如启用 LLM：`DASHSCOPE_API_KEY`（`.env.prod:44`）。
  - 可选：`CORS_ORIGINS`（前后端同源可留空）。
- 启动（前端 Nginx 暴露 80）：
  - `docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.prod up -d`
- 访问：
  - 前端：http://<你的域名或IP>
  - 后端：不直接对外暴露，由前端 Nginx 反向代理 `/api`（`frontend/nginx.conf:16` → `proxy_pass http://backend:8000/api/`）。
- 重要说明：
  - 生产默认数据库为 PostgreSQL（`docker-compose.prod.yml:2` 定义 `db` 服务；后端 `DATABASE_URL` 由 `.env` 构造，参见 `docker-compose.prod.yml:14`）。
  - 前端构建时 `VITE_API_BASE=/api`（同源反代），参见 `frontend/Dockerfile:9` 与 `.env.prod:16`。
  - 后端日志默认为 JSON 并写入容器卷 `/app/logs/app.log`（`docker-compose.prod.yml:21`、`.env.prod:31`、`.env.prod:34`）。

非 Docker 部署（不推荐于生产，仅供单机/调试）
- 后端：
  - Python 3.11+，安装依赖：`pip install -r backend/requirements.txt`。
  - 环境变量：`DATABASE_URL`、`SECRET_KEY`、`CORS_ORIGINS`（可参考 `.env.example:1`）。
  - 启动：在 `backend/` 目录执行 `uvicorn app.main:app --host 0.0.0.0 --port 8000`（`backend/Dockerfile:32`）。
- 前端：
  - Node.js 18+：`cd frontend && npm install && npm run build`，将 `frontend/dist` 交由任意静态服务器托管（Nginx/Caddy）。
  - 或开发模式：`cd frontend && npm install && npm run dev`（默认连到 `http://localhost:8000/api`，见 `frontend/src/api.ts:1`）。

环境变量（常用）
- 应用安全：
  - `SECRET_KEY`：JWT 等加密所需，生产必须改为强随机值（`.env.prod:9`）。
  - `CORS_ORIGINS`：逗号分隔，前后端同源可留空（`.env.prod:11`）。
- 数据库：
  - 开发：`DATABASE_URL=sqlite:////app/data/data.db`（`.env.dev:14`）。
  - 生产：`POSTGRES_*` + `DATABASE_URL`（`.env.prod:18`–`24`）。
- 日志：
  - `LOG_LEVEL`（`DEBUG|INFO|...`）、`LOG_FORMAT`（`text|json`）、`LOG_FILE_PATH`、`LOG_ROTATION_*`（`.env.*`）。
- 前端 API 根：
  - `VITE_API_BASE`（构建期与运行期均可配置；开发 `.env.dev:12`，生产 `.env.prod:16`）。
- LLM（可选）：
  - `LLM_PROVIDER=qwen`、`DASHSCOPE_API_KEY`、`VISION_MODEL`、`TEXT_MODEL` 等（`.env.*`）。
  - 语义判分开关：`USE_LLM_JUDGE_EN2ZH` 与策略（`.env.*`）。

数据库与迁移
- 初始化：应用启动时自动建表并执行“最小非破坏性迁移”（`backend/app/db.py:115`）。
- 迁移框架：未使用 Alembic；生产变更以“新增字段”为主（避免破坏）。
- SQLite → PostgreSQL 迁移建议：
  - 导出业务数据（如通过应用导出词库），或编写一次性脚本从 SQLite 读取后写入 Postgres。
  - 启动前确认 `DATABASE_URL` 已指向 Postgres 并可连接（`docker-compose.prod.yml:14`）。

网络与反向代理
- 内置前端 Nginx 已将 `/api/` 代理到 `backend:8000/api/`（`frontend/nginx.conf:16`）。
- 若你有外层网关（如 Traefik/Caddy/Nginx）：
  - 可将外层 80/443 → `frontend:80`；路径 `/api` 保持透传到后端容器同网络的 `backend:8000`。
  - 若自管 TLS，可在外层终止 HTTPS；容器内部保持 HTTP。

日志与监控
- 查看日志：
  - 开发：`docker compose logs -f backend` / `frontend`。
  - 生产（JSON）：`docker compose -f docker-compose.yml -f docker-compose.prod.yml logs backend | jq`（参考根 `README.md:48`）。
- 健康检查：
  - 端点：`GET /health`（`backend/app/main.py:93`）。
  - Compose 已配置 backend 健康检查（`docker-compose.yml:39`）。

备份与升级
- 备份：
  - PostgreSQL 数据：卷 `postgres_data`（`docker-compose.prod.yml:9`），使用 `pg_dump` 定期备份。
  - 日志：卷 `backend_logs`（`docker-compose.prod.yml:35`）。
- 升级：
  - 拉取新代码 → 复用原有 `.env` 与卷 → 重新 `docker compose up -d --build`。
  - 首次启动会自动执行非破坏性迁移；仍建议在升级前备份数据库。

常见问题（FAQ）
- 访问 80 端口失败：确认主机防火墙/云安全组策略已放通 80/443。
- CORS 跨域：开发模式由后端允许 `http://localhost:5173`（`backend/app/main.py:59`）；生产同源部署可清空 `CORS_ORIGINS`。
- API 根路径：开发直连后端使用 `VITE_API_BASE=http://localhost:8000/api`；生产同源反代使用 `/api`。
- 调整上传大小：修改 `frontend/nginx.conf:5` 的 `client_max_body_size`。
- 并发与性能：生产可考虑为后端设置多 worker（例如改为 `uvicorn ... --workers 2`，通过 Compose 覆盖 `command`），或将 Nginx 置于外层统一网关后水平扩容。

安全加固清单（生产）
- 必改：`SECRET_KEY`、`POSTGRES_PASSWORD`、任何第三方 API Key（`.env.prod`）。
- 关闭调试：生产使用 `LOG_LEVEL=INFO` 且 `LLM_DEBUG=0`（`.env.prod:28`、`.env.prod:72`）。
- 最小暴露：仅暴露前端 80/443；后端不直接映射宿主端口（`docker-compose.prod.yml:38` 注释说明）。
- 证书与 HTTPS：建议在外层网关（Traefik/Caddy/Nginx）终止 TLS 并将流量反代到 `frontend:80`。

验证步骤（部署后）
- 打开前端首页并完成注册/登录，上传 CSV/JSON 词库验证基本功能。
- 打开 API 文档：`/docs`，验证基础接口。
- 如启用 LLM：使用“从图片建库”或“语义判分”功能进行一次端到端验证。

参考文件
- 根 README（含快速命令）：`README.md:1`
- Compose 配置：`docker-compose.yml:1`、`docker-compose.prod.yml:1`、`docker-compose.override.yml:1`
- 前端 Nginx 代理：`frontend/nginx.conf:16`
- 前端 API 基址：`frontend/src/api.ts:1`
- 健康检查端点：`backend/app/main.py:93`

离线镜像传输（ssh + docker save/load）
- 场景：服务器无法从镜像仓库拉取，或希望直接通过 SSH 传输镜像层。
- 我们提供脚本：`scripts/deploy_via_ssh.sh`，支持在本地构建镜像，通过 `docker save | ssh ... docker load` 传输到服务器，并在远端以 Compose 启动。
- 先决条件：
  - 本地与服务器均已安装 Docker（服务器需有 Compose v2 或 `docker-compose`）。
  - 已配置无密码 SSH（公钥登录）。
- 快速使用示例：
  - 设置镜像名（可按需替换为你的仓库命名）：
    - `export BACKEND_IMAGE=sidebyside-backend:1.0.0`
    - `export FRONTEND_IMAGE=sidebyside-frontend:1.0.0`
  - 执行脚本：
    - `bash scripts/deploy_via_ssh.sh -r your-user@your-server -d /opt/sidebyside` \
      `-b "$BACKEND_IMAGE" -f "$FRONTEND_IMAGE"`
  - 说明：
    - 构建：使用 buildx 按平台构建并 `--load` 到本地 Docker。
    - 传输：`docker save $IMAGE | ssh user@host 'docker load'`。
    - 部署：远端合并 `docker-compose.yml + docker-compose.prod.yml + docker-compose.deploy.yml`，以本地加载的镜像启动：
      `docker compose up -d --no-build --pull=never`。
