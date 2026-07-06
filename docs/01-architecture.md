# Personal AI Operating System with Hermes

Phase 1 Technical Specification  
Date: 2026-07-06  
Status: Documentation only. No Notion redesign. No execution plan applied.

## 0. Executive Summary

The existing Notion workspace is considered stable and must remain the source of truth. Hermes already runs on the VPS as a Telegram-facing agent gateway with Notion MCP enabled and several personal Notion skills installed. The next architectural move is not to rebuild Notion or fork Hermes logic into random scripts. The correct move is to build a separate modular Personal AI OS layer around Hermes.

Every new capability must be classified as one of:

- Agent: goal-oriented reasoning module with a prompt, tools, inputs, outputs, and workflow.
- Automation: event or schedule-driven workflow that invokes agents/integrations.
- Integration: connector/adaptor for external systems such as Notion, Telegram, Google Drive, OCR, Search, Vision, GitHub, ChatGPT, Claude Code.

Hermes should remain the messaging/runtime layer. The Personal AI OS should become the domain orchestration layer.

## 1. Hermes Audit

### 1.1 Runtime

Hermes is running on VPS host `hermes` as a systemd service:

- Service: `hermes-gateway.service`
- Runtime command: `/usr/local/lib/hermes-agent/venv/bin/python -m hermes_cli.main gateway run`
- Working directory: `/root/.hermes`
- Main codebase: `/usr/local/lib/hermes-agent`
- User/runtime home: `/root/.hermes`
- State/logs: `/root/.hermes/state.db`, `/root/.hermes/logs`
- Messaging platform currently connected: Telegram
- Notion MCP process observed: `node ... notion-mcp-server`

The service is configured with restart behavior and journald logging. Google Cloud Vision credentials are also present at systemd level via `GOOGLE_APPLICATION_CREDENTIALS=/etc/secrets/gcp-vision-key.json`.

### 1.2 Current Active Capabilities

Hermes currently has:

- Telegram bot transport.
- Telegram DM topic support and topic auto-renaming.
- Notion MCP server enabled through `npx -y @notionhq/notion-mcp-server`.
- Built-in tools: web, browser, terminal, file, code execution, vision, image generation, TTS, skills, internal todo, memory, session search, clarify, delegation, cronjob, computer use.
- Notion-specific custom skills under `/root/.hermes/skills/productivity`.
- A custom native tool `notion_task_create`.
- Session persistence in SQLite.
- Skill/memory curation enabled.

Cron exists as a Hermes capability, but no scheduled jobs are currently configured.

### 1.3 Current Notion Skills

Existing Hermes skills already route several personal workflows:

- `notion`: generic Notion MCP/API guidance.
- `notion-tasks`: task capture into `Мои задачи`.
- `notion-expenses`: expense capture into family/trip expense databases.
- `notion-films`: film/book import workflows.
- `notion-workspace`: workspace/audit/migration guidance.

Important current task database facts:

- Task DB: `Мои задачи`
- Database ID: `176a0a22-1593-8122-94e7-cdb420698046`
- Data source ID: `176a0a22-1593-81e7-94dd-000ba2c24933`
- Main routing field: `Когда начать`
- Valid buckets: `Сегодня`, `На неделе`, `Потом`, `На выходных`

### 1.4 Local Hermes Modifications

The installed Hermes codebase has local changes:

- Modified `toolsets.py`.
- Modified `tools/todo_tool.py`.
- Added `tools/notion_task_tool.py`.

The custom `notion_task_create` tool is registered and included in `hermes-telegram`, `hermes-cron`, and `hermes-cli` toolsets. It creates pages directly in `Мои задачи` with fixed schema assumptions.

Architectural concern: this personal domain logic is patched directly into the upstream Hermes installation. This works now, but is fragile for upgrades. It should be moved into a dedicated AI OS plugin/integration package or separate repository.

### 1.5 Current Notion Workspace State

The Notion workspace has already been reorganized into a Second Brain structure and must not be redesigned in Phase 1.

Current target state from the Notion audit:

```text
Workspace
├── Second Brain
│   ├── 00. Inbox
│   ├── 01. Projects
│   ├── 02. Areas
│   ├── 03. Courses
│   ├── 04. Personal
│   ├── 05. Knowledge Graph
│   ├── 06. Resources
│   ├── 07. Entertainment
│   └── 08. System
└── Archive
```

