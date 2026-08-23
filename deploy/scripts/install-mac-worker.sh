#!/usr/bin/env bash
set -euo pipefail

OS_DIR="${OS_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
PROJECT_ALIAS="${PROJECT_ALIAS:-personal-ai-os}"
PROJECT_DIR="${PROJECT_DIR:-$OS_DIR}"
MAC_USER_HOME="${MAC_USER_HOME:-$HOME}"
TARGET_BIN="${TARGET_BIN:-${MAC_USER_HOME}/.local/bin/personal-ai-os-mac-worker}"
CONFIG_FILE="${CONFIG_FILE:-${MAC_USER_HOME}/.config/personal-ai-os/mac-worker.json}"
JOBS_DIR="${JOBS_DIR:-${MAC_USER_HOME}/Library/Application Support/personal-ai-os-mac-worker/jobs}"
CODEX_BINARY="${CODEX_BINARY:-/Applications/ChatGPT.app/Contents/Resources/codex}"
CLAUDE_BINARY="${CLAUDE_BINARY:-/opt/homebrew/bin/claude}"
PYTHON_BINARY="${PYTHON_BINARY:-$(command -v python3)}"
AUTHORIZED_KEYS="${AUTHORIZED_KEYS:-${MAC_USER_HOME}/.ssh/authorized_keys}"

usage() {
  cat <<'USAGE'
Usage:
  deploy/scripts/install-mac-worker.sh plan
  deploy/scripts/install-mac-worker.sh verify
  deploy/scripts/install-mac-worker.sh install --apply
  VPS_PUBLIC_KEY_FILE=/path/to/key.pub deploy/scripts/install-mac-worker.sh authorize-key --apply

The install command creates a user-level worker binary and config. It does not
enable Remote Login, install Tailscale, or alter macOS system settings.
USAGE
}

validate_project() {
  [[ "$PROJECT_ALIAS" =~ ^[a-z0-9][a-z0-9._-]{0,63}$ ]] || {
    echo "Invalid PROJECT_ALIAS" >&2
    exit 2
  }
  [[ -d "$PROJECT_DIR" ]] || { echo "PROJECT_DIR is not a directory: $PROJECT_DIR" >&2; exit 2; }
  PROJECT_DIR="$(cd "$PROJECT_DIR" && pwd -P)"
}

plan() {
  validate_project
  cat <<PLAN
Mac worker install plan

Source checkout:   $OS_DIR
Project alias:     $PROJECT_ALIAS
Project directory: $PROJECT_DIR
Worker binary:     $TARGET_BIN
Worker config:     $CONFIG_FILE
Jobs directory:    $JOBS_DIR
Codex CLI:         $CODEX_BINARY
Claude CLI:        $CLAUDE_BINARY
Python:            $PYTHON_BINARY

Would not:
  enable Remote Login
  install or log in to Tailscale
  modify a router or public firewall
  authorize an SSH key (separate explicit command)
PLAN
}

install_apply() {
  validate_project
  mkdir -p "$(dirname "$TARGET_BIN")" "$(dirname "$CONFIG_FILE")" "$JOBS_DIR"
  chmod 700 "$(dirname "$CONFIG_FILE")" "$JOBS_DIR"

  if [[ -e "$TARGET_BIN" ]]; then
    cp "$TARGET_BIN" "${TARGET_BIN}.bak"
  fi
  if [[ -e "$CONFIG_FILE" ]]; then
    cp "$CONFIG_FILE" "${CONFIG_FILE}.bak"
  fi

  python3 - "$CONFIG_FILE" "$PROJECT_ALIAS" "$PROJECT_DIR" "$JOBS_DIR" "$CODEX_BINARY" "$CLAUDE_BINARY" <<'PY'
import json
from pathlib import Path
import sys

path, alias, project, jobs, codex, claude = sys.argv[1:]
value = {
    "projects": {alias: project},
    "allow_roots": [str(Path(project).parent)],
    "jobs_dir": jobs,
    "codex_binary": codex,
    "claude_binary": claude,
    "max_task_chars": 20000,
}
Path(path).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
Path(path).chmod(0o600)
PY

  python3 - "$TARGET_BIN" "$OS_DIR" "$CONFIG_FILE" "$PYTHON_BINARY" <<'PY'
from pathlib import Path
import shlex
import sys

target, source, config = map(Path, sys.argv[1:4])
script = """#!/bin/sh
set -eu
export PYTHONPATH={source}
export PERSONAL_AI_OS_MAC_WORKER_CONFIG={config}
exec {python} -m services.mac_worker.worker "$@"
""".format(
    source=shlex.quote(str(source)),
    config=shlex.quote(str(config)),
    python=shlex.quote(str(sys.argv[4])),
)
target.write_text(script, encoding="utf-8")
target.chmod(0o700)
PY
  verify
}

authorize_key() {
  [[ -n "${VPS_PUBLIC_KEY_FILE:-}" && -f "$VPS_PUBLIC_KEY_FILE" ]] || {
    echo "VPS_PUBLIC_KEY_FILE must point to the dedicated VPS public key" >&2
    exit 2
  }
  public_key="$(tr -d '\r\n' < "$VPS_PUBLIC_KEY_FILE")"
  [[ "$public_key" =~ ^ssh-ed25519\ [A-Za-z0-9+/=]+([[:space:]].*)?$ ]] || {
    echo "Only an ssh-ed25519 public key is accepted" >&2
    exit 2
  }
  mkdir -p "$(dirname "$AUTHORIZED_KEYS")"
  chmod 700 "$(dirname "$AUTHORIZED_KEYS")"
  touch "$AUTHORIZED_KEYS"
  chmod 600 "$AUTHORIZED_KEYS"
  cp "$AUTHORIZED_KEYS" "${AUTHORIZED_KEYS}.personal-ai-os.bak"
  filtered="$(mktemp)"
  grep -v ' personal-ai-os-mac-worker-vps$' "$AUTHORIZED_KEYS" > "$filtered" || true
  key_type="$(awk '{print $1}' <<<"$public_key")"
  key_body="$(awk '{print $2}' <<<"$public_key")"
  printf 'restrict,command="%s serve-ssh" %s personal-ai-os-mac-worker-vps\n' \
    "$TARGET_BIN" "$key_type $key_body" >> "$filtered"
  mv "$filtered" "$AUTHORIZED_KEYS"
  chmod 600 "$AUTHORIZED_KEYS"
  echo "OK: dedicated forced-command key installed in $AUTHORIZED_KEYS"
}

verify() {
  [[ -x "$TARGET_BIN" ]] || { echo "Worker binary is not installed: $TARGET_BIN" >&2; exit 1; }
  [[ -f "$CONFIG_FILE" ]] || { echo "Worker config is missing: $CONFIG_FILE" >&2; exit 1; }
  PYTHONPATH="$OS_DIR" PERSONAL_AI_OS_MAC_WORKER_CONFIG="$CONFIG_FILE" \
    /usr/bin/python3 - <<'PY'
from services.mac_worker.protocol import WorkerConfig
from services.mac_worker.worker import config_path, doctor

config = WorkerConfig.load(config_path())
result = doctor(config)
assert result["success"], result
print(result)
PY
}

case "${1:-}" in
  plan) plan ;;
  verify) verify ;;
  install)
    [[ "${2:-}" == "--apply" ]] || { echo "Refusing without --apply" >&2; exit 2; }
    install_apply
    ;;
  authorize-key)
    [[ "${2:-}" == "--apply" ]] || { echo "Refusing without --apply" >&2; exit 2; }
    authorize_key
    ;;
  *) usage; exit 2 ;;
esac
