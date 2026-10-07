#!/usr/bin/env bash
# Deploy the RAG assistant on a fresh Ubuntu 22.04/24.04 machine
# (AWS EC2, any cloud VM, or a local VM). Works both as EC2 "user data"
# and when run by hand over SSH.
#
#   curl -fsSL https://raw.githubusercontent.com/manyaagarwal23/disaster-response-intelligence-repo-hub/main/deploy/install_on_ubuntu.sh | sudo GROQ_API_KEY=gsk_... bash
#
# Environment (all optional):
#   GROQ_API_KEY   Groq key; without it the service runs in search-only mode
#   REPO_URL       git repository to deploy (default: the project repo)
#   REPO_REF       branch or tag to deploy (default: main)
#   APP_DIR        install directory (default: /opt/disaster-response-rag)
#   PORT           public port (default: 8000)
set -euo pipefail

REPO_URL=${REPO_URL:-https://github.com/manyaagarwal23/disaster-response-intelligence-repo-hub.git}
REPO_REF=${REPO_REF:-main}
APP_DIR=${APP_DIR:-/opt/disaster-response-rag}
PORT=${PORT:-8000}

log() { echo "[deploy] $*"; }

if [ "$(id -u)" -ne 0 ]; then
    echo "Run as root (sudo)."; exit 1
fi

# ---- Docker -----------------------------------------------------------
if ! command -v docker >/dev/null 2>&1; then
    log "installing Docker"
    apt-get update -qq
    apt-get install -y -qq ca-certificates curl git
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
    chmod a+r /etc/apt/keyrings/docker.asc
    . /etc/os-release
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" \
        > /etc/apt/sources.list.d/docker.list
    apt-get update -qq
    apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-compose-plugin
    systemctl enable --now docker
fi

# ---- Code ---------------------------------------------------------------
if [ -d "$APP_DIR/.git" ]; then
    log "updating $APP_DIR"
    git -C "$APP_DIR" fetch -q origin "$REPO_REF"
    git -C "$APP_DIR" checkout -q FETCH_HEAD
else
    log "cloning $REPO_URL ($REPO_REF) into $APP_DIR"
    git clone -q --branch "$REPO_REF" --depth 1 "$REPO_URL" "$APP_DIR"
fi

# ---- Secrets ------------------------------------------------------------
if [ -n "${GROQ_API_KEY:-}" ]; then
    umask 077
    printf 'GROQ_API_KEY=%s\nPORT=%s\n' "$GROQ_API_KEY" "$PORT" > "$APP_DIR/.env"
    log "wrote $APP_DIR/.env"
elif [ ! -f "$APP_DIR/.env" ]; then
    printf 'PORT=%s\n' "$PORT" > "$APP_DIR/.env"
    log "no GROQ_API_KEY given: service will run in search-only mode (edit $APP_DIR/.env later)"
fi

# ---- Run -----------------------------------------------------------------
log "building and starting (first start builds the vector DB, 20-40 min)"
cd "$APP_DIR"
docker compose up -d --build

cat <<EOF

[deploy] started. Check progress with:
    docker compose -f $APP_DIR/docker-compose.yml logs -f
    curl http://localhost:$PORT/healthz      -> {"database_ready": true} when ready
Open http://<this-machine-ip>:$PORT (open port $PORT in the firewall / security group).
EOF
