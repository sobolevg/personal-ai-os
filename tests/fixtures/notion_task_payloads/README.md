# Notion Task Payload Fixtures

These fixtures lock the current `notion_task_create` behavior before extracting
it from patched Hermes runtime code into Personal AI OS.

Each positive case has:

- `<case>.input.json`
- `<case>.expected.json`

Each validation case has:

- `<case>.input.json`
- `<case>.expected_error.json`

The expected payloads mirror the current Hermes patch documented in
`docs/current-hermes-patches.md`.
