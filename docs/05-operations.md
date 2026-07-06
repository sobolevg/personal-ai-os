# Operations

Date: 2026-07-06  
Status: Baseline operations placeholder.

## Rollback Rule

Every deployable state must have:

- git tag
- previous tag
- deployment log
- exact rollback command

Example:

```bash
cd /opt/personal-ai-os
git fetch --tags
git checkout v0.2.0-task-capture
systemctl restart hermes-gateway
```

## Config Backup Targets

Before changing Hermes config, back up:

- `/root/.hermes/config.yaml`
- `/root/.hermes/.env`
- `/etc/systemd/system/hermes-gateway.service`
- `/etc/systemd/system/hermes-gateway.service.d/*`

## Notion Safety

- Do not bulk edit without approval.
- Prefer create-only operations first.
- Store source message and idempotency key.
- Store previous values before updates where practical.
- Archive instead of permanent delete.
