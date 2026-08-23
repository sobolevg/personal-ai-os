#!/usr/bin/env bash
set -euo pipefail

OS_DIR="${OS_DIR:-/opt/personal-ai-os}"
HERMES_DIR="${HERMES_DIR:-/usr/local/lib/hermes-agent}"
HERMES_HOME="${HERMES_HOME:-/root/.hermes}"
HERMES_PYTHON="${HERMES_PYTHON:-${HERMES_DIR}/venv/bin/python}"
CONFIG_FILE="${HERMES_HOME}/config.yaml"
TOOLSETS_FILE="${HERMES_DIR}/toolsets.py"
DROPIN_DIR="/etc/systemd/system/hermes-gateway.service.d"
DROPIN_FILE="${DROPIN_DIR}/personal-ai-os-mac-worker.conf"
BACKUP_ROOT="${HERMES_HOME}/backups"
TOOLSET_NAME="mac_worker"
SSH_HOST_ALIAS="${SSH_HOST_ALIAS:-personal-ai-os-mac-worker}"

usage() { echo "Usage: $0 plan|verify|enable --apply|disable --apply"; }

require_preconditions() {
  [[ -f "$CONFIG_FILE" && -f "$TOOLSETS_FILE" && -x "$HERMES_PYTHON" ]]
  grep -q '"mac_worker"' "$TOOLSETS_FILE"
  PYTHONPATH="$OS_DIR" PERSONAL_AI_OS_MAC_WORKER_SSH_HOST="$SSH_HOST_ALIAS" "$HERMES_PYTHON" - <<'PY'
import json
from services.mac_worker.client import call_mac_worker
from services.mac_worker.protocol import WorkerRequest

result = call_mac_worker(WorkerRequest.from_dict({"operation": "doctor"}), timeout=20)
print(json.dumps(result, ensure_ascii=False, sort_keys=True))
if not result.get("success"):
    raise SystemExit("Mac worker doctor failed")
if not result.get("agents", {}).get("codex", {}).get("authenticated"):
    raise SystemExit("Codex is not authenticated on the Mac worker")
PY
}

set_toolset() {
  desired="$1"
  "$HERMES_PYTHON" - "$TOOLSET_NAME" "$desired" <<'PY'
import sys
from hermes_cli.tools_config import load_config, save_config

name = sys.argv[1]
desired = sys.argv[2] == "true"
config = load_config()
items = [str(item) for item in config.setdefault("platform_toolsets", {}).setdefault("telegram", [])]
items = sorted(set(items) | {name}) if desired else [item for item in items if item != name]
config["platform_toolsets"]["telegram"] = items
save_config(config)
print(f"telegram_toolsets={items}")
PY
}

backup() {
  timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
  backup_dir="${BACKUP_ROOT}/personal-ai-os-mac-worker-enable-${timestamp}"
  mkdir -p "$backup_dir"
  cp "$CONFIG_FILE" "$backup_dir/config.yaml"
  [[ ! -e "$DROPIN_FILE" ]] || cp "$DROPIN_FILE" "$backup_dir/"
  echo "$backup_dir"
}

write_dropin() {
  mkdir -p "$DROPIN_DIR"
  cat > "$DROPIN_FILE" <<EOF
[Service]
Environment="PERSONAL_AI_OS_MAC_WORKER_SSH_HOST=${SSH_HOST_ALIAS}"
EOF
  chmod 600 "$DROPIN_FILE"
  systemctl daemon-reload
}

verify() {
  require_preconditions
  "$HERMES_PYTHON" - "$TOOLSET_NAME" <<'PY'
import sys
from hermes_cli.tools_config import _get_platform_tools, load_config

name = sys.argv[1]
config = load_config()
telegram = config.get("platform_toolsets", {}).get("telegram", [])
print(f"enabled={name in telegram}")
print(f"effective={name in _get_platform_tools(config, 'telegram')}")
PY
}

plan() {
  cat <<PLAN
Mac worker production enablement plan

Precondition: a live forced-command SSH doctor check with authenticated Codex.
Would manage:
  $CONFIG_FILE
  $DROPIN_FILE
Would not restart Hermes automatically.
PLAN
}

case "${1:-}" in
  plan) plan ;;
  verify) verify ;;
  enable)
    [[ "${2:-}" == "--apply" ]] || exit 2
    require_preconditions
    backup
    write_dropin
    set_toolset true
    ;;
  disable)
    [[ "${2:-}" == "--apply" ]] || exit 2
    backup
    set_toolset false
    [[ ! -e "$DROPIN_FILE" ]] || mv "$DROPIN_FILE" "${DROPIN_FILE}.disabled"
    systemctl daemon-reload
    ;;
  *) usage; exit 2 ;;
esac
