#!/usr/bin/env bash
set -euo pipefail

# One-click deploy script for TextRPG server.
# Default behavior:
# 1) install/update Python deps
# 2) restart backend (supervisor)
# 3) restart frontend (pm2)
# 4) run local health checks

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PYTHON="${ROOT_DIR}/.venv/bin/python"
VENV_PIP="${ROOT_DIR}/.venv/bin/pip"

BACKEND_HEALTH_URL="${BACKEND_HEALTH_URL:-http://127.0.0.1:8000/health}"
FRONTEND_HEALTH_URL="${FRONTEND_HEALTH_URL:-http://127.0.0.1:3000}"

SUPERVISOR_SERVICE="${SUPERVISOR_SERVICE:-textrpg_api:*}"
PM2_APP_NAME="${PM2_APP_NAME:-textrpg_web}"

SKIP_INSTALL=0
SKIP_RESTART_BACKEND=0
SKIP_RESTART_FRONTEND=0

log() {
  echo "[deploy] $*"
}

usage() {
  cat <<'EOF'
Usage: ./scripts/deploy.sh [options]

Options:
  --skip-install           Skip pip install -r requirements.txt
  --skip-restart-backend   Skip restarting supervisor backend service
  --skip-restart-frontend  Skip restarting pm2 frontend app
  -h, --help               Show this help

Environment overrides:
  SUPERVISOR_SERVICE   default: textrpg_api:*
  PM2_APP_NAME         default: textrpg_web
  BACKEND_HEALTH_URL   default: http://127.0.0.1:8000/health
  FRONTEND_HEALTH_URL  default: http://127.0.0.1:3000
EOF
}

while (($#)); do
  case "$1" in
    --skip-install)
      SKIP_INSTALL=1
      ;;
    --skip-restart-backend)
      SKIP_RESTART_BACKEND=1
      ;;
    --skip-restart-frontend)
      SKIP_RESTART_FRONTEND=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      usage
      exit 1
      ;;
  esac
  shift
done

if [[ ! -x "${VENV_PYTHON}" ]]; then
  echo "Missing virtualenv Python: ${VENV_PYTHON}"
  exit 1
fi

if [[ ! -x "${VENV_PIP}" ]]; then
  echo "Missing virtualenv pip: ${VENV_PIP}"
  exit 1
fi

cd "${ROOT_DIR}"

if [[ ${SKIP_INSTALL} -eq 0 ]]; then
  log "Installing Python dependencies"
  "${VENV_PIP}" install -r requirements.txt
else
  log "Skipping dependency install"
fi

if [[ ${SKIP_RESTART_BACKEND} -eq 0 ]]; then
  if [[ -x /www/server/panel/pyenv/bin/supervisorctl ]]; then
    log "Restarting backend via /www/server/panel/pyenv/bin/supervisorctl (${SUPERVISOR_SERVICE})"
    /www/server/panel/pyenv/bin/supervisorctl restart "${SUPERVISOR_SERVICE}"
  elif command -v supervisorctl >/dev/null 2>&1; then
    log "Restarting backend via supervisorctl (${SUPERVISOR_SERVICE})"
    supervisorctl restart "${SUPERVISOR_SERVICE}"
  else
    echo "supervisorctl not found; cannot restart backend"
    exit 1
  fi
else
  log "Skipping backend restart"
fi

if [[ ${SKIP_RESTART_FRONTEND} -eq 0 ]]; then
  if command -v pm2 >/dev/null 2>&1; then
    log "Restarting frontend via pm2 (${PM2_APP_NAME})"
    pm2 restart "${PM2_APP_NAME}"
  else
    echo "pm2 not found; cannot restart frontend"
    exit 1
  fi
else
  log "Skipping frontend restart"
fi

sleep 2

log "Checking backend health: ${BACKEND_HEALTH_URL}"
curl -fsS "${BACKEND_HEALTH_URL}" >/dev/null

log "Checking frontend health: ${FRONTEND_HEALTH_URL}"
curl -fsSI "${FRONTEND_HEALTH_URL}" >/dev/null

log "Deploy completed successfully"
