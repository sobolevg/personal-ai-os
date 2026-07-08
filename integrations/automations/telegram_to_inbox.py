"""Runtime-safe orchestration for Telegram capture messages."""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import replace
import json
import os
from pathlib import Path
from typing import Any, Callable

from integrations.agents.knowledge_curator import curate_knowledge_candidate
from integrations.agents.research_agent import draft_research_brief
from integrations.events.event_log import (
    JsonlEventStore,
    PersonalAIEvent,
    plan_event_from_dispatch,
)
from integrations.notion.task_capture import DEFAULT_BUCKET
from integrations.routing.capture_dispatch import (
    ACTION_NOTION_TASK_CREATE,
    ACTION_KNOWLEDGE_CANDIDATE,
    ACTION_RESEARCH_BRIEF,
    WRITE_CREATE_ONLY,
    CaptureDispatchPlan,
    build_capture_dispatch_plan,
)

try:  # pragma: no cover - local tests inject a fake task creator.
    from hermes.tools.notion_task_create import notion_task_create
except Exception:  # pragma: no cover
    notion_task_create = None

TaskCreator = Callable[..., str]
DEFAULT_EVENT_LOG_RELATIVE_PATH = "personal-ai-os/events/events.jsonl"


@dataclass(frozen=True)
class TelegramCaptureResult:
    dispatch_plan: CaptureDispatchPlan
    event: PersonalAIEvent
    should_execute_action: bool
    confirmation_text: str
    execution_event: PersonalAIEvent | None = None
    action_result: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "dispatch_plan": self.dispatch_plan.to_dict(),
            "event": self.event.to_dict(),
            "should_execute_action": self.should_execute_action,
            "confirmation_text": self.confirmation_text,
            "execution_event": (
                self.execution_event.to_dict() if self.execution_event else None
            ),
            "action_result": self.action_result,
        }


def plan_telegram_capture(
    message: str,
    source_message_id: str,
    event_store_path: str | Path | None = None,
    source_platform: str = "telegram",
) -> TelegramCaptureResult:
    dispatch_plan = build_capture_dispatch_plan(
        message=message,
        source_platform=source_platform,
        source_message_id=source_message_id,
    )
    planned_event = _event_from_dispatch_with_agent_draft(dispatch_plan)
    event_store = JsonlEventStore(resolve_event_store_path(event_store_path))
    recorded_event = event_store.record_event(planned_event)
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


def execute_telegram_capture(
    message: str,
    source_message_id: str,
    event_store_path: str | Path | None = None,
    source_platform: str = "telegram",
    task_creator: TaskCreator | None = None,
) -> TelegramCaptureResult:
    resolved_event_store_path = resolve_event_store_path(event_store_path)
    result = plan_telegram_capture(
        message=message,
        source_message_id=source_message_id,
        event_store_path=resolved_event_store_path,
        source_platform=source_platform,
    )
    if not result.should_execute_action:
        return result

    creator = task_creator or notion_task_create
    store = JsonlEventStore(resolved_event_store_path)
    if creator is None:
        execution_event = store.record_outcome(
            result.event,
            status="failed",
            error="notion_task_create is not available",
        )
        return _replace_result(
            result,
            execution_event=execution_event,
            confirmation_text="Task creation failed.",
        )

    try:
        action_result = _parse_task_creator_result(
            creator(
                title=_task_title_from_dispatch(result.dispatch_plan),
                bucket=DEFAULT_BUCKET,
                comment=None,
            )
        )
    except Exception as error:
        execution_event = store.record_outcome(
            result.event,
            status="failed",
            error=str(error),
        )
        return _replace_result(
            result,
            execution_event=execution_event,
            confirmation_text="Task creation failed.",
        )

    if action_result.get("success") is not True:
        execution_event = store.record_outcome(
            result.event,
            status="failed",
            error=str(action_result.get("error") or "task creator returned no success"),
            metadata={"action_result": action_result},
        )
        return _replace_result(
            result,
            action_result=action_result,
            execution_event=execution_event,
            confirmation_text="Task creation failed.",
        )

    execution_event = store.record_outcome(
        result.event,
        status="executed",
        notion_page_id=_string_or_none(action_result.get("id")),
        metadata={"action_result": action_result},
    )
    return _replace_result(
        result,
        action_result=action_result,
        execution_event=execution_event,
        should_execute_action=False,
        confirmation_text="Task created.",
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


def _event_from_dispatch_with_agent_draft(
    dispatch_plan: CaptureDispatchPlan,
) -> PersonalAIEvent:
    event = plan_event_from_dispatch(dispatch_plan)
    if dispatch_plan.action != ACTION_KNOWLEDGE_CANDIDATE:
        if dispatch_plan.action != ACTION_RESEARCH_BRIEF:
            return event

        draft = draft_research_brief(dispatch_plan.normalized_text)
        return replace(
            event,
            metadata={
                **event.metadata,
                "agent": "research_agent",
                "research_brief": draft.to_dict(),
            },
        )

    draft = curate_knowledge_candidate(dispatch_plan.normalized_text)
    return replace(
        event,
        metadata={
            **event.metadata,
            "agent": "knowledge_curator",
            "knowledge_candidate": draft.to_dict(),
        },
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


def resolve_event_store_path(event_store_path: str | Path | None = None) -> Path:
    if event_store_path is not None:
        return Path(event_store_path)

    env_path = os.environ.get("PERSONAL_AI_OS_EVENT_LOG_PATH")
    if env_path:
        return Path(env_path)

    hermes_home = Path(os.environ.get("HERMES_HOME", "/root/.hermes"))
    return hermes_home / DEFAULT_EVENT_LOG_RELATIVE_PATH


def _replace_result(
    result: TelegramCaptureResult,
    should_execute_action: bool | None = None,
    confirmation_text: str | None = None,
    execution_event: PersonalAIEvent | None = None,
    action_result: dict[str, Any] | None = None,
) -> TelegramCaptureResult:
    return TelegramCaptureResult(
        dispatch_plan=result.dispatch_plan,
        event=result.event,
        should_execute_action=(
            result.should_execute_action
            if should_execute_action is None
            else should_execute_action
        ),
        confirmation_text=confirmation_text or result.confirmation_text,
        execution_event=execution_event,
        action_result=action_result,
    )


def _parse_task_creator_result(raw_result: str) -> dict[str, Any]:
    result = json.loads(raw_result)
    if not isinstance(result, dict):
        raise ValueError("task creator returned non-object JSON")
    return result


def _task_title_from_dispatch(dispatch_plan: CaptureDispatchPlan) -> str:
    title = dispatch_plan.normalized_text
    for prefix in ("todo:", "task:", "задача:"):
        if title.lower().startswith(prefix):
            return title[len(prefix) :].strip()
    return title


def _string_or_none(value: object) -> str | None:
    if value is None:
        return None
    return str(value)
