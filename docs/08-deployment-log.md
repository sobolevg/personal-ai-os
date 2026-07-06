# Deployment Log

## 2026-07-06 - Hermes Notion Task Bridge

Status: deployed and smoke-tested.

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

Observed caveat:

- The visible Telegram trace showed Notion MCP calls for task creation.
- Native `notion_task_create` bridge import was verified by the install script.
- A later trace should explicitly confirm direct `notion_task_create` tool usage.

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
