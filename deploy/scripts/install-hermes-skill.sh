#!/usr/bin/env bash
set -euo pipefail

OS_DIR="${OS_DIR:-/opt/personal-ai-os}"
HERMES_HOME="${HERMES_HOME:-/root/.hermes}"
BACKUP_ROOT="${BACKUP_ROOT:-${HERMES_HOME}/backups}"

SKILL_NAME="${SKILL_NAME:-notion-tasks}"
SKILL_GROUP="${SKILL_GROUP:-productivity}"
SOURCE_DIR="${SOURCE_DIR:-${OS_DIR}/hermes/skills/${SKILL_GROUP}/${SKILL_NAME}}"
TARGET_DIR="${TARGET_DIR:-${HERMES_HOME}/skills/${SKILL_GROUP}/${SKILL_NAME}}"

usage() {
  cat <<'USAGE'
Usage:
  deploy/scripts/install-hermes-skill.sh plan
  deploy/scripts/install-hermes-skill.sh verify
  deploy/scripts/install-hermes-skill.sh install --apply

Environment overrides:
  OS_DIR=/opt/personal-ai-os
  HERMES_HOME=/root/.hermes
  BACKUP_ROOT=/root/.hermes/backups
  SKILL_GROUP=productivity
  SKILL_NAME=notion-tasks
  SOURCE_DIR=/opt/personal-ai-os/hermes/skills/productivity/notion-tasks
  TARGET_DIR=/root/.hermes/skills/productivity/notion-tasks
USAGE
}

require_dir() {
  local path="$1"
  if [[ ! -d "$path" ]]; then
    echo "Missing required directory: $path" >&2
    exit 1
  fi
}

verify_source() {
  require_dir "$SOURCE_DIR"
  if [[ ! -f "$SOURCE_DIR/SKILL.md" ]]; then
    echo "Missing required file: $SOURCE_DIR/SKILL.md" >&2
    exit 1
  fi
  if ! grep -q "notion_task_create" "$SOURCE_DIR/SKILL.md"; then
    echo "Skill does not mention notion_task_create: $SOURCE_DIR/SKILL.md" >&2
    exit 1
  fi
  echo "OK: source skill routes task capture to notion_task_create"
}

verify_installed() {
  require_dir "$TARGET_DIR"
  if [[ ! -f "$TARGET_DIR/SKILL.md" ]]; then
    echo "Missing installed skill file: $TARGET_DIR/SKILL.md" >&2
    exit 1
  fi
  if ! grep -q "notion_task_create" "$TARGET_DIR/SKILL.md"; then
    echo "Installed skill does not mention notion_task_create: $TARGET_DIR/SKILL.md" >&2
    exit 1
  fi
  echo "OK: installed skill routes task capture to notion_task_create"
}

plan() {
  cat <<PLAN
Hermes skill install plan

OS_DIR:       $OS_DIR
HERMES_HOME:  $HERMES_HOME
BACKUP_ROOT:  $BACKUP_ROOT
SKILL_GROUP:  $SKILL_GROUP
SKILL_NAME:   $SKILL_NAME

Would copy:
  $SOURCE_DIR
to:
  $TARGET_DIR

Would not:
  restart hermes-gateway
  write to Notion
  edit secrets
  edit systemd units

Run:
  deploy/scripts/install-hermes-skill.sh verify
  deploy/scripts/install-hermes-skill.sh install --apply
PLAN
}

install_apply() {
  verify_source

  local timestamp
  timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
  local backup_dir="${BACKUP_ROOT}/personal-ai-os-skill-${SKILL_NAME}-${timestamp}"
  mkdir -p "$backup_dir"

  if [[ -e "$TARGET_DIR" ]]; then
    cp -R "$TARGET_DIR" "$backup_dir/${SKILL_NAME}"
  else
    touch "$backup_dir/${SKILL_NAME}.absent"
  fi

  mkdir -p "$(dirname "$TARGET_DIR")"
  rm -rf "$TARGET_DIR"
  cp -R "$SOURCE_DIR" "$TARGET_DIR"
  verify_installed

  cat <<DONE
Installed personal-ai-os Hermes skill.

Backup directory:
  $backup_dir

No Hermes restart was performed.

Review, then restart manually if approved:
  systemctl restart hermes-gateway
  journalctl -u hermes-gateway -n 100 --no-pager

Rollback:
  if [[ -d "$backup_dir/${SKILL_NAME}" ]]; then
    rm -rf "$TARGET_DIR"
    cp -R "$backup_dir/${SKILL_NAME}" "$TARGET_DIR"
  else
    rm -rf "$TARGET_DIR"
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
      verify_source
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
