"""Draft-only Knowledge Curator runtime."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import re
from typing import Any


RESEARCH_MARKERS = (
    "исследуй",
    "найди",
    "выбери",
    "купить",
    "доставка",
    "research",
    "compare",
    "find",
    "buy",
    "delivery",
)

TOPIC_PREFIXES = (
    "knowledge:",
    "note:",
    "idea:",
    "мысль:",
    "идея:",
    "заметка:",
    "подумать над",
    "подумать о",
    "подумать",
    "think about",
)


@dataclass(frozen=True)
class KnowledgeCandidateDraft:
    title: str
    summary: str
    source_text: str
    source_url: str | None = None
    topic_hint: str | None = None
    durable_ideas: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    suggested_research_queries: list[str] = field(default_factory=list)
    suggested_tasks: list[str] = field(default_factory=list)
    links_to_existing_topics: list[str] = field(default_factory=list)
    needs_research: bool = False
    needs_confirmation: bool = True
    write_policy: str = "draft_only"
    target: str = "notion.knowledge"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def curate_knowledge_candidate(
    source_text: str,
    source_url: str | None = None,
    topic_hint: str | None = None,
) -> KnowledgeCandidateDraft:
    normalized_text = _normalize(source_text)
    topic = _normalize(topic_hint) or _extract_topic(normalized_text)
    title = _title_from_topic(topic)
    needs_research = _needs_research(normalized_text)

    durable_ideas = _durable_ideas(normalized_text, topic)
    open_questions = _open_questions(topic, needs_research)
    suggested_research_queries = (
        _research_queries(topic, normalized_text) if needs_research else []
    )
    suggested_tasks = _suggested_tasks(topic, needs_research)

    return KnowledgeCandidateDraft(
        title=title,
        summary=_summary(topic, normalized_text, needs_research),
        source_text=normalized_text,
        source_url=_normalize(source_url) or None,
        topic_hint=_normalize(topic_hint) or None,
        durable_ideas=durable_ideas,
        open_questions=open_questions,
        suggested_research_queries=suggested_research_queries,
        suggested_tasks=suggested_tasks,
        links_to_existing_topics=_topic_links(topic),
        needs_research=needs_research,
    )


def _normalize(value: str | None) -> str:
    return " ".join((value or "").strip().split())


def _extract_topic(text: str) -> str:
    lowered = text.lower()
    for prefix in TOPIC_PREFIXES:
        if lowered.startswith(prefix):
            return text[len(prefix) :].strip(" :-")
    return text.strip(" :-")


def _title_from_topic(topic: str) -> str:
    if not topic:
        return "Knowledge candidate"
    title = topic[:80].strip()
    return title[:1].upper() + title[1:]


def _needs_research(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in RESEARCH_MARKERS)


def _durable_ideas(text: str, topic: str) -> list[str]:
    ideas = []
    if topic:
        ideas.append(f"Clarify the durable idea around: {topic}.")
    if "?" in text:
        ideas.append("Preserve the question as an explicit open thread.")
    if not ideas:
        ideas.append("Review the captured note and decide whether it belongs in knowledge.")
    return ideas


def _open_questions(topic: str, needs_research: bool) -> list[str]:
    questions = [f"What decision, project, or topic should this connect to: {topic}?"]
    if needs_research:
        questions.append("What external evidence is needed before this becomes durable?")
    return questions


def _research_queries(topic: str, text: str) -> list[str]:
    base = topic or text
    cleaned = re.sub(r"\s+", " ", base).strip()
    if not cleaned:
        return []
    return [
        cleaned,
        f"{cleaned} comparison",
        f"{cleaned} delivery availability",
    ]


def _suggested_tasks(topic: str, needs_research: bool) -> list[str]:
    if needs_research:
        return [f"Research options for: {topic}"]
    return [f"Review and link knowledge note: {topic}"]


def _summary(topic: str, text: str, needs_research: bool) -> str:
    if needs_research:
        return f"Research-backed knowledge draft requested for: {topic or text}."
    return f"Knowledge draft captured for: {topic or text}."


def _topic_links(topic: str) -> list[str]:
    lowered = topic.lower()
    links = []
    if "personal ai os" in lowered or "hermes" in lowered:
        links.append("Personal AI OS")
    if "agent" in lowered or "агент" in lowered:
        links.append("Agents")
    return links
