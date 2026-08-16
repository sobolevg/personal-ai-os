"""One-time interactive login for the persistent PLAUD Web VPS profile."""

from __future__ import annotations

import argparse
import getpass
import os
from pathlib import Path
import secrets
import string
import sys
from urllib.parse import urlparse


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile-dir", type=Path, required=True)
    parser.add_argument(
        "--generated-password-file",
        type=Path,
        help=(
            "create a strong PLAUD password in this mode-0600 file when "
            "code login requires the one-time password setup step"
        ),
    )
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


def _is_auth_response(response, endpoint: str) -> bool:
    return urlparse(response.url).path.endswith(endpoint)


def _require_successful_response(response, operation: str) -> dict:
    if not response.ok:
        raise RuntimeError(
            f"PLAUD {operation} request failed with HTTP {response.status}"
        )
    try:
        payload = response.json()
    except Exception:
        return {}
    service_status = payload.get("status") if isinstance(payload, dict) else None
    if service_status not in (None, 0):
        raise RuntimeError(
            f"PLAUD {operation} request failed with status {service_status}"
        )
    return payload if isinstance(payload, dict) else {}


def _response_data(payload: dict) -> dict:
    data = payload.get("data", payload)
    return data if isinstance(data, dict) else {}


def _ensure_policy_checked(page) -> None:
    policy = page.get_by_test_id("policy-checkbox-agreeTerms")
    policy.wait_for(state="visible", timeout=10_000)
    checkbox = policy.locator('[role="checkbox"]')
    if checkbox.get_attribute("aria-checked") != "true":
        policy.click()
    page.wait_for_function(
        """() => document.querySelector(
          '[data-testid="policy-checkbox-agreeTerms"] [role="checkbox"]'
        )?.getAttribute('aria-checked') === 'true'""",
        timeout=10_000,
    )


def _generate_password() -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%"
    required = [
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.digits),
    ]
    password = required + [secrets.choice(alphabet) for _ in range(13)]
    secrets.SystemRandom().shuffle(password)
    return "".join(password)


def _create_password_file(path: Path) -> str:
    resolved = path.expanduser().resolve()
    resolved.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    password = _generate_password()
    descriptor = os.open(resolved, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(password + "\n")
    except Exception:
        resolved.unlink(missing_ok=True)
        raise
    return password


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
            existing_code = page.get_by_placeholder("Enter verification code")
            if existing_code.count() and existing_code.first.is_visible():
                password_mode = page.get_by_role(
                    "button", name="Sign in with password", exact=True
                )
                if not _click_if_visible(password_mode):
                    raise RuntimeError("could not reset the code sign-in form")
                existing_code.first.wait_for(state="hidden", timeout=10_000)
            email_input = page.get_by_placeholder("Email address")
            email_input.click(force=True)
            page.wait_for_function(
                """() => {
                  const input = document.querySelector(
                    'input[placeholder="Email address"]'
                  );
                  return input && !input.hasAttribute('readonly');
                }""",
                timeout=10_000,
            )
            email_input.fill(email)
            _ensure_policy_checked(page)
            otp_send_responses = []
            page.on(
                "response",
                lambda response: otp_send_responses.append(response)
                if _is_auth_response(response, "/auth/otp-send-code")
                else None,
            )
            button = page.get_by_test_id("login-toggle-method-button")
            if not _click_if_visible(button):
                raise RuntimeError("code sign-in control was not found")
            code_input = page.get_by_placeholder("Enter verification code")
            code_input.wait_for(state="visible", timeout=30_000)
            _ensure_policy_checked(page)

            # The current PLAUD UI normally sends the first code automatically
            # when code mode opens. Only click Send when no request occurred,
            # otherwise the first code can be invalidated by a duplicate send.
            page.wait_for_timeout(5_000)
            if not otp_send_responses:
                send = page.get_by_role("button", name="Send", exact=True)
                if not send.is_enabled():
                    raise RuntimeError("verification-code request is not enabled")
                with page.expect_response(
                    lambda response: _is_auth_response(
                        response, "/auth/otp-send-code"
                    ),
                    timeout=30_000,
                ) as send_response_info:
                    send.click()
                otp_send_responses.append(send_response_info.value)
            _require_successful_response(
                otp_send_responses[-1], "verification-code"
            )
            _ensure_policy_checked(page)
            print("Verification code sent. Check your email.")
            code = getpass.getpass("Verification code: ").strip()
            if not code:
                raise ValueError("verification code is required")
            code_input.click(force=True)
            code_input.fill(code)
            sign_in = page.get_by_test_id("login-login-btn")
            if not sign_in.count() or not sign_in.first.is_visible():
                raise RuntimeError("code sign-in submission was not found")
            with page.expect_response(
                lambda response: _is_auth_response(response, "/auth/otp-login"),
                timeout=30_000,
            ) as login_response_info:
                sign_in.first.click(timeout=3_000)
            login_payload = _require_successful_response(
                login_response_info.value, "login"
            )
            login_data = _response_data(login_payload)
            expected_password_setup = bool(login_data.get("set_password_token"))
            print(
                "PLAUD OTP response received "
                f"(password_setup={str(expected_password_setup).lower()}, "
                f"access_granted={str(bool(login_data.get('access_token'))).lower()})."
            )

            set_password_form = page.get_by_test_id(
                "login-otp-set-password-form"
            )
            try:
                set_password_form.wait_for(state="visible", timeout=30_000)
            except Exception:
                pass
            if set_password_form.count() and set_password_form.first.is_visible():
                print("PLAUD password setup form detected.")
                if args.generated_password_file is None:
                    raise RuntimeError(
                        "PLAUD requires one-time password setup; rerun with "
                        "--generated-password-file after user approval"
                    )
                password = _create_password_file(args.generated_password_file)
                page.get_by_test_id("otp-set-password-input").fill(password)
                page.get_by_test_id("otp-set-confirm-password-input").fill(
                    password
                )
                with page.expect_response(
                    lambda response: _is_auth_response(
                        response, "/auth/set-password-issue-token"
                    ),
                    timeout=30_000,
                ) as password_response_info:
                    print("Submitting PLAUD password setup.")
                    page.get_by_test_id("otp-set-password-create-btn").click()
                _require_successful_response(
                    password_response_info.value, "password setup"
                )
            elif expected_password_setup:
                raise RuntimeError(
                    "PLAUD requested password setup but its form did not appear"
                )
            elif "/login" in page.url:
                code_error = page.locator("#login-code-error")
                if code_error.count() and code_error.first.is_visible():
                    message = code_error.first.inner_text().strip()
                    if message:
                        raise RuntimeError(f"PLAUD rejected the code: {message}")
                result_kind = (
                    "access token"
                    if login_data.get("access_token")
                    else "no recognized login result"
                )
                raise RuntimeError(
                    f"PLAUD stayed on the login page after returning {result_kind}"
                )
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
        if isinstance(error, RuntimeError):
            print(f"Login failed: {error}", file=sys.stderr)
        else:
            print(f"Login failed: {type(error).__name__}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
