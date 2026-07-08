from __future__ import annotations

import unittest

from integrations.agents.research_agent import draft_research_brief


class ResearchAgentRuntimeTest(unittest.TestCase):
    def test_purchase_request_becomes_purchase_research_draft(self) -> None:
        draft = draft_research_brief(
            "купить белые кроссовки Nike размер 43 с доставкой домой"
        )

        self.assertEqual(draft.title, "Купить белые кроссовки Nike размер 43 с доставкой домой")
        self.assertEqual(draft.research_type, "purchase")
        self.assertEqual(draft.write_policy, "draft_only")
        self.assertEqual(draft.target, "notion.research")
        self.assertTrue(draft.needs_live_research)
        self.assertTrue(draft.needs_confirmation)
        self.assertIn("budget", draft.missing_inputs)
        self.assertNotIn("size", draft.missing_inputs)
        self.assertIn("total price including delivery", draft.evaluation_criteria)
        self.assertIn("delivery return policy", draft.search_queries[-1])

    def test_purchase_request_without_size_records_missing_size(self) -> None:
        draft = draft_research_brief("найди белые кроссовки Nike с доставкой")

        self.assertEqual(draft.research_type, "purchase")
        self.assertIn("size", draft.missing_inputs)

    def test_general_research_request_uses_source_criteria(self) -> None:
        draft = draft_research_brief("исследуй local-first agents")

        self.assertEqual(draft.title, "Local-first agents")
        self.assertEqual(draft.research_type, "general")
        self.assertEqual(draft.missing_inputs, [])
        self.assertIn("source credibility", draft.evaluation_criteria)
        self.assertIn("local-first agents overview", draft.search_queries)

    def test_draft_serializes_to_dict(self) -> None:
        draft = draft_research_brief("research: personal ai os agent architecture")

        payload = draft.to_dict()

        self.assertEqual(payload["write_policy"], "draft_only")
        self.assertEqual(payload["target"], "notion.research")
        self.assertEqual(payload["title"], "Personal ai os agent architecture")
