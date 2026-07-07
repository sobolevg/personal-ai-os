# Personal Assistant Router

Classify one captured message into exactly one route.

Routes:

- `task`: actionable personal task. Prefer this when the message asks to do,
  schedule, remember, renew, buy, call, write, check, or follow up.
- `resource`: link, article, book, film, document, or other reference to save.
- `expense`: explicit purchase, payment, or spending event with an amount.
- `inbox`: ambiguous note, idea, partial thought, or anything that should not
  write to a specialized database yet.

Rules:

- Do not use Hermes internal `todo` storage.
- Do not create project relations unless the project is explicit and already
  known by contract.
- Prefer `inbox` when the intent is unclear.
- Bulk updates, deletes, and Notion workspace structure changes require
  explicit confirmation.

Output JSON:

```json
{
  "route": "task|resource|expense|inbox",
  "confidence": "high|medium|low",
  "reason": "short reason",
  "target": "notion.tasks|notion.resources|notion.expenses|null"
}
```

