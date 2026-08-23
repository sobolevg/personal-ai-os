from __future__ import annotations

import json
from pathlib import Path
import re
from tempfile import TemporaryDirectory
import unittest

from services.mac_worker.protocol import WorkerConfig, WorkerRequest, decode_request, encode_request


class MacWorkerProtocolTest(unittest.TestCase):
    def test_round_trip_uses_shell_safe_base64url(self) -> None:
        request = WorkerRequest.from_dict(
            {
                "operation": "run",
                "project": "personal-ai-os",
                "task": "Исправь тесты; $(touch /tmp/nope)",
                "agent": "codex",
            }
        )
        token = encode_request(request)
        restored = decode_request(token)

        self.assertRegex(token, re.compile(r"^[A-Za-z0-9_-]+$"))
        self.assertEqual(restored.task, request.task)
        self.assertFalse(restored.allow_commit)
        self.assertFalse(restored.allow_push)

    def test_push_requires_explicit_commit_permission(self) -> None:
        with self.assertRaisesRegex(ValueError, "requires allow_commit"):
            WorkerRequest.from_dict(
                {
                    "operation": "run",
                    "project": "personal-ai-os",
                    "task": "push",
                    "allow_push": True,
                }
            )

    def test_raw_paths_are_not_valid_project_aliases(self) -> None:
        with self.assertRaisesRegex(ValueError, "project alias"):
            WorkerRequest.from_dict(
                {
                    "operation": "run",
                    "project": "/Users/me/secret",
                    "task": "read it",
                }
            )

    def test_config_rejects_project_outside_allowlist(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            allowed = root / "allowed"
            outside = root / "outside"
            allowed.mkdir()
            outside.mkdir()
            config_path = root / "config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "projects": {"bad": str(outside)},
                        "allow_roots": [str(allowed)],
                        "jobs_dir": str(root / "jobs"),
                        "codex_binary": "/usr/bin/true",
                        "claude_binary": "/usr/bin/true",
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "outside allow_roots"):
                WorkerConfig.load(config_path)

    def test_resolved_symlink_cannot_escape_allowlist(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            allowed = root / "allowed"
            outside = root / "outside"
            allowed.mkdir()
            outside.mkdir()
            (allowed / "linked").symlink_to(outside, target_is_directory=True)
            config_path = root / "config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "projects": {"linked": str(allowed / "linked")},
                        "allow_roots": [str(allowed)],
                        "jobs_dir": str(root / "jobs"),
                        "codex_binary": "/usr/bin/true",
                        "claude_binary": "/usr/bin/true",
                    }
                ),
                encoding="utf-8",
            )
            config = WorkerConfig.load(config_path)

            with self.assertRaisesRegex(ValueError, "escaped allow_roots"):
                config.project_path("linked")


if __name__ == "__main__":
    unittest.main()
