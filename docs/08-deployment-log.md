# Deployment Log

## 2026-07-08 - Telegram Capture Dry-Plan Enablement

Status: enabled for Telegram with execution blocked; explicit native-tool smoke
tested.

Commit deployed:

```text
0149460 feat: gate telegram capture execution
```

Target:

```text
VPS host: hermes
Checkout: /opt/personal-ai-os
Hermes service: hermes-gateway.service
Branch: phase3-capture-router-v1
```

Validation before enablement:

- ran `python3 -m unittest discover` on the VPS: 37 tests OK
- reinstalled `personal_ai_os_telegram_capture` bridge from repo-owned code
- verified `personal_ai_os_capture` was defined in Hermes `toolsets.py`
- verified `platform_toolsets.telegram` initially contained
  `['hermes-telegram', 'notion_task']`

Bridge reinstall backup:

```text
/root/.hermes/backups/personal-ai-os-telegram-capture-20260707T222513Z
```

Enablement:

```text
deploy/scripts/enable-telegram-capture-runtime.sh enable --apply
systemctl restart hermes-gateway
```

Config backup:

```text
/root/.hermes/backups/personal-ai-os-telegram-capture-enable-20260707T222523Z
```

Post-restart validation:

- `hermes-gateway.service` is active.
- `platform_toolsets.telegram` now contains
  `['hermes-telegram', 'notion_task', 'personal_ai_os_capture']`.
- `PERSONAL_AI_OS_CAPTURE_EXECUTE_ENABLED` is not enabled.
- Direct dry-plan smoke returned route `task`, event status `planned`, and
  `execution_event=None`.
- Direct `execute=true` smoke returned a controlled error:
  `execution is disabled; set PERSONAL_AI_OS_CAPTURE_EXECUTE_ENABLED=1 on the server to allow writes`.
- Smoke checks used a temporary event log under `/tmp` and did not write to
  Notion.

Telegram smoke:

- Sent from Telegram Web to `@hermes_evgenii_bot`:
  `todo: smoke dry plan personal ai os`.
- Result: Hermes responded, but selected the older terminal path rather than
  `personal_ai_os_telegram_capture`.
- Sent explicit native-tool smoke:
  `Use native tool personal_ai_os_telegram_capture with execute=false for message: todo: smoke dry plan personal ai os explicit`.
- Result: Hermes called `personal_ai_os_telegram_capture`.
- Event log now contains one planned event:
  - route: `task`
  - action: `notion_task_create`
  - source platform: `telegram`
  - source message id: `telegram:535063`
  - normalized text: `todo: smoke dry plan personal ai os explicit`
  - Notion page id: `null`
- No Notion write occurred.

Follow-up:

- Update routing prompt/skill behavior so ordinary task-like Telegram messages
  choose `personal_ai_os_telegram_capture` without an explicit tool instruction.

Rollback:

```bash
cp "/root/.hermes/backups/personal-ai-os-telegram-capture-enable-20260707T222523Z/config.yaml" "/root/.hermes/config.yaml"
systemctl restart hermes-gateway
```

## 2026-07-07 - Telegram Capture Runtime Bridge

Status: deployed as Hermes bridge, not enabled for Telegram.

Commit deployed:

```text
62b8e5f feat: add telegram capture hermes bridge install path
```

Target:

```text
VPS host: hermes
Checkout: /opt/personal-ai-os
Hermes service: hermes-gateway.service
Branch: phase3-capture-router-v1
```

Deployment transport:

- `git fetch origin` from the VPS failed because the server does not have a
  GitHub SSH key for `git@github.com:sobolevg/personal-ai-os.git`.
- The commit was transferred as a local git bundle and fetched into the VPS
  checkout, preserving git state without adding secrets to the server.

Validation before install:

