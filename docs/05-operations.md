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

## Event Log

Default VPS path:

```text
/root/.hermes/personal-ai-os/events/events.jsonl
```

Override with:

```text
PERSONAL_AI_OS_EVENT_LOG_PATH
```

The event log is append-only JSONL. It stores planned, executed, failed, and
duplicate-skipped events. It does not store secrets.

Manage the path with:

```bash
deploy/scripts/manage-event-log.sh plan
deploy/scripts/manage-event-log.sh verify
deploy/scripts/manage-event-log.sh install --apply
deploy/scripts/manage-event-log.sh backup --apply
deploy/scripts/manage-event-log.sh rotate --apply
```

Rotation backs up the current JSONL file under `/root/.hermes/backups` before
truncating it. The default rotation threshold is `10485760` bytes and can be
changed with `MAX_BYTES`.

## Telegram Capture Runtime

Install or verify the prepared Hermes bridge with:

```bash
deploy/scripts/install-telegram-capture-runtime.sh plan
deploy/scripts/install-telegram-capture-runtime.sh verify
deploy/scripts/install-telegram-capture-runtime.sh install --apply
```

This only installs the `personal_ai_os_telegram_capture` bridge and
`personal_ai_os_capture` toolset. It does not enable the toolset for Telegram.

Before activation, confirm:

- event log path is installed and valid
- Hermes imports the bridge without errors
- rollback command from the install output is saved
- `platform_toolsets.telegram` change is intentional and reviewed
