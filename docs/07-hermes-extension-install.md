# Hermes Extension Install

Date: 2026-07-07  
Status: Prepared install path. Do not deploy without explicit approval.

## Goal

Install the OS-owned `notion_task_create` wrapper into the existing Hermes
runtime without continuing manual edits in `/usr/local/lib/hermes-agent`.

The immediate target is conservative:

- keep `/opt/personal-ai-os` as the versioned source of truth
- keep Hermes as the runtime/gateway
- install a tiny compatibility bridge in Hermes
- do not restart Hermes automatically
- do not perform a real Notion write during install

## Current Constraint

The current Hermes patch registers native tools by importing a module that calls
`tools.registry.register(...)` at import time, while `toolsets.py` lists the tool
name.

Because of that, simply adding this repository to `PYTHONPATH` is not enough.
Hermes also needs an import path that loads the OS-owned wrapper so registration
happens.

Until Hermes exposes a cleaner plugin/autoload hook, the safe intermediate
installation is:

```text
/usr/local/lib/hermes-agent/tools/notion_task_tool.py
  -> compatibility bridge that imports /opt/personal-ai-os/hermes/tools/notion_task_create.py
```

This is still a Hermes runtime touchpoint, but it is no longer hand-maintained
business logic. The business logic lives in git under `personal-ai-os`.

## Files Installed

The install script manages:

- `/usr/local/lib/hermes-agent/tools/notion_task_tool.py`
- `/usr/local/lib/hermes-agent/toolsets.py`

It backs up existing files before changing them.

It does not change:

- `/root/.hermes/.env`
- `/root/.hermes/config.yaml`
- systemd unit files
- Notion data

It does not restart:

- `hermes-gateway.service`

## Preconditions

On the VPS:

```bash
test -d /opt/personal-ai-os/.git
test -d /usr/local/lib/hermes-agent
test -x /usr/local/lib/hermes-agent/venv/bin/python
```

The checkout should be at a reviewed commit or release tag:

```bash
cd /opt/personal-ai-os
git status --short
git log --oneline --decorate --max-count=3
python3 -m unittest discover
```

## Dry Run

From the repo checkout:

```bash
cd /opt/personal-ai-os
deploy/scripts/install-hermes-extension.sh plan
deploy/scripts/install-hermes-extension.sh verify
```

`plan` prints what would be changed.

`verify` checks that the OS-owned wrapper imports and exposes the expected
Hermes tool schema. It does not contact Notion.

## Install

Install requires an explicit `--apply` flag:

```bash
cd /opt/personal-ai-os
deploy/scripts/install-hermes-extension.sh install --apply
```

The script:

1. creates a timestamped backup directory under `/root/.hermes/backups`
2. backs up current Hermes files
3. writes the compatibility bridge
4. ensures `toolsets.py` lists `notion_task_create`
5. verifies the OS-owned wrapper import

It does not restart Hermes.

## Manual Restart

Only after checking the diff and rollback command:

```bash
systemctl restart hermes-gateway
systemctl status hermes-gateway --no-pager
journalctl -u hermes-gateway -n 100 --no-pager
```

## Post-Restart Verification

Safe checks:

```bash
cd /opt/personal-ai-os
deploy/scripts/install-hermes-extension.sh verify
```

Then verify in Telegram with a non-write routing check first. A real Notion task
write should happen only after the service is healthy and the rollback path is
ready.

## Rollback

The install command prints the exact backup directory.

Manual rollback shape:

```bash
cp /root/.hermes/backups/<timestamp>/notion_task_tool.py /usr/local/lib/hermes-agent/tools/notion_task_tool.py
cp /root/.hermes/backups/<timestamp>/toolsets.py /usr/local/lib/hermes-agent/toolsets.py
systemctl restart hermes-gateway
```

If the previous file did not exist, remove the bridge instead:

```bash
rm -f /usr/local/lib/hermes-agent/tools/notion_task_tool.py
cp /root/.hermes/backups/<timestamp>/toolsets.py /usr/local/lib/hermes-agent/toolsets.py
systemctl restart hermes-gateway
```

## Future Cleaner Target

Replace the compatibility bridge with an official Hermes extension mechanism if
one becomes available:

- plugin package
- configured extension autoload path
- tool registry config
- user-level skill/tool package under Hermes home

Until then, this script keeps the remaining Hermes touchpoint small,
documented, backed up, and generated from git.

## Skill Routing Overlay

The bridge makes `notion_task_create` available, but Hermes still needs routing
instructions that prefer the native tool over generic Notion MCP page creation.

The repo-owned skill overlay lives at:

```text
hermes/skills/productivity/notion-tasks/SKILL.md
```

Install it with:

```bash
cd /opt/personal-ai-os
deploy/scripts/install-hermes-skill.sh plan
deploy/scripts/install-hermes-skill.sh verify
deploy/scripts/install-hermes-skill.sh install --apply
```

The skill install script backs up the existing skill directory and does not
restart Hermes.
