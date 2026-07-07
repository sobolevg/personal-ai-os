from __future__ import annotations

import unittest

from integrations.agents.knowledge_curator import curate_knowledge_candidate


class KnowledgeCuratorRuntimeTest(unittest.TestCase):
    def test_thinking_note_becomes_knowledge_draft(self) -> None:
        draft = curate_knowledge_candidate(
            "подумать над personal ai os как системой агентов вокруг Hermes"
        )

        self.assertEqual(
            draft.title,
            "Personal ai os как системой агентов вокруг Hermes",
        )
        self.assertEqual(draft.write_policy, "draft_only")
        self.assertEqual(draft.target, "notion.knowledge")
        self.assertTrue(draft.needs_confirmation)
        self.assertFalse(draft.needs_research)
        self.assertIn("Personal AI OS", draft.links_to_existing_topics)
        self.assertIn("Agents", draft.links_to_existing_topics)

    def test_purchase_research_note_marks_research_needed(self) -> None:
        draft = curate_knowledge_candidate(
            "купить белые кроссовки Nike размер 43 с доставкой домой"
        )

        self.assertTrue(draft.needs_research)
        self.assertGreaterEqual(len(draft.suggested_research_queries), 3)
        self.assertIn(
            "Research options for: купить белые кроссовки Nike размер 43 с доставкой домой",
            draft.suggested_tasks,
        )
        self.assertIn("delivery availability", draft.suggested_research_queries[-1])

    def test_topic_hint_overrides_title_topic(self) -> None:
        draft = curate_knowledge_candidate(
            "заметка: сравнить подходы к локальным агентам",
            topic_hint="Local-first agents",
            source_url="https://example.com/agents",
        )

        self.assertEqual(draft.title, "Local-first agents")
        self.assertEqual(draft.topic_hint, "Local-first agents")
        self.assertEqual(draft.source_url, "https://example.com/agents")

    def test_draft_serializes_to_dict(self) -> None:
        draft = curate_knowledge_candidate("idea: weekly review agent")

        payload = draft.to_dict()

        self.assertEqual(payload["write_policy"], "draft_only")
        self.assertEqual(payload["target"], "notion.knowledge")
        self.assertEqual(payload["title"], "Weekly review agent")
