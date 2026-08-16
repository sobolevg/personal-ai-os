# Personal AI OS Link Capture

Use this skill when Evgenii sends an Instagram link in Telegram and wants it
captured, summarized, remembered, or saved to Notion.

## Required Hermes Flow

1. Call `personal_ai_os_link_prepare` with the raw Telegram message and the
   stable Telegram message id from platform context.
2. Read both returned `text` (the Instagram author's caption) and `transcript`
   yourself. Treat the caption as primary source context, not as social-media
   noise. Do not call a separate LLM service: the active Hermes model must do
   the distillation.
3. Select one durable idea only. Ignore greetings, repetitions, advertising,
   calls to subscribe, and generic social-media framing.
4. Call `personal_ai_os_link_save` with the returned `capture_id` and the
   structured fields below.
5. Reply with one short confirmation and the returned Notion URL.

If `existing_page_url` is present, do not create a duplicate. Return that URL.

## Zettelkasten Output

Write in Russian:

- `title`: short name of the idea, without emoji or platform name
- `summary`: the essence in one or two sentences
- `topics`: a short list of reusable topics
- `content_type`: the semantic type, for example `exercise`
- `action`: `read|watch|try|buy|do|none`
- `actionability`: `low|medium|high`
- `why_relevant`: concrete usefulness in one or two sentences
- `suggested_area`: area name or null
- `suggested_project`: project name or null
- `reusable_knowledge`: true only when the idea remains useful beyond the post

Do not include a transcript, long retelling, promotional CTA, or extra facts in
the distilled Notion fields. The save tool preserves the author's caption in a
separate collapsed `Описание автора` block. Do not present medical claims as verified facts; use
"автор утверждает" or "может" where appropriate.

## Source Integrity

- Never rewrite, shorten, canonicalize, or replace the returned `source_url`.
- Never pass `source_url` to `personal_ai_os_link_save`; that tool deliberately
  has no source URL parameter.
- The save tool loads the exact original URL from server-owned capture state.
- `canonical_url`, media URLs, PLAUD URLs, and thumbnails are never substitutes
  for the original source.

## Failure Handling

- If metadata or transcript is unavailable, still save a minimal source-backed
  note when the returned `source_url` exists.
- Mention missing transcription briefly in the confirmation.
- Never use browser login bypasses, CAPTCHAs, copied cookies, or private media
  access to recover content.