Phase 5 audit notes indicate the workspace was moved from a flat layout to a PARA-based Second Brain. Remaining manual Notion UI work may exist, but this specification treats the database structure as stable.

### 1.6 Observed Usage Patterns

Recent Hermes sessions show these real workflows:

- Telegram expense capture for trip/family contexts.
- Notion workspace audit under Personal AI OS.
- Task capture into Notion.
- Film/media related skills.
- Topic auto-renaming based on conversations.

This confirms the OS should prioritize capture, classification, linking, planning, and review before advanced autonomy.

### 1.7 Current Risks

- Personal OS logic is mixed into upstream Hermes code.
- No clear separation between agent prompts, automation definitions, and integration adapters.
- Cron is unused, so scheduled routines are not yet formalized.
- Notion schema knowledge is spread across skills, scripts, memory, and custom tools.
- `notion_task_create` is narrow and hardcoded to one database.
- Some skills instruct MCP first while others use direct API scripts, creating inconsistent integration paths.
- Long Telegram responses can hit flood control.
- Vision/auxiliary provider errors appear in logs when provider configuration is incomplete.
- No explicit domain-level event bus, audit trail, or idempotency model exists yet.

## 2. Overall Architecture

### 2.1 Target Model

```text
User
  |
  v
Telegram / ChatGPT / Claude Code / Future Interfaces
  |
  v
Hermes Gateway
  |
  v
Personal AI OS Orchestrator
  |
  +--> Agents
  +--> Automations
  +--> Integrations
  |
  v
Notion Source of Truth
  |
  v
Logs / Events / Artifacts / Review Queues
```

### 2.2 Architectural Boundary

Hermes responsibilities:

- Messaging transport.
- Telegram delivery and topic management.
- Tool execution runtime.
- MCP startup and access.
- Session persistence.
- Cron runner, if used.

Personal AI OS responsibilities:

- Domain routing.
- Agent definitions.
- Automation library.
- Prompt library.
- Notion schema contracts.
- Event model.
- Integration adapters.
- Error policies.
- Audit logs.
- Deployment configuration.

Notion responsibilities:

- Source of truth for inbox, tasks, projects, areas, resources, knowledge, reviews, entertainment, system settings.
- Human-readable state.
- Manual override surface.

## 3. Required Repositories

### 3.1 `hermes-agent`

Existing upstream runtime. Should remain as close to upstream as possible.

Policy:

- Avoid personal code patches inside this repo.
- Keep only minimal configuration.
- Personal tools should move to plugin/integration repo.

### 3.2 `personal-ai-os`

New primary repository for the OS layer.

Contents:

- Agent definitions.
- Automation definitions.
- Prompt library.
- Notion schema contracts.
- Integration adapters.
- Event schemas.
- Tests.
- Deployment assets.
- Documentation.

### 3.3 `personal-ai-os-hermes-plugin`

Optional separate repo or package if Hermes plugin packaging is cleaner than keeping everything in `personal-ai-os`.

Contents:

- Native Hermes tools such as generalized Notion item creation.
- Toolset registrations.
- Hermes skill definitions.
- Telegram command mappings.

### 3.4 `personal-ai-os-infra`

Optional later repository if deployment grows.

Contents:

- systemd units.
- Docker Compose.
- backup scripts.
- secrets templates.
- monitoring config.

For Phase 1, `personal-ai-os` can contain infra docs and templates. Split only when deployment complexity justifies it.

## 4. Folder Structure

Recommended structure for `personal-ai-os`:

