"""
Conversation manager — owns all reads/writes to Conversation and Message rows.
No business logic lives here; this is purely a persistence helper.
"""
from __future__ import annotations
import logging
from typing import Sequence

from db.relational.models.message import Message
from modules.chat.config import ChatSettings

logger = logging.getLogger(__name__)



class ConversationManager:
    def __init__(self, settings: ChatSettings):
        self.settings = settings


    def trim_history(self, messages: Sequence[Message]) -> list[Message]:
        """
        Return the most recent messages that fit within HISTORY_TOKEN_BUDGET.

        Falls back to raw character count (÷ 4) when token_count is not set.
        Always includes at least the most recent message regardless of size.
        """
        limit = self.settings.context_window_limit
        selected: list[Message] = []

        for msg in reversed(messages):
            tokens = msg.token_count or (len(msg.content) // 4)
            if limit - tokens < 0 and selected:
                break
            selected.append(msg)
            limit -= tokens

        selected.reverse()
        trimmed = len(messages) - len(selected)
        if trimmed:
            logger.debug("Trimmed %d older messages to fit context budget", trimmed)
        return selected
