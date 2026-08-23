from __future__ import annotations

import json
import subprocess
import unittest

from services.mac_worker.client import call_mac_worker
from services.mac_worker.protocol import WorkerRequest


class MacWorkerClientTest(unittest.TestCase):
    def test_ssh_transport_uses_argument_list_and_disables_forwarding(self) -> None:
        calls = []

        def fake_transport(command, **kwargs):
            calls.append((command, kwargs))
            return subprocess.CompletedProcess(command, 0, json.dumps({"success": True}), "")

        result = call_mac_worker(
            WorkerRequest.from_dict({"operation": "doctor"}),
            ssh_host="personal-ai-os-mac-worker",
            transport=fake_transport,
        )

        command = calls[0][0]
        self.assertTrue(result["success"])
        self.assertEqual(command[0], "/usr/bin/ssh")
        self.assertIn("ClearAllForwardings=yes", command)
        self.assertEqual(command[-2], "mac-worker")
        self.assertNotIn("shell=True", calls[0][1])

    def test_invalid_host_is_rejected_before_transport(self) -> None:
        with self.assertRaisesRegex(ValueError, "SSH_HOST"):
            call_mac_worker(
                WorkerRequest.from_dict({"operation": "doctor"}),
                ssh_host="-oProxyCommand=bad",
            )


if __name__ == "__main__":
    unittest.main()
