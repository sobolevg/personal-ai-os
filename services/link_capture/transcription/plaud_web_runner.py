"""Standalone Playwright runner for the PLAUD Web provider.

This module intentionally imports Playwright only inside the runtime function,
so the domain package and its unit tests do not depend on a browser install.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import re
import sys
import time
from typing import Any, Iterator


PLAUD_WEB_URL = "https://web.plaud.ai/"
FILE_URL_PATTERN = re.compile(r"https://web\.plaud\.ai/file/[0-9a-f]+")


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile-dir", type=Path, required=True)
    parser.add_argument("--media-file", type=Path, required=True)
    parser.add_argument("--language", default="auto")
    parser.add_argument("--timeout-seconds", type=float, default=900.0)
    parser.add_argument("--headed", action="store_true")
    return parser.parse_args()


@contextmanager
def _profile_lock(profile_dir: Path) -> Iterator[None]:
    lock_path = profile_dir.parent / f".{profile_dir.name}.lock"
    lock_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def _is_authentication_required(page: Any) -> bool:
    return "/login" in page.url or page.locator('input[type="password"]').count() > 0


def _click_if_visible(locator: Any) -> bool:
    try:
        if locator.count() and locator.first.is_visible():
            locator.first.click(timeout=3_000)
            return True
    except Exception:
        return False
    return False


def _upload(page: Any, media_file: Path, deadline: float) -> None:
    _click_if_visible(page.get_by_role("button", name="Accept All"))
    if not _click_if_visible(page.get_by_text("Add audio", exact=True)):
        raise RuntimeError("add audio control was not found")
    if not _click_if_visible(page.get_by_role("menuitem", name="Import audio")):
        raise RuntimeError("import audio control was not found")
    file_input = page.locator('input[type="file"]')
    file_input.wait_for(state="attached", timeout=10_000)
    file_input.set_input_files(str(media_file))

    while time.monotonic() < deadline:
        if FILE_URL_PATTERN.fullmatch(page.url):
            return
        page.wait_for_timeout(1_000)
    raise TimeoutError("PLAUD Web upload did not open a file page")


def _start_generation_if_needed(page: Any) -> None:
    for name in (
        "Generate",
        "Generate now",
        "Start transcription",
        "Transcribe",
    ):
        if _click_if_visible(page.get_by_role("button", name=name, exact=True)):
            return


def _wait_for_transcript(page: Any, deadline: float) -> None:
    generation_checked = False
    while time.monotonic() < deadline:
        if page.locator(".transcribe-item .item-content").count() > 0:
            return
        if not generation_checked:
            _start_generation_if_needed(page)
            generation_checked = True
        page.wait_for_timeout(2_000)
        page.reload(wait_until="domcontentloaded", timeout=60_000)
        page.wait_for_timeout(1_000)
    raise TimeoutError("PLAUD Web transcript was not ready before the deadline")


def _seconds(value: str) -> float:
    parts = [float(part) for part in value.strip().split(":")]
    result = 0.0
    for part in parts:
        result = result * 60 + part
    return result


def _extract(page: Any, language: str) -> dict[str, Any]:
    raw = page.locator(".transcribe-item").evaluate_all(
        """items => items.map(item => ({
          timestamp: (item.querySelector('.timestamp')?.textContent || '').trim(),
          speaker: (item.querySelector('.speaker-name')?.textContent || '').trim(),
          text: (item.querySelector('.item-content')?.innerText || '').trim()
        }))"""
    )
    clean = [item for item in raw if item.get("timestamp") and item.get("text")]
    segments: list[dict[str, Any]] = []
    for index, item in enumerate(clean):
        start = _seconds(item["timestamp"])
        if index + 1 < len(clean):
            end = _seconds(clean[index + 1]["timestamp"])
        else:
            end = start
        segments.append(
            {
                "start": start,
                "end": end,
                "speaker": item.get("speaker") or None,
                "text": item["text"],
            }
        )
    text = "\n".join(item["text"] for item in segments)
    return {
        "status": "success",
        "language": "" if language == "auto" else language,
        "duration_seconds": None,
        "text": text,
        "segments": segments,
        "file_url": page.url,
    }


def _run(args: argparse.Namespace) -> dict[str, Any]:
    from playwright.sync_api import sync_playwright

    profile_dir = args.profile_dir.expanduser().resolve()
    media_file = args.media_file.expanduser().resolve()
    if not media_file.is_file():
        raise ValueError("media file does not exist")
    profile_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    deadline = time.monotonic() + args.timeout_seconds
    with _profile_lock(profile_dir), sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            str(profile_dir),
            executable_path="/usr/bin/google-chrome-stable",
            headless=not args.headed,
            viewport={"width": 1366, "height": 900},
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        try:
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(PLAUD_WEB_URL, wait_until="domcontentloaded", timeout=90_000)
            page.wait_for_timeout(3_000)
            if _is_authentication_required(page):
                return {"status": "authentication_required"}
            _upload(page, media_file, deadline)
            _wait_for_transcript(page, deadline)
            return _extract(page, args.language)
        finally:
            context.close()


def main() -> int:
    try:
        result = _run(_arguments())
    except Exception as error:
        result = {"status": "error", "error_type": type(error).__name__}
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get("status") == "success" else 2


if __name__ == "__main__":
    sys.exit(main())
