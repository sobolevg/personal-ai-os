#!/usr/bin/env bash
set -euo pipefail

HERMES_DIR="${HERMES_DIR:-/usr/local/lib/hermes-agent}"
HERMES_HOME="${HERMES_HOME:-/root/.hermes}"
HERMES_PYTHON="${HERMES_PYTHON:-${HERMES_DIR}/venv/bin/python}"
BACKUP_ROOT="${BACKUP_ROOT:-${HERMES_HOME}/backups}"

CONFIG_FILE="${HERMES_HOME}/config.yaml"
TOOLSETS_FILE="${HERMES_DIR}/toolsets.py"
TOOLSET_NAME="personal_ai_os_capture"

usage() {
  cat <<'USAGE'
Usage:
  deploy/scripts/enable-telegram-capture-runtime.sh plan
  deploy/scripts/enable-telegram-capture-runtime.sh verify
  deploy/scripts/enable-telegram-capture-runtime.sh enable --apply
  deploy/scripts/enable-telegram-capture-runtime.sh disable --apply

Environment overrides:
  HERMES_DIR=/usr/local/lib/hermes-agent
  HERMES_HOME=/root/.hermes
  HERMES_PYTHON=/usr/local/lib/hermes-agent/venv/bin/python
  BACKUP_ROOT=/root/.hermes/backups
USAGE
}

require_file() {
  local path="$1"
  if [[ ! -e "$path" ]]; then
    echo "Missing required path: $path" >&2
    exit 1
  fi
}

require_preconditions() {
  require_file "$HERMES_DIR"
  require_file "$HERMES_PYTHON"
  require_file "$CONFIG_FILE"
  require_file "$TOOLSETS_FILE"
  if ! grep -q "\"${TOOLSET_NAME}\"" "$TOOLSETS_FILE"; then
    echo "Missing ${TOOLSET_NAME} in ${TOOLSETS_FILE}; install the bridge first." >&2
    exit 1
  fi
}

plan() {
  cat <<PLAN
Telegram capture enablement plan

HERMES_DIR:      $HERMES_DIR
HERMES_HOME:     $HERMES_HOME
HERMES_PYTHON:   $HERMES_PYTHON
BACKUP_ROOT:     $BACKUP_ROOT

Would manage:
  $CONFIG_FILE

Would add/remove:
  platform_toolsets.telegram += ${TOOLSET_NAME}

Would not:
  restart hermes-gateway
  write to Notion
  enable PERSONAL_AI_OS_CAPTURE_EXECUTE_ENABLED
  edit systemd units

Run:
  deploy/scripts/enable-telegram-capture-runtime.sh verify
  deploy/scripts/enable-telegram-capture-runtime.sh enable --apply
PLAN
}

verify() {
  require_preconditions
  HERMES_HOME="$HERMES_HOME" PYTHONPATH="$HERMES_DIR:${PYTHONPATH:-}" "$HERMES_PYTHON" - "$TOOLSET_NAME" <<'PY'
import sys
from hermes_cli.tools_config import load_config, _get_platform_tools

toolset_name = sys.argv[1]
config = load_config()
telegram = config.get("platform_toolsets", {}).get("telegram", [])
effective = _get_platform_tools(config, "telegram")
print(f"telegram_toolsets={telegram}")
print(f"{toolset_name}_enabled={toolset_name in telegram}")
print(f"{toolset_name}_effective={toolset_name in effective}")
PY
}

backup_config() {
  local timestamp
  timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
  local backup_dir="${BACKUP_ROOT}/personal-ai-os-telegram-capture-enable-${timestamp}"
  mkdir -p "$backup_dir"
  cp "$CONFIG_FILE" "$backup_dir/config.yaml"
  echo "$backup_dir"
}

set_enabled() {
  local desired="$1"
  require_preconditions

  local backup_dir
  backup_dir="$(backup_config)"

  HERMES_HOME="$HERMES_HOME" PYTHONPATH="$HERMES_DIR:${PYTHONPATH:-}" "$HERMES_PYTHON" - "$TOOLSET_NAME" "$desired" <<'PY'
import sys
from hermes_cli.tools_config import load_config, save_config, _get_platform_tools

toolset_name = sys.argv[1]
desired = sys.argv[2] == "true"

config = load_config()
platform_toolsets = config.setdefault("platform_toolsets", {})
telegram = platform_toolsets.setdefault("telegram", [])
if not isinstance(telegram, list):
    telegram = []

items = [str(item) for item in telegram]
if desired:
    items = sorted(set(items) | {toolset_name})
else:
    items = [item for item in items if item != toolset_name]

platform_toolsets["telegram"] = items
save_config(config)

effective = _get_platform_tools(config, "telegram")
print(f"telegram_toolsets={items}")
print(f"{toolset_name}_effective={toolset_name in effective}")
PY

  cat <<DONE
Updated Telegram capture toolset config.

Backup directory:
  $backup_dir

No Hermes restart was performed.
PERSONAL_AI_OS_CAPTURE_EXECUTE_ENABLED was not changed.

Review, then restart manually only when approved:
  systemctl restart hermes-gateway
  journalctl -u hermes-gateway -n 100 --no-pager

Rollback:
  cp "$backup_dir/config.yaml" "$CONFIG_FILE"
  systemctl restart hermes-gateway
DONE
}

main() {
  local command="${1:-}"
  case "$command" in
    plan)
      plan
      ;;
    verify)
      verify
      ;;
    enable)
      if [[ "${2:-}" != "--apply" ]]; then
        echo "Refusing enable without explicit --apply." >&2
        usage >&2
        exit 2
      fi
      set_enabled true
      ;;
    disable)
      if [[ "${2:-}" != "--apply" ]]; then
        echo "Refusing disable without explicit --apply." >&2
        usage >&2
        exit 2
      fi
      set_enabled false
      ;;
    -h|--help|help|"")
      usage
      ;;
    *)
      echo "Unknown command: $command" >&2
      usage >&2
      exit 2
      ;;
  esac
}

main "$@"
