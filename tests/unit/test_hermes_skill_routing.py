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
        self.assertIn("Knowledge Curator", skill_text)
        self.assertIn("Do not use `session_search`", skill_text)


if __name__ == "__main__":
    unittest.main()
