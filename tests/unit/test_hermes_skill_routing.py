from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
NOTION_TASKS_SKILL = (
    REPO_ROOT / "hermes" / "skills" / "productivity" / "notion-tasks" / "SKILL.md"
)
PERSONAL_AI_OS_CAPTURE_SKILL = (
    REPO_ROOT
    / "hermes"
    / "skills"
    / "productivity"
    / "personal-ai-os-capture"
    / "SKILL.md"
)
PERSONAL_AI_OS_LINK_CAPTURE_SKILL = (
    REPO_ROOT
    / "hermes"
    / "skills"
    / "productivity"
    / "personal-ai-os-link-capture"
    / "SKILL.md"
)
MAC_WORKER_SKILL = (
    REPO_ROOT / "hermes" / "skills" / "productivity" / "mac-worker" / "SKILL.md"
)


class HermesSkillRoutingTest(unittest.TestCase):
    def test_notion_tasks_prefers_telegram_capture_tool_for_telegram_messages(self) -> None:
        skill_text = NOTION_TASKS_SKILL.read_text(encoding="utf-8")

        self.assertIn("personal_ai_os_telegram_capture", skill_text)
        self.assertIn("execute`: `false`", skill_text)
        self.assertIn("Do not use `terminal`, `execute_code`", skill_text)
        self.assertLess(
            skill_text.index("personal_ai_os_telegram_capture"),
            skill_text.index("notion_task_create"),
        )

    def test_personal_ai_os_capture_skill_routes_knowledge_to_capture_tool(self) -> None:
        skill_text = PERSONAL_AI_OS_CAPTURE_SKILL.read_text(encoding="utf-8")

        self.assertIn("personal_ai_os_telegram_capture", skill_text)
        self.assertIn("knowledge_candidate", skill_text)
        self.assertIn("research_brief", skill_text)
        self.assertIn("Knowledge Curator", skill_text)
        self.assertIn("Research Agent", skill_text)
        self.assertIn("Do not use `session_search`", skill_text)

    def test_link_skill_requires_hermes_model_between_prepare_and_save(self) -> None:
        skill_text = PERSONAL_AI_OS_LINK_CAPTURE_SKILL.read_text(encoding="utf-8")

        self.assertIn("personal_ai_os_link_prepare", skill_text)
        self.assertIn("personal_ai_os_link_save", skill_text)
        self.assertIn("active Hermes model", skill_text)
        self.assertIn("Never pass `source_url`", skill_text)

    def test_mac_worker_skill_routes_natural_language_and_explicit_commands(self) -> None:
        skill_text = MAC_WORKER_SKILL.read_text(encoding="utf-8")

        self.assertIn("передай Codex на моём Mac", skill_text)
        self.assertIn("mac run codex", skill_text)
        self.assertIn("mac_worker_run", skill_text)
        self.assertIn("mac_worker_status", skill_text)
        self.assertIn("mac_worker_stop", skill_text)
        self.assertIn("Do not use `terminal`, `execute_code`", skill_text)


if __name__ == "__main__":
    unittest.main()
