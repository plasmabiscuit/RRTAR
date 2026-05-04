#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Bootstrap an Ubuntu 20.04 VM for the RRTard processing/backend runtime.

This script prepares:
  - system packages required by the current PDF/XML pipeline
  - an application user
  - /opt code checkout
  - persistent server-side reference data for schemas/config/contacts
  - a Python virtualenv
  - a shared API-key environment file
  - optional systemd services if start commands are provided

Usage:
  sudo ./deploy/bootstrap_oracle_vm.sh --api-key <shared-key> [options]

Options:
  --api-key <key>              Shared API key to write into the env file.
  --app-user <user>            System user to run the app. Default: rrtard
  --app-group <group>          System group to run the app. Default: rrtard
  --install-root <path>        Install root for app code and venv. Default: /opt/rrtard
  --state-root <path>          Persistent state root. Default: /var/lib/rrtard
  --env-file <path>            Environment file path. Default: /etc/rrtard/rrtard.env
  --host <host>                Default bind host for future backend. Default: 0.0.0.0
  --port <port>                Default bind port for future backend. Default: 8081
  --backend-cmd <command>      Install/enable a backend systemd service with this command.
  --worker-cmd <command>       Install/enable a worker systemd service with this command.
  --refresh-reference-data     Overwrite persistent config/data/schemas from the repo copy.
  --help                       Show this help text.

Examples:
  sudo ./deploy/bootstrap_oracle_vm.sh --api-key "$(openssl rand -hex 32)"

  sudo ./deploy/bootstrap_oracle_vm.sh \
    --api-key "replace-me" \
    --backend-cmd "/opt/rrtard/.venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8081" \
    --worker-cmd "/opt/rrtard/.venv/bin/python -m backend.worker"
EOF
}

require_root() {
  if [[ "${EUID}" -ne 0 ]]; then
    echo "This script must be run as root." >&2
    exit 1
  fi
}

log() {
  printf '\n[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

APP_USER="rrtard"
APP_GROUP="rrtard"
INSTALL_ROOT="/opt/rrtard"
STATE_ROOT="/var/lib/rrtard"
ENV_FILE="/etc/rrtard/rrtard.env"
HOST="0.0.0.0"
PORT="8081"
BACKEND_CMD=""
WORKER_CMD=""
REFRESH_REFERENCE_DATA="0"
API_KEY=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --api-key)
      API_KEY="${2:-}"
      shift 2
      ;;
    --app-user)
      APP_USER="${2:-}"
      shift 2
      ;;
    --app-group)
      APP_GROUP="${2:-}"
      shift 2
      ;;
    --install-root)
      INSTALL_ROOT="${2:-}"
      shift 2
      ;;
    --state-root)
      STATE_ROOT="${2:-}"
      shift 2
      ;;
    --env-file)
      ENV_FILE="${2:-}"
      shift 2
      ;;
    --host)
      HOST="${2:-}"
      shift 2
      ;;
    --port)
      PORT="${2:-}"
      shift 2
      ;;
    --backend-cmd)
      BACKEND_CMD="${2:-}"
      shift 2
      ;;
    --worker-cmd)
      WORKER_CMD="${2:-}"
      shift 2
      ;;
    --refresh-reference-data)
      REFRESH_REFERENCE_DATA="1"
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ -z "${API_KEY}" ]]; then
  echo "--api-key is required." >&2
  usage >&2
  exit 1
fi

require_root

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
APP_DIR="${INSTALL_ROOT}/app"
VENV_DIR="${INSTALL_ROOT}/.venv"
ENV_DIR="$(dirname "${ENV_FILE}")"
CONFIG_DIR="${STATE_ROOT}/config"
DATA_DIR="${STATE_ROOT}/data"
SCHEMA_DIR="${STATE_ROOT}/schemas"
DB_DIR="${STATE_ROOT}/db"
TMP_DIR="${STATE_ROOT}/tmp"
LOG_DIR="${STATE_ROOT}/log"
REQ_FILE="${REPO_ROOT}/deploy/requirements.vm.txt"

