# Safe Hermes to Mac Worker Delegation

Date: 2026-08-23
Status: implementation, local validation, and isolated VPS staging complete;
production enablement is blocked until this Mac joins the VPS tailnet and
Remote Login is enabled.

## Architecture

```text
Telegram
   |
Hermes gateway on VPS
   |  mac_worker_run/status/stop/doctor
   |  dedicated SSH identity, strict pinned host key, no forwarding or TTY
   v
Tailscale-only Mac address
   |  authorized_keys forced command + restrict
   v
personal-ai-os-mac-worker
   |  project alias -> server-owned absolute path allowlist
   +-- Codex: workspace-write, approvals=never, network off by default
   +-- Claude: permission checks, file tools only, no Bash in the safe MVP
```

The Hermes model never receives a general SSH or shell tool. It can send only a
base64url-encoded JSON RPC with one of four operations. Both the VPS bridge and
the Mac endpoint validate the request. The Mac resolves the configured project
and verifies that it remains below an allowed root, including after symlink
resolution.

## Security Properties

- SSH is addressed only through a Tailscale `100.64.0.0/10` address or
  `*.ts.net` MagicDNS name. Do not add router port forwarding for TCP 22.
- The VPS uses a dedicated Ed25519 identity and a dedicated pinned known-hosts
  file. Password and keyboard-interactive authentication are disabled.
- The Mac `authorized_keys` entry uses `restrict` and a forced command. Even a
  direct `ssh host bash` request reaches only the worker parser and is rejected.
- Projects are tool parameters by alias, not paths. Only aliases present in the
  Mac config can run.
- Codex runs non-interactively with `workspace-write`; live network access is
  disabled unless an explicit push authorization reaches the tool.
- Commit and push default to denied. Git hooks add a second guard and the task
  policy repeats the restriction. Claude receives no Bash tool in the safe MVP.
- The worker passes a small environment allowlist to child processes. It does
  not forward VPS environment variables or SSH agents.
- Job files and local logs are mode `0600`; returned log tails pass through
  token/password pattern redaction. Prompts must not contain secrets.

## Current Audit

Verified on 2026-08-23:

- VPS SSH alias `hermes` works; `hermes-gateway.service` is active.
- VPS Tailscale is running as `hermes-vps.tailf4d775.ts.net`, IP
  `100.92.32.85`.
- production checkout is clean on `phase3-capture-router-v1` at `28eae08f`.
- Mac has no Tailscale app/CLI and TCP 22 is not listening.
- Codex CLI `0.148.0-alpha.21` is installed and logged in with ChatGPT.
- Claude Code `2.1.221` is installed but `claude auth status` reports
  `loggedIn=false`.

## 1. Prepare the Mac Worker

From the repository on the Mac:

```bash
cd /path/to/personal-ai-os
deploy/scripts/install-mac-worker.sh plan
deploy/scripts/install-mac-worker.sh install --apply
deploy/scripts/install-mac-worker.sh verify
```

The default project alias is `personal-ai-os`. Add more projects by editing
`~/.config/personal-ai-os/mac-worker.json`; every project must also be below one
of `allow_roots`. Keep that config mode `0600`.

## 2. Join the Same Tailnet and Enable SSH

Install the official Tailscale macOS app, sign in to the same tailnet as the
VPS, and record the Mac's Tailscale IP or MagicDNS name:

```bash
brew install --cask tailscale-app
open -a Tailscale
/Applications/Tailscale.app/Contents/MacOS/Tailscale status
```

The sign-in/system-extension approval is interactive. Then enable macOS Remote
Login for this user. This requires the Mac administrator password:

```bash
sudo systemsetup -setremotelogin on
nc -z 127.0.0.1 22
```

Do not expose or forward port 22 on the public router. Tailnet policy should
allow TCP 22 from the VPS device to this Mac and deny other sources where that
access is not needed. Tailscale installation and ACL references:

- <https://tailscale.com/kb/1016/install-mac>
- <https://tailscale.com/kb/1337/acl-syntax>
- <https://tailscale.com/kb/1082/firewall-ports>

## 3. Create and Install the Dedicated SSH Identity

On the VPS checkout at the candidate commit:

```bash
cd /opt/personal-ai-os
export MAC_WORKER_HOSTNAME='<mac-name>.tailf4d775.ts.net'
export MAC_WORKER_USER='evgeniisobolev'
deploy/scripts/setup-vps-mac-worker-ssh.sh plan
deploy/scripts/setup-vps-mac-worker-ssh.sh setup-key --apply
deploy/scripts/setup-vps-mac-worker-ssh.sh print-public-key
```

