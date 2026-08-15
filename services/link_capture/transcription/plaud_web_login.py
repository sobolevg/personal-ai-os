"""One-time interactive login for the persistent PLAUD Web VPS profile."""

from __future__ import annotations

import argparse
import getpass
from pathlib import Path
import re
import sys


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile-dir", type=Path, required=True)
    parser.add_argument("--headed", action="store_true")
    return parser.parse_args()


def _click_if_visible(locator) -> bool:
    try:
        if locator.count() and locator.first.is_visible():
            locator.first.click(timeout=3_000)
            return True
    except Exception:
        return False
    return False


def _run(args: argparse.Namespace) -> int:
    from playwright.sync_api import sync_playwright

    email = input("PLAUD account email: ").strip()
    if not email or "@" not in email:
        raise ValueError("a valid account email is required")

    profile_dir = args.profile_dir.expanduser().resolve()
    profile_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            str(profile_dir),
            executable_path="/usr/bin/google-chrome-stable",
            headless=not args.headed,
            viewport={"width": 1366, "height": 900},
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        try:
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(
                "https://web.plaud.ai/",
                wait_until="domcontentloaded",
                timeout=90_000,
            )
            page.wait_for_timeout(3_000)
            if "/login" not in page.url:
                print("PLAUD Web profile is already authenticated.")
                return 0

            _click_if_visible(page.get_by_role("button", name="Accept All"))
            email_input = page.get_by_placeholder("Email address")
            if email_input.get_attribute("readonly") is not None:
                password_mode = page.get_by_role(
                    "button", name="Sign in with password", exact=True
                )
                if not _click_if_visible(password_mode):
                    raise RuntimeError("could not reset the code sign-in form")
                email_input.wait_for(state="visible", timeout=10_000)
            email_input.fill(email)
            agreement = page.locator('input[type="checkbox"]')
            if agreement.count() and not agreement.first.is_checked():
                agreement.first.check()
            button = page.get_by_role(
                "button", name="Sign in with a code", exact=True
            )
            if not _click_if_visible(button):
                raise RuntimeError("code sign-in control was not found")
            page.get_by_role("button", name="Send", exact=True).click()
            code_input = page.get_by_placeholder("Enter verification code")
            code_input.wait_for(state="visible", timeout=30_000)
            print("Verification code sent. Check your email.")
            code = getpass.getpass("Verification code: ").strip()
            if not code:
                raise ValueError("verification code is required")
            code_input.fill(code)
            sign_in = page.get_by_role(
                "button", name=re.compile(r"^Sign in\s*$")
            )
            sign_in.click()
            page.wait_for_url(
                lambda url: "/login" not in url,
                timeout=60_000,
            )
            page.wait_for_timeout(2_000)
            if "/login" in page.url:
                raise RuntimeError("PLAUD Web login did not complete")
            print("PLAUD Web profile authenticated successfully.")
            return 0
        finally:
            context.close()


def main() -> int:
    try:
        return _run(_arguments())
    except Exception as error:
        print(f"Login failed: {type(error).__name__}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
