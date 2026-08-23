#!/usr/bin/env bash
set -euo pipefail

OS_DIR="${OS_DIR:-/opt/personal-ai-os}"
HERMES_DIR="${HERMES_DIR:-/usr/local/lib/hermes-agent}"
HERMES_HOME="${HERMES_HOME:-/root/.hermes}"
HERMES_PYTHON="${HERMES_PYTHON:-${HERMES_DIR}/venv/bin/python}"
BACKUP_ROOT="${BACKUP_ROOT:-${HERMES_HOME}/backups}"
TOOL_FILE="${HERMES_DIR}/tools/mac_worker.py"
TOOLSETS_FILE="${HERMES_DIR}/toolsets.py"

usage() { echo "Usage: $0 plan|verify|install --apply"; }
require_file() { [[ -e "$1" ]] || { echo "Missing: $1" >&2; exit 1; }; }

verify_repo() {
  require_file "$OS_DIR"
  require_file "$HERMES_DIR"
  require_file "$HERMES_PYTHON"
  require_file "$TOOLSETS_FILE"
  PYTHONPATH="$OS_DIR:$HERMES_DIR" "$HERMES_PYTHON" - <<'PY'
from hermes.tools.mac_worker import MAC_WORKER_RUN_SCHEMA, MAC_WORKER_STATUS_SCHEMA
assert MAC_WORKER_RUN_SCHEMA["name"] == "mac_worker_run"
assert MAC_WORKER_STATUS_SCHEMA["name"] == "mac_worker_status"
assert "path" not in MAC_WORKER_RUN_SCHEMA["parameters"]["properties"]
print("OK: OS-owned Mac worker wrapper imports")
PY
}

write_bridge() {
  cat > "$TOOL_FILE" <<PY
"""Compatibility bridge managed by personal-ai-os."""
from __future__ import annotations
import sys
from pathlib import Path
from tools.registry import registry

OS_DIR = Path("${OS_DIR}")
if str(OS_DIR) not in sys.path:
    sys.path.insert(0, str(OS_DIR))

from hermes.tools.mac_worker import (
    MAC_WORKER_DOCTOR_SCHEMA, MAC_WORKER_RUN_SCHEMA, MAC_WORKER_STATUS_SCHEMA,
    MAC_WORKER_STOP_SCHEMA, mac_worker_doctor, mac_worker_run, mac_worker_status,
    mac_worker_stop,
)

registry.register(name="mac_worker_run", toolset="mac_worker", schema=MAC_WORKER_RUN_SCHEMA,
    handler=lambda args, **kw: mac_worker_run(project=args.get("project", ""), task=args.get("task", ""),
        agent=args.get("agent", "codex"), allow_commit=bool(args.get("allow_commit", False)),
        allow_push=bool(args.get("allow_push", False))), emoji="💻", max_result_size_chars=15000)
registry.register(name="mac_worker_status", toolset="mac_worker", schema=MAC_WORKER_STATUS_SCHEMA,
    handler=lambda args, **kw: mac_worker_status(job_id=args.get("job_id", ""),
        tail_chars=args.get("tail_chars", 4000)), emoji="📟", max_result_size_chars=15000)
registry.register(name="mac_worker_stop", toolset="mac_worker", schema=MAC_WORKER_STOP_SCHEMA,
    handler=lambda args, **kw: mac_worker_stop(job_id=args.get("job_id", "")), emoji="🛑")
registry.register(name="mac_worker_doctor", toolset="mac_worker", schema=MAC_WORKER_DOCTOR_SCHEMA,
    handler=lambda args, **kw: mac_worker_doctor(), emoji="🩺")
PY
}

ensure_toolset() {
  "$HERMES_PYTHON" - "$TOOLSETS_FILE" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
if '"mac_worker"' not in text:
    needle = "    # Scenario-specific toolsets\n"
    insert = (
        '    "mac_worker": {\n'
        '        "description": "Restricted coding delegation to the user Mac",\n'
        '        "tools": ["mac_worker_run", "mac_worker_status", "mac_worker_stop", "mac_worker_doctor"],\n'
        '        "includes": [],\n'
        '    },\n\n'
        + needle
    )
    if needle not in text:
        raise SystemExit("Could not find toolset insertion point")
    path.write_text(text.replace(needle, insert, 1), encoding="utf-8")
print("OK: mac_worker toolset is present")
PY
}

plan() {
  cat <<PLAN
Mac worker Hermes runtime plan

Would manage:
  $TOOL_FILE
  $TOOLSETS_FILE

Would not enable the toolset for Telegram or restart Hermes.
PLAN
}

install_apply() {
  verify_repo
  timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
  backup_dir="${BACKUP_ROOT}/personal-ai-os-mac-worker-${timestamp}"
  mkdir -p "$backup_dir"
  [[ ! -e "$TOOL_FILE" ]] || cp "$TOOL_FILE" "$backup_dir/"
  cp "$TOOLSETS_FILE" "$backup_dir/toolsets.py"
  write_bridge
  ensure_toolset
  grep -q 'registry.register' "$TOOL_FILE"
  echo "Backup directory: $backup_dir"
  echo "No Hermes restart was performed."
}

case "${1:-}" in
  plan) plan ;;
  verify) verify_repo ;;
  install)
    [[ "${2:-}" == "--apply" ]] || { echo "Refusing without --apply" >&2; exit 2; }
    install_apply
    ;;
  *) usage; exit 2 ;;
esac
