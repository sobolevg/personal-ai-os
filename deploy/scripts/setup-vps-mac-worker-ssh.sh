#!/usr/bin/env bash
set -euo pipefail

SSH_DIR="${SSH_DIR:-/root/.ssh}"
SSH_CONFIG="${SSH_CONFIG:-${SSH_DIR}/config}"
IDENTITY_FILE="${IDENTITY_FILE:-${SSH_DIR}/personal_ai_os_mac_worker_ed25519}"
KNOWN_HOSTS_FILE="${KNOWN_HOSTS_FILE:-${SSH_DIR}/personal_ai_os_mac_worker_known_hosts}"
HOST_ALIAS="${HOST_ALIAS:-personal-ai-os-mac-worker}"
MAC_WORKER_HOSTNAME="${MAC_WORKER_HOSTNAME:-}"
MAC_WORKER_USER="${MAC_WORKER_USER:-}"

usage() {
  cat <<'USAGE'
Usage on the VPS:
  MAC_WORKER_HOSTNAME=<100.64/10 IP or *.ts.net> MAC_WORKER_USER=<mac-user> \
    deploy/scripts/setup-vps-mac-worker-ssh.sh plan
  ... setup-key --apply
  ... print-public-key
  MAC_WORKER_EXPECTED_HOST_FINGERPRINT=SHA256:... ... trust-host --apply
  ... verify
USAGE
}

validate_target() {
  [[ "$MAC_WORKER_USER" =~ ^[a-z_][a-z0-9_-]{0,31}$ ]] || {
    echo "MAC_WORKER_USER is invalid" >&2
    exit 2
  }
  python3 - "$MAC_WORKER_HOSTNAME" <<'PY'
import ipaddress
import sys

value = sys.argv[1]
if value.endswith(".ts.net") and len(value) <= 253:
    raise SystemExit(0)
try:
    address = ipaddress.ip_address(value)
except ValueError:
    raise SystemExit("MAC_WORKER_HOSTNAME must be a Tailscale IP or *.ts.net name")
if address.version != 4 or address not in ipaddress.ip_network("100.64.0.0/10"):
    raise SystemExit("MAC_WORKER_HOSTNAME is not in Tailscale CGNAT space")
PY
}

plan() {
  validate_target
  cat <<PLAN
VPS SSH setup plan

Host alias:       $HOST_ALIAS
Mac target:       $MAC_WORKER_HOSTNAME
Mac user:         $MAC_WORKER_USER
Dedicated key:    $IDENTITY_FILE
Dedicated trust:  $KNOWN_HOSTS_FILE

The host entry forces public-key-only, no TTY, no forwarding, and strict host
key checking. The Mac authorized_keys entry separately forces the worker RPC.
PLAN
}

write_config() {
  mkdir -p "$SSH_DIR"
  chmod 700 "$SSH_DIR"
  touch "$SSH_CONFIG"
  chmod 600 "$SSH_CONFIG"
  cp "$SSH_CONFIG" "${SSH_CONFIG}.personal-ai-os.bak"
  python3 - "$SSH_CONFIG" "$HOST_ALIAS" "$MAC_WORKER_HOSTNAME" "$MAC_WORKER_USER" "$IDENTITY_FILE" "$KNOWN_HOSTS_FILE" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
alias, hostname, user, identity, known_hosts = sys.argv[2:]
start = "# BEGIN personal-ai-os mac worker"
end = "# END personal-ai-os mac worker"
text = path.read_text(encoding="utf-8")
if start in text and end in text:
    before, rest = text.split(start, 1)
    _, after = rest.split(end, 1)
    text = before.rstrip() + "\n" + after.lstrip()
block = f"""{start}
Host {alias}
    HostName {hostname}
    User {user}
    Port 22
    IdentityFile {identity}
    IdentitiesOnly yes
    PasswordAuthentication no
    KbdInteractiveAuthentication no
    PubkeyAuthentication yes
    StrictHostKeyChecking yes
    UserKnownHostsFile {known_hosts}
    ClearAllForwardings yes
    RequestTTY no
{end}
"""
path.write_text(text.rstrip() + "\n\n" + block, encoding="utf-8")
path.chmod(0o600)
PY
}

setup_key() {
  validate_target
  if [[ ! -e "$IDENTITY_FILE" ]]; then
    ssh-keygen -q -t ed25519 -N '' -C personal-ai-os-mac-worker-vps -f "$IDENTITY_FILE"
  fi
  chmod 600 "$IDENTITY_FILE"
  chmod 644 "${IDENTITY_FILE}.pub"
  write_config
  echo "OK: dedicated identity and host entry configured"
}

trust_host() {
  validate_target
  [[ "${MAC_WORKER_EXPECTED_HOST_FINGERPRINT:-}" =~ ^SHA256:[A-Za-z0-9+/]+$ ]] || {
    echo "MAC_WORKER_EXPECTED_HOST_FINGERPRINT is required" >&2
    exit 2
  }
  temporary="$(mktemp)"
  ssh-keyscan -T 10 -t ed25519 "$MAC_WORKER_HOSTNAME" > "$temporary" 2>/dev/null
  [[ -s "$temporary" ]] || { echo "Could not scan Mac SSH host key" >&2; exit 1; }
  actual="$(ssh-keygen -lf "$temporary" -E sha256 | awk 'NR==1 {print $2}')"
  if [[ "$actual" != "$MAC_WORKER_EXPECTED_HOST_FINGERPRINT" ]]; then
    echo "Host key mismatch: expected $MAC_WORKER_EXPECTED_HOST_FINGERPRINT, got $actual" >&2
    exit 1
  fi
  mv "$temporary" "$KNOWN_HOSTS_FILE"
  chmod 600 "$KNOWN_HOSTS_FILE"
  echo "OK: pinned Mac host key $actual"
}

verify() {
  validate_target
  [[ -f "$IDENTITY_FILE" && -f "${IDENTITY_FILE}.pub" && -f "$KNOWN_HOSTS_FILE" ]]
  ssh -G "$HOST_ALIAS" | awk '$1 ~ /^(hostname|user|identityfile|identitiesonly|stricthostkeychecking|clearallforwardings|requesttty)$/ {print}'
  ssh -o BatchMode=yes -o ConnectTimeout=10 "$HOST_ALIAS" invalid-probe >/tmp/mac-worker-probe.out 2>/tmp/mac-worker-probe.err || true
  grep -q 'only the mac-worker RPC command is allowed' /tmp/mac-worker-probe.out || {
    echo "Forced-command worker probe failed" >&2
    sed -n '1,20p' /tmp/mac-worker-probe.err >&2
    exit 1
  }
  echo "OK: forced-command endpoint is reachable"
}

case "${1:-}" in
  plan) plan ;;
  setup-key)
    [[ "${2:-}" == "--apply" ]] || { echo "Refusing without --apply" >&2; exit 2; }
    setup_key
    ;;
  print-public-key) cat "${IDENTITY_FILE}.pub" ;;
  trust-host)
    [[ "${2:-}" == "--apply" ]] || { echo "Refusing without --apply" >&2; exit 2; }
    trust_host
    ;;
  verify) verify ;;
  *) usage; exit 2 ;;
esac
