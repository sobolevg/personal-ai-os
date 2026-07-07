# Notion Tasks

Use this skill when Evgenii asks to create, add, record, dictate, or save a
personal task or reminder in Notion.

Examples:

- `создай задачу`
- `добавь задачу`
- `запиши задачу`
- `напомни`
- `на потом`
- `на сегодня`
- `на выходные`
- `add a task`
- `save this as a task`

## Required Tool Routing

### Telegram capture path

For ordinary Telegram task/capture messages from Evgenii, use:

```text
personal_ai_os_telegram_capture
```

Call it with:

- `message`: the raw Telegram message text
- `source_message_id`: the stable Telegram message id from the platform context
- `execute`: `false`

This is the default path for messages such as:

- `todo: купить лампочки`
- `task: renew passport`
- `задача: проверить страховку`
- `добавь задачу ...`
- `запиши задачу ...`
- `на потом ...`

The capture tool writes only a planned event while
`PERSONAL_AI_OS_CAPTURE_EXECUTE_ENABLED` is unset. It must be preferred over
direct task creation for Telegram capture until runtime execution is explicitly
enabled.

Do not use `terminal`, `execute_code`, raw Notion MCP, or Hermes internal `todo`
for ordinary Telegram task/capture messages.

### Direct task creation path

For personal task capture, use the native Hermes tool:

```text
notion_task_create
```

Use `notion_task_create` only when a direct Notion task write is explicitly
intended and the request is not part of the Telegram dry-plan capture rollout.

Do not create personal tasks with generic Notion MCP page creation tools when
`notion_task_create` is available.

Avoid these tools for normal task capture:

```text
mcp_notion_API_post_page
mcp_notion_API_patch_page
mcp_notion_API_query_data_source
```

Use Notion MCP only when the user explicitly asks to inspect, search, update, or
relate existing Notion pages and the native task tool does not cover the request.

## Task Fields

Pass a simple task object to `notion_task_create`:

- `title`: the actual task text, without command phrasing
- `bucket`: one of `Сегодня`, `На неделе`, `Потом`, `На выходных`
- `comment`: optional context that should be preserved

If timing is unclear, use:

```text
Потом
```

If the user mentions priority, project, missing relation data, or other fields
that are not supported by the native tool, keep that information in `comment`.

## Boundaries

This skill is for Evgenii's user-facing Notion tasks.

Do not use Hermes internal planning/todo tools for these tasks. Internal planning
tools are only for the assistant's own execution plan inside the current
conversation.

## Confirmation

After `notion_task_create` succeeds, answer briefly with:

- the created task title
- the bucket
- the Notion URL if the tool returned one

If the native tool fails, report the error plainly and do not silently fall back
to raw Notion MCP page creation unless Evgenii explicitly approves that fallback.
