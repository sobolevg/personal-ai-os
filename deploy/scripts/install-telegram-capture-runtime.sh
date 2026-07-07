#!/usr/bin/env bash
set -euo pipefail

OS_DIR="${OS_DIR:-/opt/personal-ai-os}"
HERMES_DIR="${HERMES_DIR:-/usr/local/lib/hermes-agent}"
HERMES_HOME="${HERMES_HOME:-/root/.hermes}"
HERMES_PYTHON="${HERMES_PYTHON:-${HERMES_DIR}/venv/bin/python}"
BACKUP_ROOT="${BACKUP_ROOT:-${HERMES_HOME}/backups}"

TOOL_FILE="${HERMES_DIR}/tools/personal_ai_os_telegram_capture.py"
TOOLSETS_FILE="${HERMES_DIR}/toolsets.py"

usage() {
  cat <<'USAGE'
Usage:
  deploy/scripts/install-telegram-capture-runtime.sh plan
  deploy/scripts/install-telegram-capture-runtime.sh verify
  deploy/scripts/install-telegram-capture-runtime.sh install --apply

Environment overrides:
  OS_DIR=/opt/personal-ai-os
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
  require_file "$OS_DIR"
  require_file "$HERMES_DIR"
  require_file "$HERMES_PYTHON"
  require_file "$TOOLSETS_FILE"
  mkdir -p "${HERMES_DIR}/tools"
}

verify_repo_wrapper() {
  require_preconditions
  PYTHONPATH="$OS_DIR" "$HERMES_PYTHON" - <<'PY'
from hermes.tools.personal_ai_os_telegram_capture import (
    PERSONAL_AI_OS_TELEGRAM_CAPTURE_SCHEMA,
)

assert PERSONAL_AI_OS_TELEGRAM_CAPTURE_SCHEMA["name"] == "personal_ai_os_telegram_capture"
assert "message" in PERSONAL_AI_OS_TELEGRAM_CAPTURE_SCHEMA["parameters"]["properties"]
assert "source_message_id" in PERSONAL_AI_OS_TELEGRAM_CAPTURE_SCHEMA["parameters"]["required"]
print("OK: OS-owned Telegram capture wrapper imports")
PY

  if [[ -f "$TOOL_FILE" ]]; then
    if grep -q "registry.register(" "$TOOL_FILE"; then
      echo "OK: Hermes bridge contains discoverable registry.register call"
    else
      echo "WARN: Hermes bridge lacks direct registry.register call; reinstall before restart"
    fi
  fi
}

