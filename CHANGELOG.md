# Changelog

## Unreleased

### Added

- Documented current Hermes local patches from the VPS runtime.
- Added fixtures for Notion task payload generation and validation cases.
- Added pure Notion task payload builder with fixture-backed unit tests.
- Added Hermes wrapper for `notion_task_create` with local unit tests.
- Added documented install path and script for the Hermes extension bridge.
- Added deployment log for the first VPS Hermes bridge rollout.
- Added repo-owned Hermes `notion-tasks` skill routing overlay.
- Added install script for Hermes skill overlays.
- Added first-pass capture router with fixed examples for task, resource,
  expense, and inbox routing.
- Added safe dispatch plans for Telegram capture routing without new Notion
  writes for unfinished resource and expense contracts.
- Added the first Personal Assistant agent contract with validation tests.
- Added draft first-generation contracts and prompts for all eight planned
  agents.
- Added draft first-generation contracts and prompts for all ten planned
  automations.
- Added an agent and automation map for the Phase 3 design checkpoint.
- Added a local event log schema, JSONL store, and idempotency helpers.
- Added runtime-safe Telegram capture planning around dispatch and event
  logging.
- Added task execution outcome recording for high-confidence Telegram captures.

### Changed

- Updated the draft task Notion contract to match current
  `notion_task_create` behavior.
- Updated deployment docs to reflect the completed first Hermes bridge rollout.
- Updated Hermes bridge installation to create the canonical
  `tools/notion_task_create.py` module expected by Hermes discovery.
- Updated Hermes bridge installation to define the `notion_task` toolset and
  enable it for Telegram platform config.

## v0.1.0-docs-baseline - 2026-07-06

### Added

- Initial Personal AI OS repository baseline.
- Architecture specification.
- Implementation roadmap.
- Hermes audit summary.
- Initial Notion contract placeholder.
- Deployment and operations placeholders.
- Repository skeleton for agents, automations, integrations, Hermes extensions,
  config, deploy assets, and tests.

### Changed

- No production behavior changed.

### Fixed

- Nothing fixed in this baseline.

### Deployment Notes

- Do not deploy this baseline to the VPS as runtime code.
- Use it as the first source-of-truth checkpoint for future work.

### Rollback Notes

- No rollback needed because no production deployment happened.
