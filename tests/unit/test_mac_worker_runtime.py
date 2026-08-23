from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from services.mac_worker.protocol import WorkerConfig, WorkerRequest, encode_request
from services.mac_worker.worker import (
    build_agent_command,
    build_agent_prompt,
    job_status,
    redact_log,
    serve_ssh,
    start_job,
    stop_job,
)


class MacWorkerRuntimeTest(unittest.TestCase):
    def config(self, root: Path) -> WorkerConfig:
        project = root / "project"
        project.mkdir()
        return WorkerConfig(
            projects={"project": project},
            allow_roots=(root,),
            jobs_dir=root / "jobs",
            codex_binary=Path("/usr/bin/true"),
            claude_binary=Path("/usr/bin/false"),
        )

    def test_forced_command_rejects_everything_except_rpc(self) -> None:
        with TemporaryDirectory() as directory:
            config = self.config(Path(directory))
            with self.assertRaisesRegex(ValueError, "only the mac-worker"):
                serve_ssh("bash -lc id", config)

    def test_doctor_rpc_does_not_accept_shell_arguments(self) -> None:
        with TemporaryDirectory() as directory:
            config = self.config(Path(directory))
            token = encode_request(WorkerRequest.from_dict({"operation": "doctor"}))
            result = serve_ssh(f"mac-worker {token}", config)

        self.assertTrue(result["success"])
        self.assertEqual(result["projects"], ["project"])

    def test_codex_defaults_to_workspace_write_without_network(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            config = self.config(root)
            request = {
                "agent": "codex",
                "allow_commit": False,
                "allow_push": False,
                "task": "fix tests",
            }
            command = build_agent_command(request, config, root / "project")
            prompt = build_agent_prompt(request, root / "project")

        self.assertIn("workspace-write", command)
        self.assertIn("sandbox_workspace_write.network_access=false", command)
        self.assertNotIn("danger-full-access", command)
        self.assertIn("Commit and push are forbidden", prompt)

    def test_claude_has_no_bash_tool_in_safe_mvp(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            config = self.config(root)
            command = build_agent_command(
                {"agent": "claude", "task": "edit"}, config, root / "project"
            )

        self.assertIn("Read,Edit,Write,Glob,Grep", command)
        self.assertNotIn("Bash", command)
        self.assertNotIn("bypassPermissions", command)

    def test_log_redaction_masks_common_secret_shapes(self) -> None:
        value = "Authorization: Bearer abc123\nAPI_KEY=secret-value\nsk-1234567890abcdef"
        redacted = redact_log(value)

        self.assertNotIn("abc123", redacted)
        self.assertNotIn("secret-value", redacted)
        self.assertNotIn("sk-1234567890abcdef", redacted)
        self.assertGreaterEqual(redacted.count("[REDACTED]"), 3)

    def test_run_persists_background_job_without_running_a_shell(self) -> None:
        class FakeProcess:
            pid = 4242

        popen_calls = []

        def fake_popen(command, **kwargs):
            popen_calls.append((command, kwargs))
            return FakeProcess()

        with TemporaryDirectory() as directory:
            root = Path(directory)
            config = self.config(root)
            request = WorkerRequest.from_dict(
                {"operation": "run", "project": "project", "task": "inspect", "agent": "codex"}
            )
            with patch("services.mac_worker.worker._agent_status", return_value={"authenticated": True}), patch(
                "services.mac_worker.worker.subprocess.Popen", side_effect=fake_popen
            ):
                result = start_job(request, config)

            job_dir = config.jobs_dir / result["job_id"]
            self.assertTrue((job_dir / "request.json").is_file())
            self.assertTrue((job_dir / "process.json").is_file())
            self.assertEqual(popen_calls[0][0][0:3], [unittest.mock.ANY, "-m", "services.mac_worker.worker"])
            self.assertNotIn("shell", popen_calls[0][1])
            self.assertTrue(popen_calls[0][1]["start_new_session"])

    def test_status_returns_redacted_tail_for_completed_job(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            config = self.config(root)
            job_id = "a" * 32
            job_dir = config.jobs_dir / job_id
            job_dir.mkdir(parents=True)
            (job_dir / "request.json").write_text(
                '{"agent":"codex","project":"project","created_at":"now"}', encoding="utf-8"
            )
            (job_dir / "process.json").write_text('{"pid":4242}', encoding="utf-8")
            (job_dir / "result.json").write_text(
                '{"exit_code":0,"finished_at":"later"}', encoding="utf-8"
            )
            (job_dir / "agent.log").write_text("TOKEN=secret-value\ndone", encoding="utf-8")

            result = job_status(job_id, 4000, config)

        self.assertEqual(result["state"], "succeeded")
        self.assertIn("[REDACTED]", result["log_tail"])
        self.assertNotIn("secret-value", result["log_tail"])

    def test_stop_targets_only_the_recorded_process_group(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            config = self.config(root)
            job_id = "b" * 32
            job_dir = config.jobs_dir / job_id
            job_dir.mkdir(parents=True)
            (job_dir / "process.json").write_text('{"pid":4242}', encoding="utf-8")
            with patch(
                "services.mac_worker.worker.job_status",
                return_value={"state": "running"},
            ), patch("services.mac_worker.worker.os.killpg") as killpg:
                result = stop_job(job_id, config)

        killpg.assert_called_once_with(4242, unittest.mock.ANY)
        self.assertEqual(result["state"], "stopping")


if __name__ == "__main__":
    unittest.main()