```text
personal-ai-os/
├── README.md
├── docs/
│   ├── architecture.md
│   ├── hermes-audit.md
│   ├── notion-contracts.md
│   ├── deployment.md
│   └── operations.md
├── agents/
│   ├── inbox_processor.yaml
│   ├── task_planner.yaml
│   ├── knowledge_curator.yaml
│   ├── resource_importer.yaml
│   ├── weekly_review.yaml
│   ├── research_agent.yaml
│   ├── project_manager.yaml
│   └── personal_assistant.yaml
├── automations/
│   ├── telegram_to_inbox.yaml
│   ├── book_import.yaml
│   ├── movie_import.yaml
│   ├── voice_notes.yaml
│   ├── weekly_review.yaml
│   ├── daily_planning.yaml
│   ├── project_creation.yaml
│   ├── knowledge_linking.yaml
│   ├── task_breakdown.yaml
│   └── resource_classification.yaml
├── integrations/
│   ├── notion/
│   │   ├── contracts/
│   │   ├── client.py
│   │   └── mappers.py
│   ├── telegram/
│   ├── google_drive/
│   ├── github/
│   ├── search/
│   ├── vision/
│   └── ocr/
├── prompts/
│   ├── system/
│   ├── agents/
│   ├── automations/
│   └── shared/
├── events/
│   ├── schemas/
│   └── examples/
├── config/
│   ├── default.yaml
│   ├── production.example.yaml
│   └── secrets.example.env
├── tests/
│   ├── agents/
│   ├── automations/
│   └── integrations/
└── deploy/
    ├── systemd/
    ├── docker/
    └── scripts/
```

## 5. Agent Architecture

### 5.1 Agent Contract

Each agent must define:

- `id`
- `purpose`
- `inputs`
- `outputs`
- `tools`
- `triggers`
- `workflow`
- `prompt`
- `error_policy`
- `future_improvements`

Agents must not directly redesign Notion. They operate against existing Notion contracts.

### 5.2 First Generation Agents

#### 5.2.1 Inbox Processor

Purpose: Convert raw captured input into structured Notion inbox/task/resource/knowledge candidates.

Inputs:

- Telegram text.
- Voice transcription.
- Shared links.
- Screenshots/OCR text.
- ChatGPT/Claude notes.

Outputs:

- Inbox item.
- Task candidate.
- Resource candidate.
- Knowledge note candidate.
- Clarification request when classification is unsafe.

Tools:

- Notion MCP.
- Notion integration adapter.
- Telegram metadata.
- OCR/Vision later.
- Search later.

Triggers:

- New Telegram message.
- New voice note.
- New shared URL.
- Manual command: `/inbox`.

Workflow:

1. Normalize input.
2. Detect intent: task, idea, resource, expense, media, project, knowledge, unknown.
3. Apply deterministic routing rules first.
4. Create/update the correct Notion item.
5. Add source metadata.
6. Return short confirmation.

Prompt:

```text
You are the Inbox Processor for Evgenii's Personal AI OS.
Classify the input into exactly one primary destination: Inbox, Task, Resource, Knowledge, Expense, Media, Project, or Clarification.
Use existing Notion schema contracts. Do not redesign databases.
Prefer creating a lightweight Inbox item when uncertain.
Never claim success without a real Notion operation result.
Return a short Russian confirmation.
```

Future improvements:

- Multi-label classification.
- Confidence scoring.
- Duplicate detection.
- Batch capture.
- Entity extraction from images and documents.

#### 5.2.2 Task Planner

Purpose: Transform tasks into actionable next steps while preserving the existing `Мои задачи` workflow.

Inputs:

- Notion task.
- Inbox item classified as task.
- Project page.
- User command.

Outputs:

- Updated task title.
- Start bucket.
- Optional due date.
- Subtasks/checklist.
- Project relation suggestion.

Tools:

- Notion MCP.
- Task DB contract.
- Project DB contract.

Triggers:

- New task created.
- User asks to break down a task.
- Daily planning automation.

Workflow:

1. Read task.
2. Determine if task is atomic.
3. If too broad, propose subtasks.
4. Assign `Когда начать`.
5. Link project only if project is explicit or high-confidence.
6. Write concise updates.

Prompt:

```text
You are the Task Planner.
Make tasks actionable without over-planning.
Keep task titles short, verb-first, and concrete.
Use existing buckets: Сегодня, На неделе, Потом, На выходных.
Do not invent projects. If project relation is unclear, leave it unlinked or ask.
```

Future improvements:

- Effort estimates.
- Calendar integration.
- Recurring tasks.
- Dependency mapping.

#### 5.2.3 Knowledge Curator

Purpose: Convert useful notes into durable knowledge entries and link them to projects, areas, resources, or tags.

Inputs:

- Inbox note.
- Chat transcript.
- Research result.
- Book/movie/resource notes.

Outputs:

- Knowledge note.
- Links to Areas, Projects, Resources, Tags.
- Summary and extracted claims.

Tools:

- Notion MCP.
- Search.
- Google Drive later.

Triggers:

- Manual command.
- Weekly review.
- Resource import completion.

Workflow:

1. Read source note.
2. Identify durable knowledge vs temporary task.
3. Create/update knowledge entry.
4. Link to relevant existing entities.
5. Preserve source link.

Prompt:

```text
You are the Knowledge Curator.
Extract durable knowledge, not temporary chatter.
Link to existing Areas, Projects, Resources, and Tags when clear.
Do not create new taxonomy unless explicitly requested.
Keep summaries compact and useful for future retrieval.
```

Future improvements:

- Semantic duplicate detection.
- Embeddings/search index.
- Automatic backlinks.
- Citation extraction.

#### 5.2.4 Resource Importer

Purpose: Import external resources into the Resources/Entertainment/Knowledge system.

Inputs:

- URL.
- Book title.
- Movie title.
- PDF/document.
- Google Drive file.

Outputs:

- Resource entry.
- Media entry.
- Extracted metadata.
- Summary.
- Cover/poster when available.

Tools:

- Web search.
- Notion MCP/API.
- Google Drive.
- OCR/Vision.

Triggers:

- Telegram URL.
- Manual import command.
- Google Drive upload.

Workflow:

1. Detect resource type.
2. Fetch metadata.
3. Ask for confirmation when multiple matches exist.
4. Create correct Notion entry.
5. Link to Area/Project if clear.

Prompt:

```text
You are the Resource Importer.
Import resources into the existing Notion system with clean metadata.
For films/books, confirm ambiguous matches before creation.
For articles/videos, create a concise resource entry with source URL and summary.
Never create duplicate entries if an obvious match already exists.
```

Future improvements:

- Readwise-style highlights.
- YouTube transcript extraction.
- PDF full-text import.
- Auto-tagging.

#### 5.2.5 Weekly Review

Purpose: Produce a weekly operating review from Notion state.

Inputs:

- Tasks.
- Projects.
- Areas.
- Inbox.
- Resources.
- Completed items.

Outputs:

- Weekly review page.
- Summary.
- Suggested next actions.
- Stale items list.

Tools:

- Notion MCP.
- Search only if needed.

Triggers:

- Weekly schedule.
- Manual command.

Workflow:

1. Read open tasks and active projects.
2. Read inbox backlog.
3. Identify completed work.
4. Identify stuck projects.
5. Create review note.
6. Ask user to confirm planning changes.

Prompt:

```text
You are the Weekly Review Agent.
Summarize the week from Notion facts only.
Separate facts from suggestions.
Do not reorganize the workspace.
Prioritize clarity: completed, stuck, next, waiting, cleanup.
```

Future improvements:

- Weekly scorecards.
- Area health metrics.
- Calendar recap.
- Automatic recurring review prompts.

#### 5.2.6 Research Agent

Purpose: Research topics and produce source-backed notes or briefs.

Inputs:

- Research question.
- Project context.
- Area context.
- Links/documents.

Outputs:

- Research brief.
- Source list.
- Recommendation or options.
- Follow-up questions.

Tools:

- Web search.
- Google Drive.
- Notion MCP.
- Future specialized search.

Triggers:

- Manual research request.
- Project Manager needs context.
- Resource Importer requests enrichment.

Workflow:

1. Clarify research target if needed.
2. Search reliable sources.
3. Extract findings.
4. Separate evidence, assumptions, and recommendations.
5. Save to Notion if requested or automation requires it.

Prompt:

```text
You are the Research Agent.
Answer with evidence and links.
Mark uncertainty clearly.
Do not turn research into tasks unless asked.
Save outputs as research notes when the request belongs to a Project or Area.
```

Future improvements:

- Deep research mode.
- Source quality scoring.
- Watchlists.
- Multi-step literature review.

#### 5.2.7 Project Manager

Purpose: Maintain active projects without redesigning the workspace.

Inputs:

- Project page.
- Related tasks.
- Inbox items.
- User planning request.

Outputs:

- Project status update.
- Next actions.
- Risks/blockers.
- Suggested task updates.

Tools:

- Notion MCP.
- Task Planner.
- Research Agent.

Triggers:

- Project creation.
- Weekly review.
- Manual command.

Workflow:

1. Read project and related tasks.
2. Determine outcome, status, next actions.
3. Identify stale/missing tasks.
4. Propose changes.
5. Apply only low-risk updates or ask for confirmation.