Save that public key to a temporary file on the Mac and authorize only the
forced worker command:

```bash
cd /path/to/personal-ai-os
VPS_PUBLIC_KEY_FILE=/path/to/personal_ai_os_mac_worker_ed25519.pub \
  deploy/scripts/install-mac-worker.sh authorize-key --apply
```

Read the Mac SSH host fingerprint locally, through the trusted local terminal:

```bash
ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub -E sha256
```

Pin that exact fingerprint on the VPS and verify the forced endpoint:

```bash
cd /opt/personal-ai-os
export MAC_WORKER_HOSTNAME='<mac-name>.tailf4d775.ts.net'
export MAC_WORKER_USER='evgeniisobolev'
export MAC_WORKER_EXPECTED_HOST_FINGERPRINT='SHA256:...'
deploy/scripts/setup-vps-mac-worker-ssh.sh trust-host --apply
deploy/scripts/setup-vps-mac-worker-ssh.sh verify
```

## 4. Isolated VPS Staging

Use an isolated worktree at the reviewed commit. Do not alter the production
checkout or restart the gateway:

```bash
cd /opt/personal-ai-os
git worktree add --detach /opt/personal-ai-os-mac-worker-staging <commit>
cd /opt/personal-ai-os-mac-worker-staging
python3 -m unittest discover
deploy/scripts/install-mac-worker-hermes-runtime.sh plan
deploy/scripts/install-mac-worker-hermes-runtime.sh verify
SKILL_NAME=mac-worker OS_DIR="$PWD" deploy/scripts/install-hermes-skill.sh verify
```

Run the doctor RPC from the VPS staging worktree:

```bash
PYTHONPATH="$PWD" PERSONAL_AI_OS_MAC_WORKER_SSH_HOST=personal-ai-os-mac-worker \
python3 - <<'PY'
import json
from services.mac_worker.client import call_mac_worker
from services.mac_worker.protocol import WorkerRequest
print(json.dumps(call_mac_worker(WorkerRequest.from_dict({"operation": "doctor"})), indent=2))
PY
```

Then run a no-write Codex smoke against an allowlisted disposable or clean
project, poll it, and verify the Git tree and HEAD did not change. A full smoke
can use the local worker CLI token generated by `encode_request`; Hermes uses
the same protocol.

## 5. Production Enablement

Proceed only when all of these pass:

- full unit suite on candidate commit;
- forced-command SSH probe;
- doctor reports the expected project aliases and authenticated Codex;
- run/status/stop smoke;
- gateway still healthy and the Instagram/PLAUD/link-capture toolsets are
  unchanged;
- production backup and rollback paths are recorded.

Install the bridge and skill without enabling or restarting first:

```bash
cd /opt/personal-ai-os-mac-worker-staging
OS_DIR="$PWD" deploy/scripts/install-mac-worker-hermes-runtime.sh install --apply
SKILL_NAME=mac-worker OS_DIR="$PWD" deploy/scripts/install-hermes-skill.sh install --apply
deploy/scripts/enable-mac-worker-runtime.sh plan
deploy/scripts/enable-mac-worker-runtime.sh enable --apply
```

The enable command performs a live doctor check and refuses to continue unless
Codex is authenticated. Review backups, then restart and smoke Telegram:

```bash
systemctl restart hermes-gateway
systemctl status hermes-gateway --no-pager
journalctl -u hermes-gateway -n 100 --no-pager
```

Telegram examples:

```text
передай Codex на моём Mac задачу в personal-ai-os: запусти тесты и объясни падение, ничего не коммить и не пушь
mac status <job_id>
mac stop <job_id>
```

## Rollback

Disable the Telegram toolset and systemd environment first:

```bash
cd /opt/personal-ai-os-mac-worker-staging
deploy/scripts/enable-mac-worker-runtime.sh disable --apply
systemctl restart hermes-gateway
```

Restore `toolsets.py`, the bridge, skill directory, and Hermes config from the
timestamped backup directories printed by their install commands. Removing the
Mac forced-key line tagged `personal-ai-os-mac-worker-vps` revokes VPS access.
Turning off Remote Login is optional if it is not otherwise used:

```bash
sudo systemsetup -setremotelogin off
```
