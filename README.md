# Personal AI OS

Personal AI OS is the domain layer for personal agents, automations, prompts,
Notion contracts, and Hermes extensions.

## Guiding Decision

All durable code, configuration templates, prompts, agent definitions,
automation definitions, deployment scripts, and documentation live in git.

The VPS is a deployment target, not the source of truth.

```text
Git repository -> reviewed commit -> tagged release -> deployed to VPS
```

Personal data remains in Notion. Hermes remains the messaging, runtime, and
tool gateway. Personal AI OS owns the domain layer:

- agents
- automations
- integrations
- prompts
- Notion contracts
- Hermes-owned extension points
- deployment and rollback documentation

## Phase 0 Status

This repository starts as a documentation baseline. No production behavior is
changed by this baseline.

Current baseline docs:

- `docs/00-hermes-audit.md`
- `docs/01-architecture.md`
- `docs/02-implementation-roadmap.md`
- `docs/03-notion-contracts.md`
- `docs/04-deployment.md`
- `docs/05-operations.md`
- `docs/08-deployment-log.md`

## First Milestone

Move the current `notion_task_create` capability out of patched Hermes runtime
code and into a versioned OS-owned Hermes extension with tests.

Definition of done:

- current behavior reproduced in this repo
- tests cover task capture payloads
- deployment notes exist
- rollback command exists
- no secrets are committed
- production deployment is explicit

Current status: first Hermes bridge deployment completed and recorded in
`docs/08-deployment-log.md`.

## Local Verification

```bash
python3 -m unittest discover
```

## Repository Rules

- `main` must remain deployable.
- Every feature gets a branch.
- Every deployable checkpoint gets a tag.
- Every deployment gets rollback notes.
- Real secrets never live in git.
- Notion bulk edits require explicit approval.
