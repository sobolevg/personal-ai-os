"""VPS-side SSH client for the forced-command Mac worker endpoint."""

from __future__ import annotations

import json
import os
import re
import subprocess
from typing import Any, Callable

from .protocol import WorkerRequest, encode_request


Transport = Callable[..., subprocess.CompletedProcess[str]]
HOST_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,252}$")


def call_mac_worker(
    request: WorkerRequest,
    *,
    ssh_host: str | None = None,
    timeout: int = 20,
    transport: Transport = subprocess.run,
) -> dict[str, Any]:
    """Send one validated RPC without exposing a general remote shell."""
    host = (ssh_host or os.environ.get("PERSONAL_AI_OS_MAC_WORKER_SSH_HOST", "")).strip()
    if not HOST_RE.fullmatch(host) or host.startswith("-"):
        raise ValueError("PERSONAL_AI_OS_MAC_WORKER_SSH_HOST is invalid")
    if not 1 <= timeout <= 120:
        raise ValueError("SSH timeout must be between 1 and 120 seconds")

    token = encode_request(request)
    completed = transport(
        [
            "/usr/bin/ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            f"ConnectTimeout={min(timeout, 30)}",
            "-o",
            "ClearAllForwardings=yes",
            host,
            "mac-worker",
            token,
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if completed.returncode != 0:
        detail = _safe_transport_error(completed.stderr)
        raise RuntimeError(f"Mac worker SSH request failed ({completed.returncode}): {detail}")
    if len(completed.stdout) > 100_000:
        raise RuntimeError("Mac worker response exceeded the size limit")
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError("Mac worker returned invalid JSON") from error
    if not isinstance(result, dict):
        raise RuntimeError("Mac worker returned a non-object response")
    return result


def _safe_transport_error(value: str) -> str:
    line = " ".join(value.strip().splitlines())[:500]
    return line or "no diagnostic output"
