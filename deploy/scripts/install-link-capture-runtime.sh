#!/usr/bin/env bash
set -euo pipefail

OS_DIR="${OS_DIR:-/opt/personal-ai-os}"
HERMES_DIR="${HERMES_DIR:-/usr/local/lib/hermes-agent}"
HERMES_HOME="${HERMES_HOME:-/root/.hermes}"
HERMES_PYTHON="${HERMES_PYTHON:-${HERMES_DIR}/venv/bin/python}"
BACKUP_ROOT="${BACKUP_ROOT:-${HERMES_HOME}/backups}"
TOOL_FILE="${HERMES_DIR}/tools/personal_ai_os_link_capture.py"
TOOLSETS_FILE="${HERMES_DIR}/toolsets.py"

usage() {
  echo "Usage: $0 plan|verify|install --apply"
}

require_file() {
  [[ -e "$1" ]] || { echo "Missing required path: $1" >&2; exit 1; }
}

require_preconditions() {
  require_file "$OS_DIR"
  require_file "$HERMES_DIR"
  require_file "$HERMES_PYTHON"
  require_file "$TOOLSETS_FILE"
}

verify_repo_wrapper() {
  require_preconditions
  PYTHONPATH="$OS_DIR:$HERMES_DIR" "$HERMES_PYTHON" - <<'PY'
from hermes.tools.personal_ai_os_link_capture import (
    PERSONAL_AI_OS_LINK_PREPARE_SCHEMA,
    PERSONAL_AI_OS_LINK_SAVE_SCHEMA,
)
assert PERSONAL_AI_OS_LINK_PREPARE_SCHEMA["name"] == "personal_ai_os_link_prepare"
assert PERSONAL_AI_OS_LINK_SAVE_SCHEMA["name"] == "personal_ai_os_link_save"
assert "source_url" not in PERSONAL_AI_OS_LINK_SAVE_SCHEMA["parameters"]["properties"]
print("OK: OS-owned link capture wrapper imports")
PY
}

write_bridge() {
  cat > "$TOOL_FILE" <<PY
"""Compatibility bridge managed by personal-ai-os.

Source of truth:
  ${OS_DIR}/hermes/tools/personal_ai_os_link_capture.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from tools.registry import registry

OS_DIR = Path("${OS_DIR}")
if str(OS_DIR) not in sys.path:
    sys.path.insert(0, str(OS_DIR))

from hermes.tools.personal_ai_os_link_capture import (
    PERSONAL_AI_OS_LINK_PREPARE_SCHEMA,
    PERSONAL_AI_OS_LINK_SAVE_SCHEMA,
    personal_ai_os_link_prepare,
    personal_ai_os_link_save,
)

registry.register(
    name="personal_ai_os_link_prepare",
    toolset="personal_ai_os_link_capture",
    schema=PERSONAL_AI_OS_LINK_PREPARE_SCHEMA,
    handler=lambda args, **kw: personal_ai_os_link_prepare(
        message=args.get("message", ""),
        source_message_id=args.get("source_message_id", ""),
        source_platform=args.get("source_platform", "telegram"),
    ),
    emoji="🔗",
    max_result_size_chars=50_000,
)

registry.register(
    name="personal_ai_os_link_save",
    toolset="personal_ai_os_link_capture",
    schema=PERSONAL_AI_OS_LINK_SAVE_SCHEMA,
    handler=lambda args, **kw: personal_ai_os_link_save(
        capture_id=args.get("capture_id", ""),
        title=args.get("title", ""),
        summary=args.get("summary", ""),
        topics=args.get("topics", []),
        content_type=args.get("content_type", ""),
        action=args.get("action", "none"),
        actionability=args.get("actionability", "low"),
        why_relevant=args.get("why_relevant", ""),
        suggested_area=args.get("suggested_area"),
        suggested_project=args.get("suggested_project"),
        reusable_knowledge=bool(args.get("reusable_knowledge", False)),
    ),
    emoji="🗂️",
)
PY
}

ensure_toolset_entry() {
  "$HERMES_PYTHON" - "$TOOLSETS_FILE" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
if '"personal_ai_os_link_capture"' not in text:
    needle = '    # Scenario-specific toolsets\n'
    insert = (
        '    "personal_ai_os_link_capture": {\n'
        '        "description": "Instagram to PLAUD to Zettelkasten capture",\n'
        '        "tools": ["personal_ai_os_link_prepare", "personal_ai_os_link_save"],\n'
        '        "includes": [],\n'
        '    },\n\n'
        + needle
    )
    if needle not in text:
        raise SystemExit("Could not find TOOLSETS insertion point")
    path.write_text(text.replace(needle, insert, 1), encoding="utf-8")
print("OK: link capture toolset is present")
PY
}

verify_installed() {
  require_file "$TOOL_FILE"
  grep -q 'registry.register(' "$TOOL_FILE"
  grep -q '"personal_ai_os_link_capture"' "$TOOLSETS_FILE"
  echo "OK: link capture bridge is installed but not platform-enabled"
}

plan() {
  cat <<PLAN
Link capture runtime install plan

Would manage:
  $TOOL_FILE
  $TOOLSETS_FILE

Would not:
  restart hermes-gateway
  enable Telegram access
  enable Notion writes
  edit secrets
PLAN
}

install_apply() {
  verify_repo_wrapper
  timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
  backup_dir="${BACKUP_ROOT}/personal-ai-os-link-capture-${timestamp}"
  mkdir -p "$backup_dir"
  [[ ! -e "$TOOL_FILE" ]] || cp "$TOOL_FILE" "$backup_dir/"
  cp "$TOOLSETS_FILE" "$backup_dir/toolsets.py"
  write_bridge
  ensure_toolset_entry
  verify_installed
  echo "Backup directory: $backup_dir"
  echo "No Hermes restart was performed."
}

case "${1:-}" in
  plan) plan ;;
  verify) verify_repo_wrapper ;;
  install)
    [[ "${2:-}" == "--apply" ]] || { echo "Refusing without --apply" >&2; exit 2; }
    install_apply
    ;;
  *) usage; exit 2 ;;
esac
