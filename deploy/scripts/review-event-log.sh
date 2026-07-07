#!/usr/bin/env bash
set -euo pipefail

OS_DIR="${OS_DIR:-/opt/personal-ai-os}"
HERMES_HOME="${HERMES_HOME:-/root/.hermes}"
EVENT_LOG_PATH="${PERSONAL_AI_OS_EVENT_LOG_PATH:-${HERMES_HOME}/personal-ai-os/events/events.jsonl}"

usage() {
  cat <<'USAGE'
Usage:
  deploy/scripts/review-event-log.sh summary
  deploy/scripts/review-event-log.sh summary --json
  deploy/scripts/review-event-log.sh pending
  deploy/scripts/review-event-log.sh pending --json
  deploy/scripts/review-event-log.sh pending --limit 20

Environment overrides:
  OS_DIR=/opt/personal-ai-os
  HERMES_HOME=/root/.hermes
  PERSONAL_AI_OS_EVENT_LOG_PATH=/root/.hermes/personal-ai-os/events/events.jsonl
USAGE
}

main() {
  local command="${1:-}"
  case "$command" in
    summary|pending)
      PYTHONPATH="$OS_DIR" python3 -m integrations.events.event_review \
        "$command" \
        --path "$EVENT_LOG_PATH" \
        "${@:2}"
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
