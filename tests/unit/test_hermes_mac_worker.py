from __future__ import annotations

import json
import unittest

from hermes.tools.mac_worker import mac_worker_run, register_tools


class HermesMacWorkerTest(unittest.TestCase):
    def test_run_defaults_to_codex_without_git_permission(self) -> None:
        requests = []

        def fake_caller(request):
            requests.append(request)
            return {"success": True, "job_id": "a" * 32}

        result = json.loads(
            mac_worker_run("personal-ai-os", "run tests", caller=fake_caller)
        )

        self.assertTrue(result["success"])
        self.assertEqual(requests[0].agent, "codex")
        self.assertFalse(requests[0].allow_commit)
        self.assertFalse(requests[0].allow_push)

    def test_registers_all_worker_operations(self) -> None:
        class FakeRegistry:
            def __init__(self):
                self.calls = []

            def register(self, **kwargs):
                self.calls.append(kwargs)

        registry = FakeRegistry()
        self.assertTrue(register_tools(registry))
        self.assertEqual(
            [call["name"] for call in registry.calls],
            ["mac_worker_run", "mac_worker_status", "mac_worker_stop", "mac_worker_doctor"],
        )
        self.assertTrue(all(call["toolset"] == "mac_worker" for call in registry.calls))


if __name__ == "__main__":
    unittest.main()
