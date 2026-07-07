#!/usr/bin/env bash
set -euo pipefail

HERMES_HOME="${HERMES_HOME:-/root/.hermes}"
EVENT_LOG_PATH="${PERSONAL_AI_OS_EVENT_LOG_PATH:-${HERMES_HOME}/personal-ai-os/events/events.jsonl}"
BACKUP_ROOT="${BACKUP_ROOT:-${HERMES_HOME}/backups}"
MAX_BYTES="${MAX_BYTES:-10485760}"

usage() {
  cat <<'USAGE'
Usage:
  deploy/scripts/manage-event-log.sh plan
  deploy/scripts/manage-event-log.sh verify
  deploy/scripts/manage-event-log.sh install --apply
  deploy/scripts/manage-event-log.sh backup --apply
  deploy/scripts/manage-event-log.sh rotate --apply

Environment overrides:
  HERMES_HOME=/root/.hermes
  PERSONAL_AI_OS_EVENT_LOG_PATH=/root/.hermes/personal-ai-os/events/events.jsonl
  BACKUP_ROOT=/root/.hermes/backups
  MAX_BYTES=10485760
USAGE
}

event_dir() {
  dirname "$EVENT_LOG_PATH"
}

event_size() {
  if [[ -f "$EVENT_LOG_PATH" ]]; then
    wc -c < "$EVENT_LOG_PATH" | tr -d ' '
  else
    echo 0
  fi
}

backup_path() {
  local timestamp
  timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
  echo "${BACKUP_ROOT}/personal-ai-os-events-${timestamp}.jsonl"
}

plan() {
  cat <<PLAN
Personal AI OS event log plan

HERMES_HOME:     $HERMES_HOME
EVENT_LOG_PATH: $EVENT_LOG_PATH
BACKUP_ROOT:    $BACKUP_ROOT
MAX_BYTES:      $MAX_BYTES

Would manage:
  $(event_dir)
  $EVENT_LOG_PATH

Would not:
  restart hermes-gateway
  write to Notion
  edit secrets
  delete event history without backup
PLAN
}

verify() {
  if [[ -e "$EVENT_LOG_PATH" && ! -f "$EVENT_LOG_PATH" ]]; then
    echo "Event log path exists but is not a file: $EVENT_LOG_PATH" >&2
    exit 1
  fi

  if [[ -f "$EVENT_LOG_PATH" ]]; then
    python3 - "$EVENT_LOG_PATH" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
    if line.strip():
        json.loads(line)
print(f"OK: event log is valid JSONL ({path})")
PY
  else
    echo "OK: event log does not exist yet"
  fi
}

install_apply() {
  mkdir -p "$(event_dir)"
  touch "$EVENT_LOG_PATH"
  chmod 700 "$(event_dir)"
  chmod 600 "$EVENT_LOG_PATH"
  verify
  echo "OK: event log path is ready: $EVENT_LOG_PATH"
}

backup_apply() {
  mkdir -p "$BACKUP_ROOT"
  if [[ ! -f "$EVENT_LOG_PATH" ]]; then
    echo "No event log to back up: $EVENT_LOG_PATH"
    return
  fi

  local target
  target="$(backup_path)"
  cp "$EVENT_LOG_PATH" "$target"
  chmod 600 "$target"
  echo "OK: backed up event log to $target"
}

rotate_apply() {
  local size
  size="$(event_size)"
  if (( size <= MAX_BYTES )); then
    echo "OK: event log size ${size} bytes is within MAX_BYTES=${MAX_BYTES}"
    return
  fi

  backup_apply
  : > "$EVENT_LOG_PATH"
  chmod 600 "$EVENT_LOG_PATH"
  echo "OK: rotated event log after backup"
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
    install)
      if [[ "${2:-}" != "--apply" ]]; then
        echo "Refusing install without explicit --apply." >&2
        usage >&2
        exit 2
      fi
      install_apply
      ;;
    backup)
      if [[ "${2:-}" != "--apply" ]]; then
        echo "Refusing backup without explicit --apply." >&2
        usage >&2
        exit 2
      fi
      backup_apply
      ;;
    rotate)
      if [[ "${2:-}" != "--apply" ]]; then
        echo "Refusing rotate without explicit --apply." >&2
        usage >&2
        exit 2
      fi
      rotate_apply
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
