# Notion Contracts

Date: 2026-07-06  
Status: Placeholder for Phase 1 contract work.

## Policy

Notion is the source of truth for personal data. Personal AI OS may read from
and write to Notion only through documented contracts.

## Required Contract Files

- `integrations/notion/contracts/tasks.yaml`
- `integrations/notion/contracts/projects.yaml`
- `integrations/notion/contracts/areas.yaml`
- `integrations/notion/contracts/resources.yaml`
- `integrations/notion/contracts/knowledge.yaml`
- `integrations/notion/contracts/entertainment.yaml`
- `integrations/notion/contracts/expenses.yaml`

## Safe Write Rules

- Prefer create-only operations first.
- Store source message metadata when available.
- Use idempotency keys before enabling automations.
- Ask before bulk updates.
- Archive instead of permanent delete.
- Never store secrets in contracts.

## First Contract

The first concrete contract should be `tasks.yaml`, matching current
`notion_task_create` behavior before generalizing it.
