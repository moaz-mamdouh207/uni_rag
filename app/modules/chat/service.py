"""
ChatService — orchestrates all chat functionality.

Two paths in chat():
  PATH A (files attached) → AgentLoop
      The LLM drives the reasoning: it calls extract_file(), retrieve(),
      calculate(), clarify_question(), and finish() in whatever order it
      decides. The service just starts the loop and waits for finish().

  PATH B (text only) → existing single-pass RAG
      Unchanged from the original implementation.
"""
from __future__ import annotations
import logging
from typing import TYPE_CHECKING
from uuid import UUID

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from db.relational.schemas import ConversationCreate, MessageCreate
from db.relational.models.conversation import Conversation
from db.relational.constants import MessageRole
from db.vector.schemas import SearchQuery

from modules.chat.schemas import (
    ChatRequest,
    ChatResponse,
    ConversationHistoryResponse,
    ConversationMetadata,
)

if TYPE_CHECKING:
    from modules.chat.config import ChatSettings
    from db.relational.repositories.conversation_repository import AsyncConversationRepository
    from db.relational.repositories.message_repository import AsyncMessageRepository
    from modules.chat.conversation import ConversationManager
    from modules.chat.prompt_builder import PromptBuilder
    from modules.chat.agent.loop import AgentLoop
    from modules.retrieval.service import RetrievalService
    from shared.llm.client import LLMClient
    from db.relational.schemas import ConversationUpdate

logger = logging.getLogger(__name__)


class ChatService:
    def __init__(
        self,
        conversation_repo:   AsyncConversationRepository,
        message_repo:        AsyncMessageRepository,
        retrieval_service:   RetrievalService,
        convesation_manager: ConversationManager,
        prompt_builder:      PromptBuilder,
        llm_client:          LLMClient,
        settings:            ChatSettings,
        agent_loop_factory,  # callable(user_id, course_id, documents_ids) -> AgentLoop
    ):
        self._conv_repo          = conversation_repo
        self._message_repo       = message_repo
        self._retrieval          = retrieval_service
        self._conv_manager       = convesation_manager
        self._llm                = llm_client
        self._prompt             = prompt_builder
        self._settings           = settings
        self._agent_loop_factory = agent_loop_factory

    # ------------------------------------------------------------------
    # Conversation CRUD (unchanged)
    # ------------------------------------------------------------------

    async def add_conversation(self, data: ConversationCreate, user_id: UUID) -> ConversationMetadata:
        conv = await self._conv_repo.add(data=data, user_id=user_id)
        return ConversationMetadata(id=conv.id, name=conv.name)

    async def list_conversations(self, user_id: UUID) -> list[ConversationMetadata]:
        conversations = await self._conv_repo.get_all_by_user(user_id=user_id)
        return [ConversationMetadata(id=c.id, name=c.name) for c in conversations]

    async def update_conversation(self, data: ConversationUpdate, conv: Conversation) -> ConversationMetadata:
        conv = await self._conv_repo.update(data=data, conversation=conv)
        return ConversationMetadata(id=conv.id, name=conv.name)

    async def delete_conversation(self, conv: Conversation) -> None:
        await self._conv_repo.delete(conv)

    # ------------------------------------------------------------------
    # Core chat turn
    # ------------------------------------------------------------------

    async def chat(self, conv: Conversation, request: ChatRequest) -> ChatResponse:
        raw_history     = await self._message_repo.get_all_by_conversation(conv.id)
        trimmed_history = self._conv_manager.trim_history(raw_history)

        if request.files:
            answer, prompt_tokens, completion_tokens = await self._agentic_chat(
                request=request,
                conv=conv,
                history=trimmed_history,
            )
            prompt_repr = f"[agentic loop — {len(request.files)} file(s) attached]"
        else:
            answer, messages, prompt_tokens, completion_tokens = await self._standard_chat(
                request=request,
                conv=conv,
                history=trimmed_history,
            )
            prompt_repr = "\n".join(f"{m['role']}: {m['content']}" for m in messages)

        # Persist both turns
        await self._message_repo.add(
            data=MessageCreate(
                role=MessageRole.user,
                content=request.query,
                token_count=prompt_tokens,
            ),
            conversation_id=conv.id,
        )
        await self._message_repo.add(
            data=MessageCreate(
                role=MessageRole.assistant,
                content=answer,
                token_count=completion_tokens,
            ),
            conversation_id=conv.id,
        )

        return ChatResponse(
            prompt=prompt_repr,
            answer=answer,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )

    async def get_history(self, id: UUID) -> ConversationHistoryResponse:
        messages = await self._message_repo.get_all_by_conversation(id)
        return ConversationHistoryResponse(
            conversation_id=str(id),
            messages=messages,  # type: ignore[arg-type]
            total=len(messages),
        )

    # ------------------------------------------------------------------
    # Private — PATH A: agentic
    # ------------------------------------------------------------------

    async def _agentic_chat(
        self,
        request: ChatRequest,
        conv:    Conversation,
        history: list,
    ) -> tuple[str, int | None, int | None]:
        agent_loop = self._agent_loop_factory(
            user_id=conv.user_id,
            course_id=conv.meta.course_id,
            documents_ids=conv.meta.documents_ids,
        )

        lc_history = self._orm_history_to_lc(history)

        result = await agent_loop.run(
            user_query=request.query,
            file_ids=request.files,
            history=lc_history,
        )

        if result.hit_limit:
            logger.warning(
                "ChatService: agent hit iteration limit for conv %s", conv.id
            )

        return result.answer, None, None

    # ------------------------------------------------------------------
    # Private — PATH B: standard single-pass RAG
    # ------------------------------------------------------------------

    async def _standard_chat(
        self,
        request: ChatRequest,
        conv:    Conversation,
        history: list,
    ) -> tuple[str, list, int | None, int | None]:
        search_query = SearchQuery(
            query=request.query,
            top_k=self._settings.top_k,
            score_threshold=self._settings.score_threshold,
            rerank=self._settings.rerank,
        )
        response = await self._retrieval.retrieve(
            request=search_query,
            user_id=conv.user_id,
            course_id=conv.meta.course_id,
            documents_ids=conv.meta.documents_ids,
        )

        messages = self._prompt.build(
            user_message=request.query,
            history=history,
            chunks=response.results,
        )

        llm_result = await self._llm.complete(messages)

        return (
            llm_result.content,
            messages,
            getattr(llm_result.usage, "prompt_tokens", None),
            getattr(llm_result.usage, "completion_tokens", None),
        )

    # ------------------------------------------------------------------
    # Private — helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _orm_history_to_lc(history: list) -> list[BaseMessage]:
        lc: list[BaseMessage] = []
        for msg in history:
            if msg.role == MessageRole.user:
                lc.append(HumanMessage(content=msg.content))
            elif msg.role == MessageRole.assistant:
                lc.append(AIMessage(content=msg.content))
        return lc
