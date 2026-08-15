"""Environment configuration contract for the link capture service."""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path


class MissingConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class LinkCaptureSettings:
    telegram_bot_token: str = field(repr=False)
    notion_token: str = field(repr=False)
    notion_database_id: str
    llm_api_key: str = field(repr=False)
    llm_base_url: str
    llm_model: str

    @classmethod
    def from_env(cls, env_file: str | Path | None = ".env") -> LinkCaptureSettings:
        if env_file is not None:
            _load_dotenv(Path(env_file))
        names = (
            "TELEGRAM_BOT_TOKEN",
            "NOTION_TOKEN",
            "NOTION_DATABASE_ID",
            "LLM_API_KEY",
            "LLM_BASE_URL",
            "LLM_MODEL",
        )
        values = {name: os.environ.get(name, "").strip() for name in names}
        missing = [name for name, value in values.items() if not value]
        if missing:
            raise MissingConfigurationError(
                "missing required environment variables: " + ", ".join(missing)
            )
        return cls(
            telegram_bot_token=values["TELEGRAM_BOT_TOKEN"],
            notion_token=values["NOTION_TOKEN"],
            notion_database_id=values["NOTION_DATABASE_ID"],
            llm_api_key=values["LLM_API_KEY"],
            llm_base_url=values["LLM_BASE_URL"],
            llm_model=values["LLM_MODEL"],
        )


@dataclass(frozen=True, slots=True)
class PlaudSettings:
    """Credentials for the optional PLAUD transcription provider."""

    client_id: str = field(repr=False)
    api_key: str = field(repr=False)
    base_url: str = "https://platform-us.plaud.ai"

    @classmethod
    def from_env(cls, env_file: str | Path | None = ".env") -> PlaudSettings:
        if env_file is not None:
            _load_dotenv(Path(env_file))
        values = {
            "PLAUD_CLIENT_ID": os.environ.get("PLAUD_CLIENT_ID", "").strip(),
            "PLAUD_API_KEY": os.environ.get("PLAUD_API_KEY", "").strip(),
            "PLAUD_BASE_URL": os.environ.get(
                "PLAUD_BASE_URL",
                "https://platform-us.plaud.ai",
            ).strip(),
        }
        missing = [
            name
            for name in ("PLAUD_CLIENT_ID", "PLAUD_API_KEY")
            if not values[name]
        ]
        if missing:
            raise MissingConfigurationError(
                "missing required environment variables: " + ", ".join(missing)
            )
        return cls(
            client_id=values["PLAUD_CLIENT_ID"],
            api_key=values["PLAUD_API_KEY"],
            base_url=values["PLAUD_BASE_URL"].rstrip("/"),
        )


@dataclass(frozen=True, slots=True)
class PlaudWebSettings:
    """Runtime paths for the optional persistent-browser provider."""

    browser_python: Path
    profile_dir: Path
    timeout_seconds: float = 900.0
    headless: bool = True

    @classmethod
    def from_env(cls, env_file: str | Path | None = ".env") -> PlaudWebSettings:
        if env_file is not None:
            _load_dotenv(Path(env_file))
        browser_python = Path(
            os.environ.get(
                "PLAUD_WEB_BROWSER_PYTHON",
                "/opt/vfs-slot-watcher/.venv/bin/python",
            ).strip()
        )
        profile_dir = Path(
            os.environ.get(
                "PLAUD_WEB_PROFILE_DIR",
                "/root/.hermes/browser-profiles/plaud-web",
            ).strip()
        )
        timeout_raw = os.environ.get("PLAUD_WEB_TIMEOUT_SECONDS", "900").strip()
        headless_raw = os.environ.get("PLAUD_WEB_HEADLESS", "1").strip().lower()
        try:
            timeout_seconds = float(timeout_raw)
        except ValueError as error:
            raise MissingConfigurationError(
                "PLAUD_WEB_TIMEOUT_SECONDS must be numeric"
            ) from error
        if not browser_python.is_absolute() or not profile_dir.is_absolute():
            raise MissingConfigurationError(
                "PLAUD Web runtime paths must be absolute"
            )
        if timeout_seconds <= 0:
            raise MissingConfigurationError(
                "PLAUD_WEB_TIMEOUT_SECONDS must be positive"
            )
        if headless_raw not in {"0", "1", "false", "true", "no", "yes"}:
            raise MissingConfigurationError(
                "PLAUD_WEB_HEADLESS must be a boolean value"
            )
        return cls(
            browser_python=browser_python,
            profile_dir=profile_dir,
            timeout_seconds=timeout_seconds,
            headless=headless_raw in {"1", "true", "yes"},
        )


def _load_dotenv(path: Path) -> None:
    """Load the small dotenv subset needed by this service, without overrides."""
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        name, value = line.split("=", 1)
        name = name.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        if name:
            os.environ.setdefault(name, value)
