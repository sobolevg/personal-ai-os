"""Runtime-safe orchestration for Telegram capture messages."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from integrations.events.event_log import (
    JsonlEventStore,
    PersonalAIEvent,
    plan_event_from_dispatch,
)
from integrations.routing.capture_dispatch import (
    ACTION_NOTION_TASK_CREATE,
    WRITE_CREATE_ONLY,
    CaptureDispatchPlan,
    build_capture_dispatch_plan,
)


@dataclass(frozen=True)
class TelegramCaptureResult:
    dispatch_plan: CaptureDispatchPlan
    event: PersonalAIEvent
    should_execute_action: bool
    confirmation_text: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "dispatch_plan": self.dispatch_plan.to_dict(),
            "event": self.event.to_dict(),
            "should_execute_action": self.should_execute_action,
            "confirmation_text": self.confirmation_text,
        }


def plan_telegram_capture(
    message: str,
    source_message_id: str,
    event_store_path: str | Path,
    source_platform: str = "telegram",
) -> TelegramCaptureResult:
    dispatch_plan = build_capture_dispatch_plan(
        message=message,
        source_platform=source_platform,
        source_message_id=source_message_id,
    )
    planned_event = plan_event_from_dispatch(dispatch_plan)
    recorded_event = JsonlEventStore(event_store_path).record_event(planned_event)
    should_execute_action = _should_execute_action(dispatch_plan, recorded_event)

    return TelegramCaptureResult(
        dispatch_plan=dispatch_plan,
        event=recorded_event,
        should_execute_action=should_execute_action,
        confirmation_text=_confirmation_text(
            dispatch_plan,
            recorded_event,
            should_execute_action,
        ),
    )


def _should_execute_action(
    dispatch_plan: CaptureDispatchPlan,
    event: PersonalAIEvent,
) -> bool:
    if event.status == "skipped_duplicate":
        return False
    return (
        dispatch_plan.action == ACTION_NOTION_TASK_CREATE
        and dispatch_plan.write_policy == WRITE_CREATE_ONLY
        and not dispatch_plan.needs_confirmation
    )


def _confirmation_text(
    dispatch_plan: CaptureDispatchPlan,
    event: PersonalAIEvent,
    should_execute_action: bool,
) -> str:
    if event.status == "skipped_duplicate":
        return "Already captured."
    if should_execute_action:
        return "Task is ready to create."
    if dispatch_plan.needs_confirmation:
        return "I need confirmation before capturing this."
    return "Captured as a draft candidate."
