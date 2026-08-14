"""Telegram delivery boundary for link-capture confirmations."""

from __future__ import annotations

from typing import Protocol


class TelegramConfirmationSender(Protocol):
    async def send_confirmation(self, chat_id: int, text: str) -> None: ...
