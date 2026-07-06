# Hermes Audit

Date: 2026-07-06  
Status: Baseline summary extracted from the Phase 1 technical specification.

## Runtime

Hermes currently runs on the VPS host `hermes` as a systemd service:

- Service: `hermes-gateway.service`
- Runtime command: `/usr/local/lib/hermes-agent/venv/bin/python -m hermes_cli.main gateway run`
- Working directory: `/root/.hermes`
- Main codebase: `/usr/local/lib/hermes-agent`
- User/runtime home: `/root/.hermes`
- State/logs: `/root/.hermes/state.db`, `/root/.hermes/logs`
- Messaging platform: Telegram
- Notion MCP server: enabled through `npx -y @notionhq/notion-mcp-server`

## Active Capabilities

Hermes currently provides Telegram transport, topic support, Notion MCP access,
native tools, skills, memory, session persistence, cron capability, and custom
personal Notion skills.

The custom native tool `notion_task_create` is currently patched directly into
Hermes.

## Current Personal Patches

Observed local Hermes modifications:

- `toolsets.py`
- `tools/todo_tool.py`
- `tools/notion_task_tool.py`

The `notion_task_create` tool is registered in Hermes toolsets and creates
pages in the Notion task database with fixed schema assumptions.

## Architectural Risk

Personal domain logic currently lives inside the Hermes runtime installation.
That makes upgrades and rollback fragile.

Target direction:

- keep Hermes close to upstream
- move personal logic into this repository
- install Personal AI OS capabilities into Hermes from a tagged release
- document rollback before deployment

## Notion Baseline

Notion remains the source of truth for personal data.

Current known task database facts:

- Task DB: `Мои задачи`
- Database ID: `176a0a22-1593-8122-94e7-cdb420698046`
- Data source ID: `176a0a22-1593-81e7-94dd-000ba2c24933`
- Main routing field: `Когда начать`
- Valid buckets: `Сегодня`, `На неделе`, `Потом`, `На выходных`

Phase 1 must not redesign the Notion workspace. It should document contracts
and move personal logic into git.
