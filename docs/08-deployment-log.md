# Deployment Log

## 2026-07-08 - Event Log Review Tooling

Status: deployed read-only review tooling for planned Telegram capture events.

Commit deployed:

```text
6769bd0 feat: add event log review tooling
```

Target:

```text
VPS host: hermes
Checkout: /opt/personal-ai-os
Hermes service: hermes-gateway.service
Branch: phase3-capture-router-v1
```

Deployment transport:

- transferred the branch update as a git bundle because the VPS still does not
  have GitHub SSH access.
- merged with `git merge --ff-only origin/phase3-capture-router-v1`.
- no Hermes restart was required because this rollout only adds repo-owned
  review tooling.

Validation:

- ran `python3 -m unittest discover` on the VPS: 44 tests OK
- ran `deploy/scripts/review-event-log.sh summary`
- ran `deploy/scripts/review-event-log.sh pending`
- confirmed `hermes-gateway.service` is active

Review result:

- event log path: `/root/.hermes/personal-ai-os/events/events.jsonl`
- total events: 3
- pending planned events: 3
- statuses: `planned=3`
- pending items are the previous dry-plan Telegram smoke captures:
  - `todo: smoke dry plan personal ai os explicit`
  - `todo: dry plan only capture smoke 20260708`
  - `todo: clean capture routing smoke 20260708`

Rollback:

```bash
cd /opt/personal-ai-os
git checkout c7c1446
```

## 2026-07-08 - Telegram Capture Auto Routing

Status: ordinary Telegram `todo:` messages route to the capture event log with
direct Notion writes disabled.

Commits deployed:

```text
4ad994d feat: route telegram task captures to capture tool
3616a08 fix: gate direct notion task writes
33002d7 fix: keep notion task out of telegram dry-plan tools
```

Target:

```text
VPS host: hermes
Checkout: /opt/personal-ai-os
Hermes service: hermes-gateway.service
Branch: phase3-capture-router-v1
```

Validation and install:

- ran `python3 -m unittest discover` on the VPS: 39 tests OK
- installed updated `notion-tasks` skill routing overlay
- installed updated `notion_task_create` bridge with server-side write gate
- installed updated `personal_ai_os_telegram_capture` bridge
- updated `toolsets.py` so `notion_task_create` is not in shared core tools
- updated Telegram platform config to `['hermes-telegram', 'personal_ai_os_capture']`
- restarted `hermes-gateway.service`

Backups:

```text
/root/.hermes/backups/personal-ai-os-skill-notion-tasks-20260707T224335Z
/root/.hermes/backups/personal-ai-os-20260707T224331Z
/root/.hermes/backups/personal-ai-os-telegram-capture-20260707T224335Z
```

Safety incident during rollout:

- A first ordinary Telegram smoke still selected direct `notion_task_create` and
  created a Notion task titled `auto routing smoke personal ai os`.
- The page was immediately archived:
  `396a0a22-1593-81e0-852c-db6545d5bd8d`.
- Direct `notion_task_create` is now blocked unless
  `PERSONAL_AI_OS_NOTION_TASK_CREATE_ENABLED=1` is set server-side.
- `PERSONAL_AI_OS_CAPTURE_EXECUTE_ENABLED` remains unset.

Final smoke:

- Sent ordinary Telegram message:
  `todo: clean capture routing smoke 20260708`.
- Hermes replied that the item was planned and not written to Notion.
- Event log contains a planned event:
  - route: `task`
  - action: `notion_task_create`
  - source message id: `535074-3`
  - normalized text: `todo: clean capture routing smoke 20260708`
  - Notion page id: `null`
- No Notion page was created by the final smoke.

Rollback:

```bash
cp "/root/.hermes/backups/personal-ai-os-20260707T224331Z/toolsets.py" "/usr/local/lib/hermes-agent/toolsets.py"
cp "/root/.hermes/backups/personal-ai-os-20260707T224331Z/config.yaml" "/root/.hermes/config.yaml"
rm -rf "/root/.hermes/skills/productivity/notion-tasks"
cp -R "/root/.hermes/backups/personal-ai-os-skill-notion-tasks-20260707T224335Z/notion-tasks" "/root/.hermes/skills/productivity/notion-tasks"
systemctl restart hermes-gateway
```

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