- ran `python3 -m unittest discover` on the VPS: 36 tests OK
- ran `deploy/scripts/manage-event-log.sh verify`
- ran `deploy/scripts/manage-event-log.sh install --apply`
- ran `deploy/scripts/install-telegram-capture-runtime.sh plan`
- ran `deploy/scripts/install-telegram-capture-runtime.sh verify`

Install:

```text
deploy/scripts/install-telegram-capture-runtime.sh install --apply
```

Backup:

```text
/root/.hermes/backups/personal-ai-os-telegram-capture-20260707T202708Z
```

Restart:

```text
systemctl restart hermes-gateway
```

Post-restart validation:

- `hermes-gateway.service` is active.
- `personal_ai_os_telegram_capture` bridge is installed under
  `/usr/local/lib/hermes-agent/tools/`.
- `personal_ai_os_capture` toolset is defined in
  `/usr/local/lib/hermes-agent/toolsets.py`.
- `platform_toolsets.telegram` remains unchanged:
  `['hermes-telegram', 'notion_task']`.
- Dry-plan smoke test returned route `task`, event status `planned`,
  `should_execute_action=True`, and `execution_event=None`.
- The dry-plan smoke used a temporary event log under `/tmp` and did not write
  to Notion.

Rollback:

```bash
cp "/root/.hermes/backups/personal-ai-os-telegram-capture-20260707T202708Z/toolsets.py" "/usr/local/lib/hermes-agent/toolsets.py"
if [[ -f "/root/.hermes/backups/personal-ai-os-telegram-capture-20260707T202708Z/personal_ai_os_telegram_capture.py" ]]; then
  cp "/root/.hermes/backups/personal-ai-os-telegram-capture-20260707T202708Z/personal_ai_os_telegram_capture.py" "/usr/local/lib/hermes-agent/tools/personal_ai_os_telegram_capture.py"
else
  rm -f "/usr/local/lib/hermes-agent/tools/personal_ai_os_telegram_capture.py"
fi
systemctl restart hermes-gateway
```

## 2026-07-06 - Hermes Notion Task Bridge

Status: deployed and native-tool smoke-tested.

Commit deployed:

```text
142ad84 chore: add hermes extension install path
```

Target:

```text
VPS host: hermes
Checkout: /opt/personal-ai-os
Hermes service: hermes-gateway.service
```

Validation before install:

- cloned `sobolevg/personal-ai-os` into `/opt/personal-ai-os`
- ran `python3 -m unittest discover`
- ran `deploy/scripts/install-hermes-extension.sh plan`
- ran `deploy/scripts/install-hermes-extension.sh verify`

Install:

```text
deploy/scripts/install-hermes-extension.sh install --apply
```

Backup:

```text
/root/.hermes/backups/personal-ai-os-20260706T225649Z
```

Restart:

```text
systemctl restart hermes-gateway
```

Smoke test:

- Telegram bot responded after restart.
- Notion task creation flow completed from Telegram.
- Test task title included `TEST personal-ai-os bridge`.
- Direct native `notion_task_create` exposure confirmed after enabling the
  `notion_task` toolset for Telegram platform config.

Resolved caveat:

- Initial Telegram traces used Notion MCP or Python fallback because
  `notion_task_create` was registered in Hermes runtime but not enabled in
  Telegram's persisted `platform_toolsets.telegram` config.
- The install script now defines the `notion_task` toolset and enables it for
  Telegram, so new Telegram sessions can call `notion_task_create` directly.

Rollback:

```bash
cp "/root/.hermes/backups/personal-ai-os-20260706T225649Z/toolsets.py" "/usr/local/lib/hermes-agent/toolsets.py"
if [[ -f "/root/.hermes/backups/personal-ai-os-20260706T225649Z/notion_task_tool.py" ]]; then
  cp "/root/.hermes/backups/personal-ai-os-20260706T225649Z/notion_task_tool.py" "/usr/local/lib/hermes-agent/tools/notion_task_tool.py"
else
  rm -f "/usr/local/lib/hermes-agent/tools/notion_task_tool.py"
fi
systemctl restart hermes-gateway
```