write_bridge() {
  cat > "$TOOL_FILE" <<PY
"""Compatibility bridge managed by personal-ai-os.

Source of truth:
  ${OS_DIR}/hermes/tools/personal_ai_os_telegram_capture.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from tools.registry import registry

OS_DIR = Path("${OS_DIR}")
if str(OS_DIR) not in sys.path:
    sys.path.insert(0, str(OS_DIR))

from hermes.tools.personal_ai_os_telegram_capture import (  # noqa: F401
    PERSONAL_AI_OS_TELEGRAM_CAPTURE_SCHEMA,
    personal_ai_os_telegram_capture,
    register_tool,
)

registry.register(
    name="personal_ai_os_telegram_capture",
    toolset="personal_ai_os_capture",
    schema=PERSONAL_AI_OS_TELEGRAM_CAPTURE_SCHEMA,
    handler=lambda args, **kw: personal_ai_os_telegram_capture(
        message=args.get("message", ""),
        source_message_id=args.get("source_message_id", ""),
        execute=bool(args.get("execute", False)),
        event_store_path=args.get("event_store_path"),
        source_platform=args.get("source_platform", "telegram"),
    ),
    emoji="📥",
)
PY
}

ensure_toolset_entry() {
  "$HERMES_PYTHON" - "$TOOLSETS_FILE" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")

changed = False

if '"personal_ai_os_telegram_capture"' not in text:
    needle = '    "web_search", "web_extract",\n'
    insert = (
        '    "web_search", "web_extract",\n'
        '    # Evgenii Personal AI OS capture runtime, loaded from repo bridge.\n'
        '    "personal_ai_os_telegram_capture",\n'
    )
    if needle not in text:
        raise SystemExit("Could not find insertion point in _HERMES_CORE_TOOLS")
    text = text.replace(needle, insert, 1)
    changed = True
    print("OK: added personal_ai_os_telegram_capture to _HERMES_CORE_TOOLS")
else:
    print("OK: toolsets.py already lists personal_ai_os_telegram_capture")

if '"personal_ai_os_capture"' not in text:
    needle = '    # Scenario-specific toolsets\n'
    insert = (
        '    "personal_ai_os_capture": {\n'
        '        "description": "Evgenii Personal AI OS capture routing and event logging",\n'
        '        "tools": ["personal_ai_os_telegram_capture"],\n'
        '        "includes": [],\n'
        '    },\n\n'
        '    # Scenario-specific toolsets\n'
    )
    if needle not in text:
        raise SystemExit("Could not find TOOLSETS insertion point in toolsets.py")
    text = text.replace(needle, insert, 1)
    changed = True
    print("OK: added personal_ai_os_capture toolset")
else:
    print("OK: toolsets.py already defines personal_ai_os_capture toolset")

if changed:
    path.write_text(text, encoding="utf-8")
PY
}

verify_installed_bridge() {
  require_preconditions
  require_file "$TOOL_FILE"
  if ! grep -q "personal_ai_os_telegram_capture" "$TOOL_FILE"; then
    echo "Installed bridge does not reference personal_ai_os_telegram_capture" >&2
    exit 1
  fi
  if ! grep -q '"personal_ai_os_capture"' "$TOOLSETS_FILE"; then
    echo "toolsets.py does not define personal_ai_os_capture" >&2
    exit 1
  fi
  echo "OK: Telegram capture bridge is installed but not platform-enabled"
}

plan() {
  cat <<PLAN
Telegram capture runtime install plan

OS_DIR:          $OS_DIR
HERMES_DIR:      $HERMES_DIR
HERMES_HOME:     $HERMES_HOME
HERMES_PYTHON:   $HERMES_PYTHON
BACKUP_ROOT:     $BACKUP_ROOT

Would manage:
  $TOOL_FILE
  $TOOLSETS_FILE

Would not:
  restart hermes-gateway
  write to Notion
  edit platform_toolsets.telegram
  edit systemd units

Would add:
  Hermes tool personal_ai_os_telegram_capture
  Hermes toolset personal_ai_os_capture

Run:
  deploy/scripts/install-telegram-capture-runtime.sh verify
  deploy/scripts/install-telegram-capture-runtime.sh install --apply
PLAN
}

install_apply() {
  require_preconditions
  verify_repo_wrapper

  local timestamp
  timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
  local backup_dir="${BACKUP_ROOT}/personal-ai-os-telegram-capture-${timestamp}"
  mkdir -p "$backup_dir"

  if [[ -e "$TOOL_FILE" ]]; then
    cp "$TOOL_FILE" "$backup_dir/personal_ai_os_telegram_capture.py"
  else
    touch "$backup_dir/personal_ai_os_telegram_capture.py.absent"
  fi
  cp "$TOOLSETS_FILE" "$backup_dir/toolsets.py"

  write_bridge
  ensure_toolset_entry
  verify_installed_bridge

  cat <<DONE
Installed Personal AI OS Telegram capture bridge.

Backup directory:
  $backup_dir

No Hermes restart was performed.
Telegram platform config was not changed.

Review, then restart manually only when approved:
  systemctl restart hermes-gateway
  journalctl -u hermes-gateway -n 100 --no-pager

Rollback:
  cp "$backup_dir/toolsets.py" "$TOOLSETS_FILE"
  if [[ -f "$backup_dir/personal_ai_os_telegram_capture.py" ]]; then
    cp "$backup_dir/personal_ai_os_telegram_capture.py" "$TOOL_FILE"
  else
    rm -f "$TOOL_FILE"
  fi
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
      verify_repo_wrapper
      ;;
    install)
      if [[ "${2:-}" != "--apply" ]]; then
        echo "Refusing install without explicit --apply." >&2
        usage >&2
        exit 2
      fi
      install_apply
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
