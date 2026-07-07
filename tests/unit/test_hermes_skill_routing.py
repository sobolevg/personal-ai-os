from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
NOTION_TASKS_SKILL = (
    REPO_ROOT / "hermes" / "skills" / "productivity" / "notion-tasks" / "SKILL.md"
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


if __name__ == "__main__":
    unittest.main()
