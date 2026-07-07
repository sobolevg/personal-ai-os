"""Deterministic first-pass router for captured user messages."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re

ROUTE_TASK = "task"
ROUTE_RESOURCE = "resource"
ROUTE_EXPENSE = "expense"
ROUTE_KNOWLEDGE = "knowledge"
ROUTE_INBOX = "inbox"

VALID_ROUTES = (ROUTE_TASK, ROUTE_RESOURCE, ROUTE_EXPENSE, ROUTE_KNOWLEDGE, ROUTE_INBOX)

URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
MONEY_RE = re.compile(
    r"(?<!\w)(?:\d+[.,]?\d*)\s*(?:eur|euro|usd|руб|₽|€|\$)(?!\w)",
    re.IGNORECASE,
)

TASK_MARKERS = (
    "task:",
    "todo:",
    "задача:",
    "todo ",
    "надо ",
    "нужно ",
    "сделать ",
    "запланируй ",
    "напомни ",
    "remind me",
    "need to ",
)

RESOURCE_MARKERS = (
    "resource:",
    "link:",
    "прочитать",
    "посмотреть",
    "сохрани ссылку",
    "save link",
    "read later",
)

KNOWLEDGE_MARKERS = (
    "knowledge:",
    "note:",
    "idea:",
    "мысль:",
    "идея:",
    "идея ",
    "заметка:",
    "заметка ",
    "подумать",
    "think about",
    "research idea",
)

EXPENSE_MARKERS = (
    "expense:",
    "трата:",
    "расход:",
    "купил",
    "купила",
    "заплатил",
    "оплатил",
    "spent",
    "paid",
    "bought",
)


@dataclass(frozen=True)
class CaptureRoute:
    route: str
    confidence: str
    normalized_text: str
    signals: tuple[str, ...]
    target: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def route_capture_message(message: str | None) -> CaptureRoute:
    normalized_text = _normalize(message)
    if not normalized_text:
        return CaptureRoute(
            route=ROUTE_INBOX,
            confidence="low",
            normalized_text="",
            signals=("empty_message",),
        )

    lowered = normalized_text.lower()
    signals: list[str] = []

    has_url = bool(URL_RE.search(normalized_text))
    has_money = bool(MONEY_RE.search(normalized_text))
    task_marker = _first_marker(lowered, TASK_MARKERS)
    resource_marker = _first_marker(lowered, RESOURCE_MARKERS)
    knowledge_marker = _first_marker(lowered, KNOWLEDGE_MARKERS)
    expense_marker = _first_marker(lowered, EXPENSE_MARKERS)

    if expense_marker:
        signals.append(f"expense_marker:{expense_marker}")
    if has_money:
        signals.append("money_amount")
    if task_marker:
        signals.append(f"task_marker:{task_marker}")
    if resource_marker:
        signals.append(f"resource_marker:{resource_marker}")
    if knowledge_marker:
        signals.append(f"knowledge_marker:{knowledge_marker}")
    if has_url:
        signals.append("url")

    if expense_marker and has_money:
        return CaptureRoute(
            route=ROUTE_EXPENSE,
            confidence="high",
            normalized_text=normalized_text,
            signals=tuple(signals),
            target="notion.expenses",
        )

    if task_marker:
        return CaptureRoute(
            route=ROUTE_TASK,
            confidence="high",
            normalized_text=normalized_text,
            signals=tuple(signals),
            target="notion.tasks",
        )

    if knowledge_marker:
        return CaptureRoute(
            route=ROUTE_KNOWLEDGE,
            confidence="medium",
            normalized_text=normalized_text,
            signals=tuple(signals),
            target="notion.knowledge",
        )

    if has_url or resource_marker:
        return CaptureRoute(
            route=ROUTE_RESOURCE,
            confidence="medium" if has_url else "low",
            normalized_text=normalized_text,
            signals=tuple(signals),
            target="notion.resources",
        )

    if has_money:
        return CaptureRoute(
            route=ROUTE_INBOX,
            confidence="low",
            normalized_text=normalized_text,
            signals=tuple(signals + ["ambiguous_money_without_expense_marker"]),
        )

    return CaptureRoute(
        route=ROUTE_INBOX,
        confidence="low",
        normalized_text=normalized_text,
        signals=("no_route_marker",),
    )


def _normalize(message: str | None) -> str:
    return " ".join((message or "").strip().split())


def _first_marker(text: str, markers: tuple[str, ...]) -> str | None:
    for marker in markers:
        if marker in text:
            return marker.strip()
    return None
