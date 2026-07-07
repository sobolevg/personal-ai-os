# Telegram Capture Runtime Install

Date: 2026-07-08  
Status: bridge deployed; Telegram enablement is managed separately.

## Purpose

This install path places the repo-owned Telegram capture wrapper into the Hermes
runtime and adds a separate `personal_ai_os_capture` toolset.

It does not enable the toolset for Telegram. That keeps this as a safe deploy
checkpoint before real automation activation.

## What It Installs

- Hermes bridge:
  `/usr/local/lib/hermes-agent/tools/personal_ai_os_telegram_capture.py`
- Hermes tool:
  `personal_ai_os_telegram_capture`
- Hermes toolset:
  `personal_ai_os_capture`

## Commands

From the VPS checkout:

```bash
cd /opt/personal-ai-os
deploy/scripts/install-telegram-capture-runtime.sh plan
deploy/scripts/install-telegram-capture-runtime.sh verify
deploy/scripts/install-telegram-capture-runtime.sh install --apply
```

## Safety Boundary

The script does not:

- restart `hermes-gateway.service`
- write to Notion
- edit `platform_toolsets.telegram`
- edit systemd units

The tool itself defaults to `execute=false`, which means plan and event logging
only. Direct writes require both `execute=true` and the server-side
`PERSONAL_AI_OS_CAPTURE_EXECUTE_ENABLED=1` flag.

## Event Log

Prepare the event log path before runtime activation:

```bash
deploy/scripts/manage-event-log.sh install --apply
```

Default path:

```text
/root/.hermes/personal-ai-os/events/events.jsonl
```

## Activation Still Required

After this bridge is installed and reviewed, Telegram dry-plan activation is a
separate step:

1. restart Hermes after reviewing the generated rollback command
2. verify the tool is discoverable in Hermes
3. add `personal_ai_os_capture` to `platform_toolsets.telegram`:

```bash
deploy/scripts/enable-telegram-capture-runtime.sh plan
deploy/scripts/enable-telegram-capture-runtime.sh verify
deploy/scripts/enable-telegram-capture-runtime.sh enable --apply
```

4. restart Hermes again
5. test one dry-plan message

This does not enable Notion writes because
`PERSONAL_AI_OS_CAPTURE_EXECUTE_ENABLED` remains unset.

## Rollback

The install script prints the backup directory and exact rollback commands after
`install --apply`.
