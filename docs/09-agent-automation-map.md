# Agent and Automation Map

Status: draft architecture map. No production behavior is changed by this
document.

## Purpose

This map connects the first generation of Personal AI OS agents and automations
so the system can move from isolated contracts to a staged runtime rollout.

Hermes remains the messaging, runtime, and tool gateway. Personal AI OS owns the
domain contracts: which agent decides, which automation runs, which tools may be
used, and which writes are safe.

## Current Checkpoint

Implemented in git:

- 8 agent contracts under `agents/*.agent.json`
- 10 automation contracts under `automations/*.automation.json`
- agent contract validator and catalog tests
- automation contract validator and catalog tests
- deterministic capture router and dispatch plan tests
- Hermes native `notion_task_create` bridge for task creation

Implemented as local foundations:

- event log schema and JSONL store
- idempotency key generation from source platform, source message id, and
  action
- runtime-safe Telegram capture planning around dispatch and event logging
- task execution path for high-confidence Telegram captures, with executed or
  failed outcome events
- event log path management script for install, backup, and rotation

Implemented on the VPS:

- Hermes bridge for `personal_ai_os_telegram_capture`, behind a separate
  `personal_ai_os_capture` toolset
- Telegram platform access to `personal_ai_os_capture`, with execution blocked
  by default
- explicit Telegram native-tool dry-plan smoke test for
  `personal_ai_os_telegram_capture`
- ordinary Telegram `todo:` dry-plan smoke test through
  `personal_ai_os_telegram_capture`
- direct `notion_task_create` writes blocked unless explicitly enabled
- event log path at `/root/.hermes/personal-ai-os/events/events.jsonl`

Not implemented yet:

- Notion write enablement through `PERSONAL_AI_OS_CAPTURE_EXECUTE_ENABLED`
- Notion write contracts beyond tasks
- confirmation UI for ambiguous captures

## Agent Catalog

| Agent | Status | Primary role | Runtime readiness |
| --- | --- | --- | --- |
| Personal Assistant | draft | Front door for Telegram capture routing | Partially ready: router, dispatch, event log, and Hermes wrapper are tested |
| Inbox Processor | draft | Convert ambiguous captures into reviewable candidates | Design only |
| Task Planner | draft | Normalize tasks, suggest buckets and breakdowns | Partially ready through `notion_task_create` |
| Knowledge Curator | draft | Turn durable notes and research into knowledge candidates | Design only |
| Resource Importer | draft | Import URLs, books, movies, and files as resource candidates | Design only |
| Weekly Review | draft | Summarize weekly snapshots and propose focus | Design only |
| Research Agent | draft | Produce source-backed briefs and hand off durable findings | Design only |
| Project Manager | draft | Draft project candidates and initial tasks | Design only |

## Automation Catalog

| Automation | Status | Agents | Write policy | Runtime readiness |
| --- | --- | --- | --- | --- |
| Telegram To Inbox | draft | Personal Assistant, Inbox Processor, Task Planner, Resource Importer | `create_only` for high-confidence tasks; draft for unfinished paths | Ordinary Telegram dry-plan routing passed; writes still disabled |
| Voice Notes | draft | Personal Assistant, Inbox Processor | `draft_only` | Needs transcription path |
| Daily Planning | draft | Task Planner, Weekly Review, Personal Assistant | `read_only` | Needs Notion read contracts |
| Weekly Review | draft | Weekly Review, Task Planner, Project Manager | `draft_only` | Needs Notion read contracts |
| Project Creation | draft | Project Manager, Task Planner, Research Agent | `draft_only` | Needs project contract |
| Task Breakdown | draft | Task Planner, Project Manager | `draft_only` | Needs confirmation flow |
| Resource Classification | draft | Resource Importer, Knowledge Curator | `draft_only` | Needs resource contract |
| Book Import | draft | Resource Importer, Knowledge Curator | `draft_only` | Needs resource metadata contract |
| Movie Import | draft | Resource Importer | `draft_only` | Needs entertainment/resource contract |
| Knowledge Linking | draft | Knowledge Curator, Research Agent | `draft_only` | Needs knowledge contract |

## First Runtime Path

The first runtime path should remain narrow:

```text
Telegram message
  -> Personal Assistant
  -> capture router
  -> capture dispatch plan
  -> if high-confidence task: notion_task_create
  -> else: draft candidate / confirmation path
```

Why this path first:

- Hermes already exposes `notion_task_create` to Telegram.
- The task Notion contract is the only write contract filled enough for direct
  creation.
- The router and dispatch plan are covered by fixtures and unit tests.
- The path preserves source platform and message id, which is required for the
  next event-log step.

## Required Safety Boundary

Before enabling broader runtime automation:

- wire event log into the Telegram runtime path
- do not create resource, expense, project, or knowledge pages directly
- keep ambiguous captures as draft candidates
- keep bulk updates confirmation-only
- keep Notion workspace structure unchanged

## Next Build Steps

1. Wrap `Telegram To Inbox` around the existing dispatch plan.
2. Record planned events before writes.
3. Block duplicate events by idempotency key.
4. Add confirmation/draft handling for resource, expense, and inbox paths.
5. Decide when to enable Notion task writes through the server-side execution
   flags.
6. Tag a runtime checkpoint after automatic routing verification.

## Checkpoint Criteria

This design layer is ready to merge when:

- all contract tests pass
- all agent and automation contracts are present
- this map matches the contract catalog
- VPS deploy is recorded in the deployment log
- rollout notes clearly say this is a bridge checkpoint, not Telegram activation
