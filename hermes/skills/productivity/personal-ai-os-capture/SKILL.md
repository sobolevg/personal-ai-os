# Personal AI OS Capture

Use this skill when Evgenii sends a short Telegram capture that should enter
Personal AI OS as a planned event rather than being answered from memory.

This includes:

- personal tasks and reminders
- durable notes
- ideas
- "think about this" prompts
- knowledge candidates
- research requests
- purchase research such as "find/buy/choose X with delivery"
- links or resources to classify later
- ambiguous inbox captures

Examples:

- `идея для будущей системы с недельными обзорами`
- `заметка: local-first agents need rollback points`
- `подумать над personal ai os как системой агентов вокруг Hermes`
- `think about how weekly review should work`
- `найди белые кроссовки Nike размер 43 с доставкой домой`
- `купить белые кроссовки Nike размер 43`
- `choose the best monitor for a home office`
- `todo: купить лампочки`
- `https://example.com/article about home server backups`

## Required Tool Routing

For ordinary Telegram capture messages from Evgenii, use:

```text
personal_ai_os_telegram_capture
```

Call it with:

- `message`: the raw Telegram message text
- `source_message_id`: the stable Telegram message id from the platform context
- `execute`: `false`

The tool handles routing internally:

- task captures become `notion_task_create` planned events
- note, idea, and "think about" captures become `knowledge_candidate` planned
  events with Knowledge Curator draft metadata
- find, compare, choose, buy, and delivery captures become `research_brief`
  planned events with Research Agent draft metadata
- links become resource candidates
- unclear messages become inbox candidates

While `PERSONAL_AI_OS_CAPTURE_EXECUTE_ENABLED` is unset, this path writes only
planned events to the Personal AI OS event log. It does not write to Notion.

Do not use `session_search`, `terminal`, `execute_code`, raw Notion MCP, or
Hermes internal `todo` for ordinary Telegram capture messages.

## Boundaries

- Do not redesign the Notion workspace.
- Do not create knowledge pages directly.
- Do not run external research inside the capture step. The capture step should
  create a `research_brief` draft and list missing inputs or next actions.
- Keep all knowledge outputs as draft candidates until confirmation/write
  contracts exist.

## Confirmation

After planning succeeds, answer briefly that the capture was planned and not
written to Notion. If the route is `knowledge`, mention that a Knowledge Curator
draft was attached.