Prompt:

```text
You are the Project Manager.
Keep projects outcome-oriented and lightweight.
Do not create new Areas or restructure Notion.
For every active project, identify status, next action, blocker, and owner.
Prefer suggestions over edits when the intent is ambiguous.
```

Future improvements:

- Project templates.
- Milestones.
- External GitHub issue linking.
- Progress dashboards.

#### 5.2.8 Personal Assistant

Purpose: Conversational front door that routes user requests to the correct agent, automation, or integration.

Inputs:

- Telegram messages.
- ChatGPT/Claude requests.
- Commands.

Outputs:

- Direct answer.
- Delegated agent run.
- Notion update.
- Clarifying question.

Tools:

- Router.
- All approved agents.
- Notion MCP.
- Telegram.

Triggers:

- Any conversational request.

Workflow:

1. Understand request.
2. Classify as answer, capture, planning, research, import, review, integration action.
3. Delegate or execute.
4. Confirm with concise result.

Prompt:

```text
You are Evgenii's Personal AI OS Assistant.
Route every request to an Agent, Automation, or Integration.
Do not make random workspace changes.
Notion is the source of truth.
When uncertain, capture to Inbox or ask one concise question.
Prefer Russian for confirmations unless the user uses English.
```

Future improvements:

- User preference memory.
- Voice-first interactions.
- Multi-agent orchestration.
- Safety approval modes.

## 6. Automation Architecture

### 6.1 Automation Contract

Each automation must define:

- `id`
- `trigger`
- `input_event`
- `agent`
- `tools`
- `notion_targets`
- `idempotency_key`
- `success_condition`
- `failure_policy`
- `human_confirmation`

### 6.2 First Automation Library

#### Telegram To Inbox

Trigger: New Telegram message that is not an explicit command.

Agent: Inbox Processor.

Flow:

1. Receive message.
2. Classify.
3. Create task/resource/knowledge/inbox item.
4. Confirm in Telegram.

Idempotency: Telegram message ID + chat ID.

#### Book Import

Trigger: Book title, URL, screenshot, or `/book`.

Agent: Resource Importer.

Flow:

1. Search metadata.
2. Confirm match if ambiguous.
3. Create book/resource entry.
4. Link to Resources or Entertainment.

#### Movie Import

Trigger: Movie title, IMDb/Kinopoisk URL, screenshot, or `/movie`.

Agent: Resource Importer.

Flow:

1. Search IMDb/Kinopoisk/OMDB.
2. Ask confirmation for 2-3 candidates.
3. Create media entry.
4. Add poster and metadata.

#### Voice Notes

Trigger: Telegram voice message.

Agent: Inbox Processor.

Flow:

1. Transcribe audio.
2. Classify transcript.
3. Route to task/inbox/resource/knowledge.
4. Include transcript as source.

#### Weekly Review

Trigger: Weekly schedule.

Agent: Weekly Review.

Flow:

1. Read tasks/projects/inbox.
2. Generate weekly review.
3. Create Notion review page.
4. Send Telegram summary.

#### Daily Planning

Trigger: Daily schedule or morning Telegram command.

Agent: Task Planner.

Flow:

1. Read `Сегодня` and overdue tasks.
2. Suggest realistic plan.
3. Ask for confirmation before changing task buckets.

#### Project Creation

Trigger: Inbox item or user says “создай проект”.

Agent: Project Manager.

Flow:

1. Validate it is truly a project.
2. Ask for outcome if missing.
3. Create project entry.
4. Create initial tasks if confirmed.

#### Knowledge Linking

Trigger: New knowledge note/resource or weekly review.

Agent: Knowledge Curator.

Flow:

1. Find related Areas/Projects/Tags.
2. Suggest or apply links.
3. Avoid creating new taxonomy without approval.

#### Task Breakdown

Trigger: Task marked too broad, manual request, or project creation.

Agent: Task Planner.

Flow:

1. Read parent task/project.
2. Generate subtasks.
3. Ask for confirmation.
4. Create/update tasks.

#### Resource Classification

Trigger: New Resource entry without type/tag/project.

Agent: Resource Importer + Knowledge Curator.

Flow:

1. Classify type.
2. Add metadata.
3. Link to Area/Project.
4. Create summary if needed.

## 7. MCP Integrations

### 7.1 Notion MCP

