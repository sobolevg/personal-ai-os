# Current Hermes Local Patches

Date: 2026-07-06  
Source host: `hermes`  
Source path: `/usr/local/lib/hermes-agent`  
Source git commit: `5aec00f`

## Summary

The installed Hermes runtime currently has personal task-capture behavior patched
directly into the upstream codebase.

Observed `git status --short`:

```text
 M tools/todo_tool.py
 M toolsets.py
?? .install_method
?? tools/notion_task_tool.py
```

The Personal AI OS migration should reproduce the behavior of
`tools/notion_task_tool.py` as an OS-owned Hermes extension, then remove these
runtime patches from the VPS installation after validation.

## Patch: `tools/notion_task_tool.py`

Status: new untracked file in Hermes runtime.

Purpose:

- Adds native tool `notion_task_create`.
- Creates pages in Notion database `Мои задачи`.
- Avoids asking the model to construct raw Notion API payloads.
- Separates user-facing Notion tasks from Hermes internal assistant todo.

Behavior:

- Input:
  - `title`, required
  - `bucket`, optional, defaults to `Потом`
  - `comment`, optional
- Valid buckets:
  - `Сегодня`
  - `На неделе`
  - `Потом`
  - `На выходных`
- Token lookup:
  - `NOTION_TOKEN`
  - `NOTION_API_KEY`
  - fallback to `$HERMES_HOME/.env`, defaulting to `/root/.hermes/.env`
- Notion API endpoint:
  - `POST https://api.notion.com/v1/pages`
  - `Notion-Version: 2022-06-28`

Notion database:

```text
176a0a22-1593-8122-94e7-cdb420698046
```

Notion properties written:

| Property | Type | Value |
| --- | --- | --- |
| `Обезьянопонятная задача` | title | input `title` |
| `Когда начать` | select | input `bucket` |
| `Статус` | select | `В плане` |
| `Сделано?` | checkbox | `false` |
| `Комментарий` | rich_text | input `comment`, only when present |

Returned result:

- JSON string with `success`, `id`, `url`, `title`, `bucket`, and `comment`
- `tool_error(...)` string on validation, missing token, or Notion API failure

Tool schema intent:

- Use for phrases such as `добавь задачу`, `запиши задачу`, `на потом`,
  `на сегодня`, `на выходные`, or English equivalents like `add a task`.
- Do not use for the assistant's private execution plan.

## Patch: `toolsets.py`

Status: modified tracked file in Hermes runtime.

Change:

```diff
 _HERMES_CORE_TOOLS = [
     # Web
     "web_search", "web_extract",
+    # Evgenii personal Notion task capture
+    "notion_task_create",
     # Terminal + process management
     "terminal", "process",
```

Effect:

- Makes `notion_task_create` available through the core Hermes tool list.
- The Phase 1 technical spec observed this as available in `hermes-telegram`,
  `hermes-cron`, and `hermes-cli` toolsets.

Migration note:

- The OS-owned replacement should register the tool without editing upstream
  `toolsets.py` directly, or should generate/apply a documented install step.

## Patch: `tools/todo_tool.py`

Status: modified tracked file in Hermes runtime.

Change:

```diff
-        "Manage your task list for the current session. Use for complex tasks "
-        "with 3+ steps or when the user provides multiple tasks. "
-        "Call with no parameters to read the current list.\n\n"
+        "Manage ONLY the assistant's private execution plan for the current session. "
+        "Use for complex assistant work with 3+ implementation/investigation steps. "
+        "Do NOT use this for user-facing reminders, personal todos, errands, or Notion task capture; "
+        "when Evgenii asks to add/record/dictate a task, use the Notion task workflow/MCP instead. "
+        "Call with no parameters to read the current assistant plan.\n\n"
```

Effect:

- Reduces routing confusion between Hermes internal planning todos and
  user-facing Notion tasks.

Migration note:

- Keep this distinction in Personal AI OS routing prompts and tool
  descriptions.
- Avoid relying on a patched upstream `todo_tool.py` description long term.

## Phase 1 Extraction Target

The first coding task should create an OS-owned equivalent with tests:

```text
integrations/notion/task_capture.py
hermes/tools/notion_task_create.py
tests/unit/test_task_capture.py
```

Minimum behavior to preserve:

- validates non-empty title
- validates bucket enum
- defaults unclear bucket to `Потом`
- supports optional comment
- fails clearly when Notion token is missing
- writes the exact current Notion properties listed above
- returns Notion page id and URL on success

No production deployment should happen until the replacement is tested and a
rollback command is written.
