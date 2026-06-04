"""
PromptBuilder — pure logic, zero I/O.
Assembles the final message list sent to the LLM:

  [system prompt]
  [trimmed conversation history]
  [user message + retrieved context]

Fully unit-testable with no mocks.
"""
from __future__ import annotations
from typing import TYPE_CHECKING

from db.relational.constants import MessageRole

if TYPE_CHECKING:
    from db.relational.models.message import Message
    from db.vector.schemas import SearchResult

SYSTEM_PROMPT = """\
You are a helpful assistant. Answer the user's question use the provided context as helper 

When referencing information from the context, be concise and direct.\
"""

CONTEXT_HEADER = "### Relevant context\n"
CONTEXT_ITEM_TEMPLATE = "[{i}] {text}"
NO_CONTEXT_NOTE = "(No relevant context was retrieved for this query.)"


class PromptBuilder:
    """
    Builds the message list for an LLM chat-completion call.

    The output format is a list of dicts compatible with OpenAI-style APIs:
        [{"role": "system"|"user"|"assistant", "content": "..."}]
    """

    def __init__(self, system_prompt: str = SYSTEM_PROMPT):
        self._system_prompt = system_prompt

    def build(
        self,
        user_message: str,
        history: list[Message],
        chunks: list[SearchResult],
    ) -> list[dict[str, str]]:
        """
        Assemble the full prompt.

        Args:
            user_message: The current user turn (raw text, not yet persisted).
            history:      Trimmed conversation history (Message ORM objects).
            chunks:       Retrieved context chunks from the retrieval module.

        Returns:
            List of {"role": ..., "content": ...} dicts ready for the LLM client.
        """
        messages: list[dict[str, str]] = []

        # 1. System prompt
        messages.append({"role": MessageRole.system, "content": self._system_prompt})

        # 2. Conversation history (already trimmed by ConversationManager)
        for msg in history:
            messages.append({"role": msg.role, "content": msg.content})

        # 3. User message augmented with retrieved context
        messages.append({
            "role": MessageRole.user,
            "content": self._build_user_turn(user_message, chunks),
        })

        return messages

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_user_turn(self, user_message: str, chunks: list[SearchResult]) -> str:
        context_block = self._format_context(chunks)
        return f"{context_block}\n\n### Question\n{user_message}"

    def _format_context(self, chunks: list[SearchResult]) -> str:
        if not chunks:
            return f"{CONTEXT_HEADER}{NO_CONTEXT_NOTE}"

        items = "\n\n".join(
            CONTEXT_ITEM_TEMPLATE.format(i=i + 1, text=chunk.content.strip())
            for i, chunk in enumerate(chunks)
        )
        return f"{CONTEXT_HEADER}{items}"