Current state: enabled.

Purpose:

- Search pages/databases.
- Read page/database content.
- Create/update pages.
- Query data sources.

Policy:

- MCP is preferred for standard Notion operations.
- Direct API is acceptable when MCP lacks endpoint support or has token/cache issues.
- Integration adapters must abstract this choice.

### 7.2 Google Drive MCP / Connector

Future role:

- Import PDFs, Docs, Sheets.
- Attach Drive source metadata to Resources/Knowledge.
- Support OCR/document extraction.

### 7.3 GitHub

Future role:

- Store OS code.
- Track implementation issues.
- Link technical projects to Notion.
- Maintain deployment workflows.

### 7.4 Search / Vision / OCR

Future role:

- OCR screenshots.
- Analyze documents/images.
- Enrich resources.
- Extract receipts, books, movies, products.

## 8. Event Flow

### 8.1 Telegram Capture

```text
Telegram message
  -> Hermes gateway
  -> Personal Assistant router
  -> Inbox Processor
  -> Notion adapter
  -> Notion page created/updated
  -> Event log
  -> Telegram confirmation
```

### 8.2 Scheduled Review

```text
Cron trigger
  -> Weekly Review automation
  -> Weekly Review Agent
  -> Notion queries
  -> Review page
  -> Telegram summary
```

### 8.3 Resource Import

```text
URL/title/file
  -> Resource Importer
  -> Search/metadata extraction
  -> Confirmation if ambiguous
  -> Notion Resource/Entertainment entry
  -> Optional Knowledge Curator
```

## 9. Data Flow

### 9.1 Source Data

- Telegram messages.
- Voice transcripts.
- URLs.
- Files.
- Google Drive docs.
- ChatGPT/Claude outputs.
- Manual Notion edits.

### 9.2 Processing Data

- Event metadata.
- Classification result.
- Agent decision.
- Tool calls.
- Confidence.
- Error state.

### 9.3 Durable Data

- Notion pages/databases.
- Event log.
- Agent run log.
- Imported files/artifacts.
- Prompt versions.

### 9.4 Idempotency

Every automation should write an idempotency key:

- Telegram: `telegram:{chat_id}:{message_id}`
- Drive: `gdrive:{file_id}:{revision_id}`
- URL: `url:{normalized_url_hash}`
- Schedule: `schedule:{automation_id}:{date}`

## 10. Prompt Library

Prompt structure:

```text
prompts/
├── system/
│   ├── os_router.md
│   ├── notion_contract.md
│   └── safety.md
├── agents/
│   ├── inbox_processor.md
│   ├── task_planner.md
│   ├── knowledge_curator.md
│   ├── resource_importer.md
│   ├── weekly_review.md
│   ├── research_agent.md
│   ├── project_manager.md
│   └── personal_assistant.md
├── automations/
│   ├── telegram_to_inbox.md
│   └── weekly_review.md
└── shared/
    ├── russian_confirmation_style.md
    ├── no_false_success.md
    └── no_workspace_redesign.md
```

Shared prompt rules:

- Notion is source of truth.
- Do not redesign workspace.
- Do not claim success without tool result.
- Prefer capture to Inbox when uncertain.
- Every action belongs to Agent, Automation, or Integration.
- Keep Telegram replies short to avoid flood control.

## 11. Deployment Strategy

### 11.1 Phase 1

Documentation only.

Outputs:

- Hermes audit.
- OS architecture.
- Agent specs.
- Automation specs.
- Integration map.
- Repository plan.

### 11.2 Phase 2

Create `personal-ai-os` repository.

Actions:

- Move specs into repo.
- Define Notion contracts.
- Extract existing custom Notion task logic into OS integration.
- Add tests for schema mappers.

### 11.3 Phase 3

Hermes integration.

Actions:

- Package native tools as Hermes plugin or installable module.
- Remove direct upstream patches when replacement is stable.
- Add OS router skill.
- Add controlled Telegram commands.

### 11.4 Phase 4

Automations.

Actions:

- Add daily planning.
- Add weekly review.
- Add Telegram to Inbox.
- Add voice note processing.
- Add event log and idempotency.

### 11.5 Phase 5

Scale integrations.

Actions:

- Google Drive import.
- OCR/Vision.
- Search enrichment.
- GitHub project linkage.

## 12. Configuration Management

