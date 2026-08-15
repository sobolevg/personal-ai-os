"""LLM classification boundary and the Zettelkasten distillation prompt."""

from __future__ import annotations

from typing import Protocol

from services.link_capture.models import (
    ContentClassification,
    NormalizedContent,
    TranscriptResult,
)


ZETTELKASTEN_SYSTEM_PROMPT = """\
Ты редактор атомарных Zettelkasten-заметок для личной базы знаний.
Выдели только одну главную идею материала. Игнорируй приветствия, повторы,
призывы подписаться, рекламу и подробный пересказ. Пиши по-русски.

Верни только JSON строго по схеме:
{
  "title": "короткое название идеи",
  "summary": "суть в 1-2 предложениях",
  "topics": ["тема"],
  "content_type": "тип материала",
  "action": "read|watch|try|buy|do|none",
  "actionability": "low|medium|high",
  "why_relevant": "конкретно чем идея полезна в 1-2 предложениях",
  "suggested_area": null,
  "suggested_project": null,
  "reusable_knowledge": true
}

Не добавляй source_url или другие поля. Не выдавай утверждения автора за
проверенные факты: для спорных медицинских тезисов используй формулировки
«автор утверждает» или «может».
"""


def build_zettelkasten_user_prompt(
    content: NormalizedContent,
    transcript: TranscriptResult | None = None,
) -> str:
    """Prepare model input while keeping raw material out of Notion output."""
    transcript_text = transcript.text if transcript is not None else ""
    return "\n".join(
        (
            f"Платформа: {content.platform.value}",
            f"Автор: {content.author or 'неизвестен'}",
            f"Заголовок/подпись: {content.title}",
            f"Описание: {content.text}",
            f"Транскрипт: {transcript_text}",
        )
    )


class ContentClassifier(Protocol):
    async def classify(self, content: NormalizedContent) -> ContentClassification: ...
