"""Build safe dispatch plans for routed capture messages."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from integrations.routing.capture_router import (
    ROUTE_EXPENSE,
    ROUTE_INBOX,
    ROUTE_KNOWLEDGE,
    ROUTE_RESEARCH,
    ROUTE_RESOURCE,
    ROUTE_TASK,
    CaptureRoute,
    route_capture_message,
)

ACTION_NOTION_TASK_CREATE = "notion_task_create"
ACTION_RESOURCE_CANDIDATE = "resource_candidate"
ACTION_EXPENSE_CANDIDATE = "expense_candidate"
ACTION_KNOWLEDGE_CANDIDATE = "knowledge_candidate"
ACTION_RESEARCH_BRIEF = "research_brief"
ACTION_INBOX_CANDIDATE = "inbox_candidate"

WRITE_CREATE_ONLY = "create_only"
WRITE_DRAFT_ONLY = "draft_only"


@dataclass(frozen=True)
class CaptureDispatchPlan:
    route: str
    action: str
    write_policy: str
    normalized_text: str
    confidence: str
    target: str | None
    source_platform: str | None = None
    source_message_id: str | None = None
    needs_confirmation: bool = False

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def build_capture_dispatch_plan(
    message: str | None,
    source_platform: str | None = None,
    source_message_id: str | None = None,
) -> CaptureDispatchPlan:
    route = route_capture_message(message)
    return dispatch_for_route(
        route,
        source_platform=source_platform,
        source_message_id=source_message_id,
    )


def dispatch_for_route(
    route: CaptureRoute,
    source_platform: str | None = None,
    source_message_id: str | None = None,
) -> CaptureDispatchPlan:
    if route.route == ROUTE_TASK and route.confidence == "high":
        return CaptureDispatchPlan(
            route=route.route,
            action=ACTION_NOTION_TASK_CREATE,
            write_policy=WRITE_CREATE_ONLY,
            normalized_text=route.normalized_text,
            confidence=route.confidence,
            target=route.target,
            source_platform=source_platform,
            source_message_id=source_message_id,
        )

    if route.route == ROUTE_RESOURCE:
        return _candidate_plan(
            route=route,
            action=ACTION_RESOURCE_CANDIDATE,
            source_platform=source_platform,
            source_message_id=source_message_id,
        )

    if route.route == ROUTE_EXPENSE:
        return _candidate_plan(
            route=route,
            action=ACTION_EXPENSE_CANDIDATE,
            source_platform=source_platform,
            source_message_id=source_message_id,
        )

    if route.route == ROUTE_KNOWLEDGE:
        return _candidate_plan(
            route=route,
            action=ACTION_KNOWLEDGE_CANDIDATE,
            source_platform=source_platform,
            source_message_id=source_message_id,
        )

    if route.route == ROUTE_RESEARCH:
        return _candidate_plan(
            route=route,
            action=ACTION_RESEARCH_BRIEF,
            source_platform=source_platform,
            source_message_id=source_message_id,
        )

    return _candidate_plan(
        route=route,
        action=ACTION_INBOX_CANDIDATE,
        source_platform=source_platform,
        source_message_id=source_message_id,
    )


def _candidate_plan(
    route: CaptureRoute,
    action: str,
    source_platform: str | None,
    source_message_id: str | None,
) -> CaptureDispatchPlan:
    return CaptureDispatchPlan(
        route=route.route,
        action=action,
        write_policy=WRITE_DRAFT_ONLY,
        normalized_text=route.normalized_text,
        confidence=route.confidence,
        target=route.target,
        source_platform=source_platform,
        source_message_id=source_message_id,
        needs_confirmation=route.confidence == "low",
    )