Use layered config:

```text
default.yaml
production.yaml
.env
systemd environment
Notion System database later, read-only for runtime defaults
```

Required config categories:

- Notion database IDs and data source IDs.
- Telegram allowed users/chats.
- Model/provider selection.
- MCP server commands.
- Agent enable/disable flags.
- Automation schedules.
- Rate limits.
- Logging level.
- Secrets references.

Secrets policy:

- Keep tokens out of prompts and logs.
- Prefer environment variables or secret files.
- Never store raw secrets in Notion.
- Redact tool output.

## 13. Logging

### 13.1 Runtime Logs

Keep Hermes logs:

- `gateway.log`
- `errors.log`
- journald for `hermes-gateway.service`

### 13.2 OS Event Log

Add OS-level event log with fields:

- `event_id`
- `timestamp`
- `source`
- `actor`
- `agent_id`
- `automation_id`
- `input_ref`
- `notion_target`
- `action`
- `status`
- `idempotency_key`
- `error_code`
- `duration_ms`

Storage options:

- Phase 2: local JSONL or SQLite.
- Phase 3+: Notion System database plus local durable log.

### 13.3 User-Facing Logs

For the user, expose:

- What was captured.
- Where it was saved.
- What failed.
- What needs confirmation.

## 14. Error Handling

### 14.1 Error Classes

- Authentication error.
- Notion schema mismatch.
- Missing database access.
- Ambiguous classification.
- Duplicate item.
- Rate limit.
- Model/provider failure.
- Tool unavailable.
- Network timeout.

### 14.2 Policies

- Never claim success without durable result.
- On Notion 401/403: report auth/access issue.
- On Notion 404: report likely integration sharing issue.
- On schema mismatch: stop and report exact missing property.
- On Telegram flood control: send shorter summary and store full result in Notion.
- On ambiguous resource/movie/book: ask confirmation.
- On uncertain classification: create Inbox item, not a task/project.

## 15. Future Scalability

### 15.1 Modular Growth

New capabilities must be added as:

- A new Agent.
- A new Automation.
- A new Integration.

No one-off scripts should become permanent without being wrapped in one of these categories.

### 15.2 Multi-Interface Support

The OS should support:

- Telegram.
- ChatGPT.
- Claude Code.
- GitHub.
- Google Drive.
- Future web dashboard.

### 15.3 Multi-Agent Coordination

Later architecture:

```text
Personal Assistant
  -> Router
  -> Specialist Agent
  -> Integration Adapter
  -> Notion
  -> Event Log
```

### 15.4 Search Layer

Future search index should cover:

- Notion pages.
- Google Drive docs.
- Imported PDFs.
- Web resources.
- Chat/session summaries.

### 15.5 Safety

Introduce approval tiers:

- Read-only.
- Create low-risk item.
- Update existing item.
- Bulk edit.
- Delete/archive.
- External side effect.

Bulk Notion edits, deletions, and workspace layout changes always require explicit approval.

## 16. Implementation Priorities

### Priority 1

- Freeze Notion schema contracts in docs.
- Extract `notion_task_create` from patched Hermes into OS-owned integration/plugin.
- Define OS event log.
- Define Inbox Processor and Personal Assistant router.

### Priority 2

- Telegram to Inbox automation.
- Voice Notes automation.
- Daily Planning automation.
- Task Planner agent.

### Priority 3

- Weekly Review automation.
- Project Manager agent.
- Knowledge Curator agent.
- Resource Importer improvements for books/movies.

### Priority 4

- Google Drive integration.
- OCR/Vision pipeline.
- GitHub integration.
- Search index.

## 17. Non-Goals For Phase 1

- Do not redesign Notion.
- Do not migrate workspace data.
- Do not restart Hermes.
- Do not change VPS config.
- Do not deploy new code.
- Do not create repositories yet.
- Do not add scheduled jobs yet.

## 18. Architecture Decision

The Personal AI OS should be implemented as a domain layer around Hermes, not as ad hoc edits inside Hermes and not as a Notion redesign.

Hermes remains:

- transport,
- runtime,
- tool host,
- MCP host.

Personal AI OS becomes:

- agent library,
- automation library,
- integration layer,
- event system,
- prompt library,
- Notion contract owner.

This preserves the existing working Telegram/Hermes setup while making the system maintainable and extensible.
