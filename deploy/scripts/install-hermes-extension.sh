#!/usr/bin/env bash
set -euo pipefail

OS_DIR="${OS_DIR:-/opt/personal-ai-os}"
HERMES_DIR="${HERMES_DIR:-/usr/local/lib/hermes-agent}"
HERMES_HOME="${HERMES_HOME:-/root/.hermes}"
HERMES_PYTHON="${HERMES_PYTHON:-${HERMES_DIR}/venv/bin/python}"
BACKUP_ROOT="${BACKUP_ROOT:-${HERMES_HOME}/backups}"

TOOL_FILE="${HERMES_DIR}/tools/notion_task_create.py"
LEGACY_TOOL_FILE="${HERMES_DIR}/tools/notion_task_tool.py"
TOOLSETS_FILE="${HERMES_DIR}/toolsets.py"

usage() {
  cat <<'USAGE'
Usage:
  deploy/scripts/install-hermes-extension.sh plan
  deploy/scripts/install-hermes-extension.sh verify
  deploy/scripts/install-hermes-extension.sh install --apply

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
}

verify_wrapper() {
  require_preconditions
  PYTHONPATH="$OS_DIR" "$HERMES_PYTHON" - <<'PY'
from hermes.tools.notion_task_create import NOTION_TASK_CREATE_SCHEMA

assert NOTION_TASK_CREATE_SCHEMA["name"] == "notion_task_create"
assert "title" in NOTION_TASK_CREATE_SCHEMA["parameters"]["properties"]
print("OK: OS-owned Hermes wrapper imports and exposes notion_task_create")
PY

  if [[ -f "$TOOL_FILE" ]]; then
    if grep -q "registry.register(" "$TOOL_FILE"; then
      echo "OK: Hermes canonical bridge contains discoverable registry.register call"
    else
      echo "WARN: Hermes canonical bridge lacks direct registry.register call; reinstall bridge before restart"
    fi
  fi
}

write_bridge() {
  cat > "$TOOL_FILE" <<PY
"""Compatibility bridge managed by personal-ai-os.

Source of truth:
  ${OS_DIR}/hermes/tools/notion_task_create.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from tools.registry import registry

OS_DIR = Path("${OS_DIR}")
if str(OS_DIR) not in sys.path:
    sys.path.insert(0, str(OS_DIR))

from hermes.tools.notion_task_create import (  # noqa: F401
    NOTION_TASK_CREATE_SCHEMA,
    load_notion_token,
    notion_task_create,
    post_notion_page,
    register_tool,
)

registry.register(
    name="notion_task_create",
    toolset="notion_task",
    schema=NOTION_TASK_CREATE_SCHEMA,
    handler=lambda args, **kw: notion_task_create(
        title=args.get("title", ""),
        bucket=args.get("bucket", "Потом"),
        comment=args.get("comment"),
    ),
    emoji="📝",
)
PY

  cat > "$LEGACY_TOOL_FILE" <<PY
"""Legacy compatibility bridge managed by personal-ai-os.

The canonical Hermes module is tools.notion_task_create.
"""

from __future__ import annotations

from tools.notion_task_create import (  # noqa: F401
    NOTION_TASK_CREATE_SCHEMA,
    load_notion_token,
    notion_task_create,
    post_notion_page,
    register_tool,
)
PY
}

ensure_toolset_entry() {
  "$HERMES_PYTHON" - "$TOOLSETS_FILE" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
if '"notion_task_create"' in text:
    print("OK: toolsets.py already lists notion_task_create")
    raise SystemExit(0)

needle = '    "web_search", "web_extract",\n'
insert = (
    '    "web_search", "web_extract",\n'
    '    # Evgenii personal Notion task capture, loaded from personal-ai-os bridge.\n'
    '    "notion_task_create",\n'
)
if needle not in text:
    raise SystemExit("Could not find insertion point in toolsets.py")

path.write_text(text.replace(needle, insert, 1), encoding="utf-8")
print("OK: added notion_task_create to toolsets.py")
PY
}

plan() {
  cat <<PLAN
Hermes extension install plan

OS_DIR:          $OS_DIR
HERMES_DIR:      $HERMES_DIR
HERMES_HOME:     $HERMES_HOME
HERMES_PYTHON:   $HERMES_PYTHON
BACKUP_ROOT:     $BACKUP_ROOT

Would manage:
  $TOOL_FILE
  $LEGACY_TOOL_FILE
  $TOOLSETS_FILE

Would not:
  restart hermes-gateway
  write to Notion
  edit secrets
  edit systemd units

Run:
  deploy/scripts/install-hermes-extension.sh verify
  deploy/scripts/install-hermes-extension.sh install --apply
PLAN
}

install_apply() {
  require_preconditions
  verify_wrapper

  local timestamp
  timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
  local backup_dir="${BACKUP_ROOT}/personal-ai-os-${timestamp}"
  mkdir -p "$backup_dir"

  if [[ -e "$TOOL_FILE" ]]; then
    cp "$TOOL_FILE" "$backup_dir/notion_task_create.py"
  else
    touch "$backup_dir/notion_task_create.py.absent"
  fi
  if [[ -e "$LEGACY_TOOL_FILE" ]]; then
    cp "$LEGACY_TOOL_FILE" "$backup_dir/notion_task_tool.py"
  else
    touch "$backup_dir/notion_task_tool.py.absent"
  fi
  cp "$TOOLSETS_FILE" "$backup_dir/toolsets.py"

  write_bridge
  ensure_toolset_entry
  verify_wrapper

  cat <<DONE
Installed personal-ai-os Hermes bridge.

Backup directory:
  $backup_dir

No Hermes restart was performed.

Review, then restart manually if approved:
  systemctl restart hermes-gateway
  journalctl -u hermes-gateway -n 100 --no-pager

Rollback:
  cp "$backup_dir/toolsets.py" "$TOOLSETS_FILE"
  if [[ -f "$backup_dir/notion_task_create.py" ]]; then
    cp "$backup_dir/notion_task_create.py" "$TOOL_FILE"
  else
    rm -f "$TOOL_FILE"
  fi
  if [[ -f "$backup_dir/notion_task_tool.py" ]]; then
    cp "$backup_dir/notion_task_tool.py" "$LEGACY_TOOL_FILE"
  else
    rm -f "$LEGACY_TOOL_FILE"
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
      verify_wrapper
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
