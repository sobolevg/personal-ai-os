# Hermes Link Capture — Phase 1 MVP

## Scope

The service captures links shared with Hermes in Telegram, enriches and
classifies them, and stores them in Notion. Work is intentionally incremental.

This checkpoint implements only:

- normalized data contracts;
- immutable original-source handling;
- URL extraction;
- platform detection;
- provider/client boundaries;
- unit tests for this foundation.

The first provider checkpoint adds conservative Instagram extraction from
metadata exposed in an unauthenticated public HTML response. It does not use
cookies, log in, download media, or bypass access controls. Provider failures
preserve the minimal capture.

When Instagram includes public `video_versions`, the provider records the first
HTTPS media reference from an allow-listed Instagram/Facebook CDN in
`media_url`. This URL is temporary processing input, never a replacement for
`source_url`, and must not be treated as the durable Notion source link.

The next isolated checkpoint adds a provider-neutral transcript result and a
PLAUD Developer API adapter. Transcripts remain separate from captions and
captured metadata. The adapter submits a public media URL, polls boundedly,
maps time-aligned segments, redacts credentials from representations, and does
not log response bodies or authentication headers. Non-idempotent submit calls
are not retried because the provider does not expose an idempotency-key contract;
read-only polling requests use bounded retry.

The PLAUD Developer API currently documents M4A, MP3, and WAV inputs. Instagram
Reels expose MP4 video, so the adapter prepares audio separately. Live tests
with valid credentials and public M4A, MP3, and WAV inputs all returned a PLAUD
server error. Browser-based PLAUD Web transcription is therefore treated as a
replaceable fallback provider, not as pipeline-owned logic.

The PLAUD Web provider runs Playwright in a separate interpreter so the domain
service does not depend on browser packages. It uploads only a prepared local
audio artifact, uses a dedicated persistent profile, serializes concurrent
access with a lock, and returns the same `TranscriptResult` model as other
providers. Authentication is a one-time profile bootstrap and credentials are
never stored in git or passed to the provider process.

The media-preparation boundary now uses FFmpeg to remux the first audio stream
from a provider-validated HTTPS media URL into a randomly named temporary M4A.
It invokes FFmpeg without a shell, applies a hard timeout and output-size cap,
removes partial files after failure, and keeps both `source_url` and `media_url`
outside the prepared artifact model. Publishing the temporary M4A remains a
separate replaceable boundary.

The current Zettelkasten checkpoint adds a strict Russian distillation prompt
and a Notion payload builder. The page contains only the atomic summary,
concrete usefulness, a verification caveat, and a visible original-source
link. Captions and raw transcripts are deliberately excluded from Notion page
content. The `Zettelkasten Core` database schema and one Instagram example page
were verified with a live Notion write.

The Hermes-native checkpoint adds two tools instead of a second LLM client:

- `personal_ai_os_link_prepare` preserves capture identity, enriches the
  Instagram URL, prepares audio, and returns the PLAUD transcript;
- the active Hermes model distills that result using the installed link-capture
  skill;
- `personal_ai_os_link_save` validates the strict classification and writes the
  Notion page from server-owned capture state.

The save tool deliberately has no `source_url` parameter. Retries use a stable
`capture_id`, and the exact source URL and first `saved_at` value are loaded
from mode-0600 state on the VPS. The transcript is removed from that state
after a successful Notion write.

Telegram exposure and automatic Notion writes remain separately gated by
deployment configuration until the runtime smoke test is approved.

## Module Structure

```text
services/link_capture/
├── models.py
├── capture_state.py
├── workflow.py
├── url_detection.py
├── config.py
├── extraction/
│   ├── base.py
│   ├── http.py
│   ├── registry.py
│   └── providers/instagram.py
├── media/
│   ├── base.py
│   └── ffmpeg.py
├── transcription/
│   ├── base.py
│   ├── plaud.py
│   ├── plaud_web.py
│   ├── plaud_web_login.py
│   └── plaud_web_runner.py
├── classification.py
├── notion.py
└── telegram.py
```

Concrete platform providers will be added behind `ContentExtractor`. A provider
failure must result in an empty `ContentEnrichment`, not loss of the captured
record.

## Source Integrity Contract

1. Capture `source_url` and `saved_at` before redirects or network calls.
2. Never pass `source_url` as extractor-owned enrichment data.
3. Store redirect/canonical output in `canonical_url`.
4. Store downloadable or mirrored media in `media_url`.
5. Always map Notion `Original URL` to the captured `source_url`.
6. Always render a visible link to `source_url` in the Notion page body.
7. Continue with the minimal captured record when extraction fails.

## Planned Pipeline

```text
Telegram message handled by Hermes
  -> exact URL capture + platform detection
  -> provider registry + metadata extraction
  -> normalized content
  -> PLAUD Web transcript
  -> active Hermes model creates strict structured classification
  -> server-owned source identity + Notion persistence
  -> Telegram confirmation
```

## Configuration

The future runtime reads the required variables documented in `.env.example`.
Secrets remain outside git. `LinkCaptureSettings` redacts tokens/API keys from
its representation and fails clearly when required values are missing.

## Next Checkpoint

Install the Hermes bridge and skill on the VPS with writes disabled, verify the
two tool schemas in the Telegram toolset, then enable one live Instagram capture
with `PERSONAL_AI_OS_LINK_CAPTURE_EXECUTE_ENABLED=1` and monitor the resulting
Notion page and Telegram confirmation.
