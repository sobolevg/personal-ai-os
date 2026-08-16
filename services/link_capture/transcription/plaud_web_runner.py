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
FILE_ROW_SELECTOR = '[data-testid^="file-list-item-"]'


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


def _click_when_visible(locator: Any, *, timeout: float = 5_000) -> bool:
    try:
        locator.first.wait_for(state="visible", timeout=timeout)
        locator.first.click(timeout=timeout)
        return True
    except Exception:
        return False


def _log_stage(message: str) -> None:
    print(f"PLAUD Web: {message}", file=sys.stderr, flush=True)


def _file_rows(page: Any) -> list[dict[str, str]]:
    rows = page.locator(FILE_ROW_SELECTOR).evaluate_all(
        """items => items.map(item => ({
          id: item.getAttribute('data-file-id') || '',
          name: (item.textContent || '').trim()
        }))"""
    )
    return [row for row in rows if row.get("id")]


def _new_file_id(
    previous_ids: set[str],
    rows: list[dict[str, str]],
    expected_name: str,
) -> str | None:
    for row in rows:
        file_id = row.get("id", "")
        name = row.get("name", "")
        if file_id not in previous_ids and expected_name in name:
            return file_id
    return None


def _close_import_dialog(page: Any) -> None:
    _click_if_visible(
        page.locator(".modal-overlay:visible .modal-dialog__title-close")
    )


def _upload(page: Any, media_file: Path, deadline: float) -> None:
    previous_ids = {row["id"] for row in _file_rows(page)}
    _click_if_visible(page.get_by_role("button", name="Accept All"))
    if not _click_if_visible(page.get_by_text("Add audio", exact=True)):
        raise RuntimeError("add audio control was not found")
    if not _click_if_visible(page.get_by_role("menuitem", name="Import audio")):
        raise RuntimeError("import audio control was not found")
    file_input = page.locator('input[type="file"]')
    file_input.wait_for(state="attached", timeout=10_000)
    file_input.set_input_files(str(media_file))
    _log_stage("upload selected")

    while time.monotonic() < deadline:
        if FILE_URL_PATTERN.fullmatch(page.url):
            _log_stage("file page opened")
            return
        dialog = page.locator(".modal-overlay:visible")
        if dialog.count():
            dialog_text = dialog.first.inner_text()
            if media_file.stem in dialog_text and "Imported" in dialog_text:
                _close_import_dialog(page)
                _log_stage("upload imported")
        file_id = _new_file_id(previous_ids, _file_rows(page), media_file.stem)
        if file_id:
            row = page.locator(f'[data-file-id="{file_id}"]')
            if _click_if_visible(row):
                page.wait_for_url(FILE_URL_PATTERN, timeout=30_000)
                _log_stage("file page opened")
                return
        page.wait_for_timeout(1_000)
    raise TimeoutError("PLAUD Web upload did not open a file page")


def _start_generation_if_needed(page: Any) -> bool:
    generate_now = page.get_by_text("Generate now", exact=True)
    if _click_if_visible(generate_now):
        _log_stage("generation requested")
        return True

    generate = page.locator('[data-testid="file-generate-button"]')
    if _click_when_visible(generate):
        auto = page.get_by_text("Auto generation", exact=True)
        if _click_when_visible(auto):
            page.wait_for_timeout(250)
        if _click_when_visible(generate_now):
            _log_stage("generation requested")
            return True

    for name in (
        "Generate",
        "Generate now",
        "Start transcription",
        "Transcribe",
    ):
        if _click_if_visible(page.get_by_role("button", name=name, exact=True)):
            _log_stage("generation requested")
            return True
    return False


def _show_transcript(page: Any) -> None:
    _click_if_visible(page.get_by_text("Transcript", exact=True))


def _wait_for_transcript(page: Any, deadline: float) -> None:
    last_reload = time.monotonic()
    while time.monotonic() < deadline:
        _show_transcript(page)
        if page.locator(".transcribe-item .item-content").count() > 0:
            _log_stage("transcript ready")
            return
        _start_generation_if_needed(page)
        page.wait_for_timeout(2_000)
        if time.monotonic() - last_reload >= 30:
            page.reload(wait_until="domcontentloaded", timeout=60_000)
            page.wait_for_timeout(1_000)
            last_reload = time.monotonic()
    raise TimeoutError("PLAUD Web transcript was not ready before the deadline")


def _seconds(value: str) -> float:
    parts = [float(part) for part in value.strip().split(":")]
    result = 0.0
    for part in parts:
        result = result * 60 + part
    return result


def _extract(page: Any, language: str) -> dict[str, Any]:
    _show_transcript(page)
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
