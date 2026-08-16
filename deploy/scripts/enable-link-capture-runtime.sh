#!/usr/bin/env bash
set -euo pipefail

HERMES_DIR="${HERMES_DIR:-/usr/local/lib/hermes-agent}"
HERMES_HOME="${HERMES_HOME:-/root/.hermes}"
HERMES_PYTHON="${HERMES_PYTHON:-${HERMES_DIR}/venv/bin/python}"
BACKUP_ROOT="${BACKUP_ROOT:-${HERMES_HOME}/backups}"
CONFIG_FILE="${HERMES_HOME}/config.yaml"
TOOLSETS_FILE="${HERMES_DIR}/toolsets.py"
DROPIN_DIR="/etc/systemd/system/hermes-gateway.service.d"
DROPIN_FILE="${DROPIN_DIR}/personal-ai-os-link-capture.conf"
TOOLSET_NAME="personal_ai_os_link_capture"

usage() {
  echo "Usage: $0 plan|verify|enable --apply|enable-write --apply|disable --apply"
}

require_preconditions() {
  [[ -f "$CONFIG_FILE" && -f "$TOOLSETS_FILE" && -x "$HERMES_PYTHON" ]]
  grep -q "\"${TOOLSET_NAME}\"" "$TOOLSETS_FILE"
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
  backup_dir="${BACKUP_ROOT}/personal-ai-os-link-enable-${timestamp}"
  mkdir -p "$backup_dir"
  cp "$CONFIG_FILE" "$backup_dir/config.yaml"
  [[ ! -e "$DROPIN_FILE" ]] || cp "$DROPIN_FILE" "$backup_dir/"
  echo "$backup_dir"
}

enable_write() {
  [[ -n "${NOTION_DATABASE_ID:-}" ]] || {
    echo "NOTION_DATABASE_ID is required for enable-write" >&2
    exit 2
  }
  [[ "$NOTION_DATABASE_ID" =~ ^[0-9a-fA-F-]{32,36}$ ]] || {
    echo "NOTION_DATABASE_ID has an invalid format" >&2
    exit 2
  }
  mkdir -p "$DROPIN_DIR"
  cat > "$DROPIN_FILE" <<EOF
[Service]
Environment="NOTION_DATABASE_ID=${NOTION_DATABASE_ID}"
Environment="PERSONAL_AI_OS_LINK_CAPTURE_EXECUTE_ENABLED=1"
EOF
  chmod 600 "$DROPIN_FILE"
  systemctl daemon-reload
}

verify() {
  require_preconditions
  "$HERMES_PYTHON" - "$TOOLSET_NAME" <<'PY'
import sys
from hermes_cli.tools_config import load_config, _get_platform_tools
name = sys.argv[1]
config = load_config()
telegram = config.get("platform_toolsets", {}).get("telegram", [])
print(f"telegram_toolsets={telegram}")
print(f"enabled={name in telegram}")
print(f"effective={name in _get_platform_tools(config, 'telegram')}")
PY
  echo "write_dropin_present=$([[ -f "$DROPIN_FILE" ]] && echo true || echo false)"
}

plan() {
  cat <<PLAN
Link capture enablement plan

Would manage:
  $CONFIG_FILE
  $DROPIN_FILE (enable-write only)

Would not restart hermes-gateway automatically.
PLAN
}

case "${1:-}" in
  plan) plan ;;
  verify) verify ;;
  enable)
    [[ "${2:-}" == "--apply" ]] || exit 2
    require_preconditions
    backup
    set_toolset true
    ;;
  enable-write)
    [[ "${2:-}" == "--apply" ]] || exit 2
    require_preconditions
    backup
    set_toolset true
    enable_write
    ;;
  disable)
    [[ "${2:-}" == "--apply" ]] || exit 2
    require_preconditions
    backup
    set_toolset false
    [[ ! -f "$DROPIN_FILE" ]] || mv "$DROPIN_FILE" "${DROPIN_FILE}.disabled"
    systemctl daemon-reload
    ;;
  *) usage; exit 2 ;;
esac