if [[ ! -f "${REQ_FILE}" ]]; then
  echo "Missing requirements file: ${REQ_FILE}" >&2
  exit 1
fi

install_packages() {
  log "Installing apt packages"
  export DEBIAN_FRONTEND=noninteractive
  apt-get update
  apt-get install -y \
    ca-certificates \
    curl \
    git \
    rsync \
    sqlite3 \
    python3 \
    python3-dev \
    python3-venv \
    build-essential \
    pkg-config \
    poppler-utils \
    qpdf \
    libqpdf-dev \
    libxml2-dev \
    libxslt1-dev \
    zlib1g-dev
}

ensure_group() {
  if ! getent group "${APP_GROUP}" >/dev/null; then
    log "Creating group ${APP_GROUP}"
    groupadd --system "${APP_GROUP}"
  fi
}

ensure_user() {
  if ! id -u "${APP_USER}" >/dev/null 2>&1; then
    log "Creating user ${APP_USER}"
    useradd \
      --system \
      --gid "${APP_GROUP}" \
      --home-dir "${INSTALL_ROOT}" \
      --shell /usr/sbin/nologin \
      "${APP_USER}"
  fi
}

create_dirs() {
  log "Creating application directories"
  install -d -m 0755 -o root -g root "${INSTALL_ROOT}"
  install -d -m 0755 -o "${APP_USER}" -g "${APP_GROUP}" "${APP_DIR}"
  install -d -m 0750 -o root -g "${APP_GROUP}" "${ENV_DIR}"
  install -d -m 0755 -o "${APP_USER}" -g "${APP_GROUP}" \
    "${STATE_ROOT}" \
    "${CONFIG_DIR}" \
    "${DATA_DIR}" \
    "${SCHEMA_DIR}" \
    "${DB_DIR}" \
    "${TMP_DIR}" \
    "${LOG_DIR}"
}

sync_repo() {
  log "Syncing repo into ${APP_DIR}"
  rsync -a --delete \
    --exclude '.git/' \
    --exclude '.venv/' \
    --exclude '.chrome-debug-profile/' \
    --exclude '__pycache__/' \
    --exclude 'node_modules/' \
    --exclude 'audit/' \
    --exclude 'review/' \
    --exclude 'input-pdfs/' \
    --exclude 'input-budget-pdfs/' \
    --exclude 'input-performance-site-pdfs/' \
    --exclude 'extracted-xml/' \
    --exclude 'extracted-attachments/' \
    --exclude 'extracted-budget-xml/' \
    --exclude 'extracted-budget-attachments/' \
    --exclude 'extracted-performance-site-xml/' \
    --exclude 'extracted-performance-site-attachments/' \
    "${REPO_ROOT}/" "${APP_DIR}/"
  chown -R "${APP_USER}:${APP_GROUP}" "${APP_DIR}"
}

sync_reference_dir() {
  local src="$1"
  local dest="$2"

  if [[ ! -d "${src}" ]]; then
    return
  fi

  if [[ "${REFRESH_REFERENCE_DATA}" == "1" ]]; then
    rsync -a --delete "${src}/" "${dest}/"
  else
    rsync -a --ignore-existing "${src}/" "${dest}/"
  fi
}

sync_reference_data() {
  log "Syncing persistent reference data"
  sync_reference_dir "${REPO_ROOT}/config" "${CONFIG_DIR}"
  sync_reference_dir "${REPO_ROOT}/data" "${DATA_DIR}"
  sync_reference_dir "${REPO_ROOT}/schemas" "${SCHEMA_DIR}"
  chown -R "${APP_USER}:${APP_GROUP}" "${CONFIG_DIR}" "${DATA_DIR}" "${SCHEMA_DIR}"
}

create_venv() {
  log "Creating/updating Python virtualenv"
  if [[ ! -x "${VENV_DIR}/bin/python" ]]; then
    python3 -m venv "${VENV_DIR}"
  fi
  "${VENV_DIR}/bin/pip" install --upgrade pip setuptools wheel
  "${VENV_DIR}/bin/pip" install -r "${REQ_FILE}"
  chown -R "${APP_USER}:${APP_GROUP}" "${VENV_DIR}"
}

