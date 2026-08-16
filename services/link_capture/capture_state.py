"""Durable server-side state for the two-step Hermes link-capture flow."""

from __future__ import annotations

from dataclasses import dataclass, replace
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from tempfile import NamedTemporaryFile
from typing import Any

from services.link_capture.models import NormalizedContent, SourcePlatform


_CAPTURE_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")


def capture_id_for(
    source_platform: str,
    source_message_id: str,
    source_url: str,
) -> str:
    """Return an idempotency key without exposing source data in filenames."""
    if not source_platform.strip():
        raise ValueError("source_platform is required")
    if not source_message_id.strip():
        raise ValueError("source_message_id is required")
    payload = "\0".join((source_platform, source_message_id, source_url))
    return sha256(payload.encode("utf-8")).hexdigest()[:32]


@dataclass(frozen=True, slots=True)
class StoredLinkCapture:
    capture_id: str
    source_message_id: str
    content: NormalizedContent
    status: str = "prepared"
    transcript_text: str | None = None
    transcript_provider: str | None = None
    notion_page_id: str | None = None
    notion_page_url: str | None = None

    def __post_init__(self) -> None:
        _validate_capture_id(self.capture_id)
        if not self.source_message_id:
            raise ValueError("source_message_id is required")
        if self.status not in {"prepared", "saved"}:
            raise ValueError("invalid capture status")
        if self.status == "saved" and not self.notion_page_url:
            raise ValueError("saved capture requires notion_page_url")

    def mark_saved(self, page_id: str | None, page_url: str) -> StoredLinkCapture:
        if not page_url:
            raise ValueError("page_url is required")
        return replace(
            self,
            status="saved",
            transcript_text=None,
            transcript_provider=None,
            notion_page_id=page_id,
            notion_page_url=page_url,
        )

    def with_transcript(self, text: str, provider: str) -> StoredLinkCapture:
        if not text.strip() or not provider.strip():
            raise ValueError("transcript text and provider are required")
        return replace(
            self,
            transcript_text=text,
            transcript_provider=provider,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "capture_id": self.capture_id,
            "source_message_id": self.source_message_id,
            "content": self.content.to_dict(),
            "status": self.status,
            "transcript_text": self.transcript_text,
            "transcript_provider": self.transcript_provider,
            "notion_page_id": self.notion_page_id,
            "notion_page_url": self.notion_page_url,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> StoredLinkCapture:
        raw_content = payload.get("content")
        if not isinstance(raw_content, dict):
            raise ValueError("capture state omitted content")
        content_values = dict(raw_content)
        content_values["platform"] = SourcePlatform(content_values["platform"])
        return cls(
            capture_id=str(payload.get("capture_id", "")),
            source_message_id=str(payload.get("source_message_id", "")),
            content=NormalizedContent(**content_values),
            status=str(payload.get("status", "prepared")),
            transcript_text=_optional_string(payload.get("transcript_text")),
            transcript_provider=_optional_string(payload.get("transcript_provider")),
            notion_page_id=_optional_string(payload.get("notion_page_id")),
            notion_page_url=_optional_string(payload.get("notion_page_url")),
        )


class JsonLinkCaptureStore:
    """Store capture identity in mode-0600 JSON files outside the model context."""

    def __init__(self, root: Path) -> None:
        self.root = root.expanduser().resolve()

    def load(self, capture_id: str) -> StoredLinkCapture | None:
        path = self._path(capture_id)
        if not path.is_file():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("capture state must be a JSON object")
        capture = StoredLinkCapture.from_dict(payload)
        if capture.capture_id != capture_id:
            raise ValueError("capture state id mismatch")
        return capture

    def save(self, capture: StoredLinkCapture) -> None:
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(self.root, 0o700)
        path = self._path(capture.capture_id)
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=self.root,
            prefix=f".{capture.capture_id}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_path = Path(handle.name)
            json.dump(capture.to_dict(), handle, ensure_ascii=False, sort_keys=True)
            handle.write("\n")
        try:
            os.chmod(temp_path, 0o600)
            os.replace(temp_path, path)
        finally:
            temp_path.unlink(missing_ok=True)

    def _path(self, capture_id: str) -> Path:
        _validate_capture_id(capture_id)
        return self.root / f"{capture_id}.json"


def _validate_capture_id(capture_id: str) -> None:
    if not _CAPTURE_ID_PATTERN.fullmatch(capture_id):
        raise ValueError("invalid capture_id")


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    return str(value)
