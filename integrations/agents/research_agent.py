"""Draft-only Research Agent runtime."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import re
from typing import Any


PURCHASE_MARKERS = (
    "купить",
    "доставка",
    "доставкой",
    "buy",
    "delivery",
)

RESEARCH_PREFIXES = (
    "research:",
    "исследуй",
    "найди",
    "выбери",
    "подбери",
    "сравни",
    "research",
    "find",
    "compare",
    "choose",
)


@dataclass(frozen=True)
class ResearchBriefDraft:
    title: str
    question: str
    scope: str | None = None
    deadline: str | None = None
    summary: str = ""
    research_type: str = "general"
    search_queries: list[str] = field(default_factory=list)
    evaluation_criteria: list[str] = field(default_factory=list)
    missing_inputs: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)
    sources: list[dict[str, str]] = field(default_factory=list)
    needs_live_research: bool = True
    needs_confirmation: bool = True
    write_policy: str = "draft_only"
    target: str = "notion.research"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def draft_research_brief(
    question: str,
    scope: str | None = None,
    deadline: str | None = None,
) -> ResearchBriefDraft:
    normalized_question = _normalize(question)
    normalized_scope = _normalize(scope) or None
    normalized_deadline = _normalize(deadline) or None
    topic = _extract_topic(normalized_question)
    research_type = _research_type(normalized_question)

    return ResearchBriefDraft(
        title=_title_from_topic(topic),
        question=normalized_question,
        scope=normalized_scope,
        deadline=normalized_deadline,
        summary=_summary(topic, research_type),
        research_type=research_type,
        search_queries=_search_queries(topic, research_type),
        evaluation_criteria=_evaluation_criteria(research_type),
        missing_inputs=_missing_inputs(normalized_question, research_type),
        open_questions=_open_questions(topic, research_type),
        next_actions=_next_actions(topic, research_type),
        sources=[],
    )


def _normalize(value: str | None) -> str:
    return " ".join((value or "").strip().split())


def _extract_topic(text: str) -> str:
    lowered = text.lower()
    for prefix in RESEARCH_PREFIXES:
        if lowered.startswith(prefix):
            return text[len(prefix) :].strip(" :-")
    return text.strip(" :-")


def _title_from_topic(topic: str) -> str:
    if not topic:
        return "Research brief"
    title = topic[:80].strip()
    return title[:1].upper() + title[1:]


def _research_type(question: str) -> str:
    lowered = question.lower()
    if any(marker in lowered for marker in PURCHASE_MARKERS):
        return "purchase"
    return "general"


def _summary(topic: str, research_type: str) -> str:
    if research_type == "purchase":
        return f"Purchase research draft for: {topic}."
    return f"Research brief draft for: {topic}."


def _search_queries(topic: str, research_type: str) -> list[str]:
    cleaned = re.sub(r"\s+", " ", topic).strip()
    if not cleaned:
        return []
    if research_type == "purchase":
        return [
            cleaned,
            f"{cleaned} price comparison",
            f"{cleaned} delivery return policy",
        ]
    return [cleaned, f"{cleaned} overview", f"{cleaned} best sources"]


def _evaluation_criteria(research_type: str) -> list[str]:
    if research_type == "purchase":
        return [
            "availability",
            "total price including delivery",
            "delivery date and destination fit",
            "return policy",
            "seller reliability",
        ]
    return ["source credibility", "recency", "relevance", "uncertainty"]


def _missing_inputs(question: str, research_type: str) -> list[str]:
    if research_type != "purchase":
        return []

    lowered = question.lower()
    missing = []
    if not re.search(r"\b\d{2,3}\b", question):
        missing.append("size")
    if "достав" in lowered or "delivery" in lowered:
        if not any(token in lowered for token in ("дом", "home", "cyprus", "кипр", "город")):
            missing.append("delivery city or address area")
    else:
        missing.append("delivery preference")
    if not any(token in lowered for token in ("€", "$", "eur", "usd", "бюджет", "budget")):
        missing.append("budget")
    return missing


def _open_questions(topic: str, research_type: str) -> list[str]:
    if research_type == "purchase":
        return [
            f"What constraints matter most for buying: {topic}?",
            "Should the agent optimize for fastest delivery, lowest total price, or easiest returns?",
        ]
    return [f"What answer would make this research complete: {topic}?"]


def _next_actions(topic: str, research_type: str) -> list[str]:
    if research_type == "purchase":
        return [
            f"Confirm missing purchase constraints for: {topic}",
            "Run live web research after confirmation.",
            "Prepare top options with links, delivery, returns, and recommendation.",
        ]
    return [f"Run live research for: {topic}"]