write_env_file() {
  log "Writing environment file ${ENV_FILE}"
  install -m 0640 -o root -g "${APP_GROUP}" /dev/null "${ENV_FILE}"
  cat > "${ENV_FILE}" <<EOF
RRTARD_INSTALL_ROOT=${INSTALL_ROOT}
RRTARD_APP_DIR=${APP_DIR}
RRTARD_VENV_DIR=${VENV_DIR}
RRTARD_STATE_ROOT=${STATE_ROOT}
RRTARD_CONFIG_DIR=${CONFIG_DIR}
RRTARD_DATA_DIR=${DATA_DIR}
RRTARD_SCHEMAS_DIR=${SCHEMA_DIR}
RRTARD_DB_DIR=${DB_DIR}
RRTARD_DB_PATH=${DB_DIR}/rrtard.sqlite3
RRTARD_TMP_DIR=${TMP_DIR}
RRTARD_LOG_DIR=${LOG_DIR}
RRTARD_HOST=${HOST}
RRTARD_PORT=${PORT}
RRTARD_SHARED_API_KEY=${API_KEY}
EOF
}

write_service() {
  local service_name="$1"
  local exec_cmd="$2"
  local service_path="/etc/systemd/system/${service_name}.service"

  log "Installing systemd service ${service_name}"
  cat > "${service_path}" <<EOF
[Unit]
Description=RRTard ${service_name}
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${APP_USER}
Group=${APP_GROUP}
WorkingDirectory=${APP_DIR}
EnvironmentFile=${ENV_FILE}
ExecStart=/usr/bin/env bash -lc '${exec_cmd}'
Restart=on-failure
RestartSec=3
StandardOutput=append:${LOG_DIR}/${service_name}.log
StandardError=append:${LOG_DIR}/${service_name}.log

[Install]
WantedBy=multi-user.target
EOF
}

enable_services() {
  local changed="0"

  if [[ -n "${BACKEND_CMD}" ]]; then
    write_service "rrtard-backend" "${BACKEND_CMD}"
    changed="1"
  fi

  if [[ -n "${WORKER_CMD}" ]]; then
    write_service "rrtard-worker" "${WORKER_CMD}"
    changed="1"
  fi

  if [[ "${changed}" == "1" ]]; then
    log "Reloading systemd"
    systemctl daemon-reload
  fi

  if [[ -n "${BACKEND_CMD}" ]]; then
    systemctl enable --now rrtard-backend.service
  fi

  if [[ -n "${WORKER_CMD}" ]]; then
    systemctl enable --now rrtard-worker.service
  fi
}

print_summary() {
  cat <<EOF

Bootstrap complete.

Install root:
  ${INSTALL_ROOT}

Persistent reference data:
  ${CONFIG_DIR}
  ${DATA_DIR}
  ${SCHEMA_DIR}

State and temp paths:
  ${DB_DIR}
  ${TMP_DIR}
  ${LOG_DIR}

Environment file:
  ${ENV_FILE}

Python virtualenv:
  ${VENV_DIR}

Current service state:
EOF

  if [[ -n "${BACKEND_CMD}" ]]; then
    echo "  rrtard-backend.service enabled"
  else
    echo "  backend service not installed"
  fi

  if [[ -n "${WORKER_CMD}" ]]; then
    echo "  rrtard-worker.service enabled"
  else
    echo "  worker service not installed"
  fi

  cat <<EOF

Next steps:
  1. SSH to the VM and verify the env file contents:
       sudo cat ${ENV_FILE}
  2. If you later add a backend entrypoint, rerun this script with:
       --backend-cmd "<start command>"
       --worker-cmd "<start command>"
  3. Keep runtime job files ephemeral under:
       ${TMP_DIR}
EOF
}

install_packages
ensure_group
ensure_user
create_dirs
sync_repo
sync_reference_data
create_venv
write_env_file
enable_services
print_summary
