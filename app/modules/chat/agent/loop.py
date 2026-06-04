"""
AgentLoop — the agentic reasoning loop for the engineering RAG tutor.

Architecture:
  - Uses LangChain's bind_tools() with ChatGoogleGenerativeAI for native
    Gemini function calling. The LLM decides which tools to call and when.
  - Runs until the LLM calls finish() or max_iterations is reached.
  - Tool calls within a single iteration are executed in parallel where
    possible (multiple tool calls in one LLM response).
  - The full message history is maintained and passed on every iteration
    so the LLM has complete context of everything it has done so far.
  - A safe partial-answer fallback is returned if the loop hits the
    iteration cap without calling finish().

Message history shape:
    [SystemMessage]
    [HumanMessage]           ← user query + file_ids injected
    [AIMessage(tool_calls)]  ← LLM decides to call tools
    [ToolMessage(result)]    ← tool output injected back
    [AIMessage(tool_calls)]  ← LLM calls more tools or finish()
    ...

LLMClient extension:
  This module uses self._build_llm_with_tools() which calls bind_tools()
  on the underlying ChatGoogleGenerativeAI instance. The existing
  LLMClient.complete() path is untouched — this is additive.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING, Any
from uuid import UUID

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel

from modules.chat.agent.prompts import ENGINEERING_AGENT_SYSTEM_PROMPT
from modules.chat.agent.tool_schemas import FinishOutput
from modules.chat.agent.tools import AgentTools

if TYPE_CHECKING:
    from modules.chat.agent.tool_schemas import (
        ExtractFileInput,
        RetrieveInput,
        RetrieveMultiInput,
        CalculateInput,
        ClarifyQuestionInput,
        FinishInput,
    )

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# LangChain tool definitions — used with bind_tools()
# These tell Gemini the name, description, and parameter schema of each tool.
# ---------------------------------------------------------------------------

from langchain_core.tools import tool as lc_tool


@lc_tool
def extract_file(file_id: str) -> str:
    """
    Extract all questions and numbered items from an attached file (PDF or image).
    Call this FIRST for every file_id in the user's message before doing anything else.
    Returns structured markdown with every item exactly as numbered in the file.
    """
    ...  # never actually called — AgentTools.execute() handles execution


@lc_tool
def retrieve(query: str, context_hint: str | None = None) -> str:
    """
    Search the course knowledge base for a single concept, formula, or principle.
    Use for targeted lookup of one specific piece of engineering knowledge.
    context_hint should be the specific engineering sub-field e.g. 'beam bending',
    'Bernoulli equation', 'Mohr circle stress'. Always provide it when you know it.
    """
    ...


@lc_tool
def retrieve_multi(queries: list[dict]) -> str:
    """
    Search the knowledge base for multiple independent concepts in parallel.
    queries is a list of objects each with 'query' (required) and 'context_hint' (optional).
    Use when you already know you need context for several different questions at once.
    More efficient than calling retrieve() repeatedly.
    """
    ...


@lc_tool
def calculate(expression: str) -> str:
    """
    Evaluate a mathematical expression with full precision using a symbolic math engine.
    Supports arithmetic, algebra, trigonometry, logarithms, square roots, and equation solving.
    
    Examples:
      arithmetic:  (15 * 6**2) / 8
      sqrt:        sqrt(144)
      trig:        sin(pi/4)
      solve:       solve(x**2 - 4, x)
    
    Always use ** for exponentiation, not ^.
    Always call this for any numerical computation — never compute in your head.
    """
    ...


@lc_tool
def clarify_question(original_text: str, interpretation: str) -> str:
    """
    Record your interpretation of an ambiguous question or one that depends on
    a previous part (e.g. 'using the result from part a', 'hence show that').
    Call this BEFORE retrieving or calculating for that question.
    original_text: the ambiguous question text verbatim.
    interpretation: your interpretation including any dependency assumptions.
    """
    ...


@lc_tool
def finish(answer: str) -> str:
    """
    Deliver the final answer to the user and end the loop.
    Call this only when you have retrieved all necessary context and completed
    all calculations. This is the ONLY way to return a response to the user.
    Format: number answers to match question numbering, show formulas and
    working, state units explicitly in every final answer.
    """
    ...


ALL_LC_TOOLS = [extract_file, retrieve, retrieve_multi, calculate, clarify_question, finish]


# ---------------------------------------------------------------------------
# AgentLoop
# ---------------------------------------------------------------------------

class AgentLoopResult(BaseModel):
    answer:      str
    iterations:  int
    hit_limit:   bool = False


class AgentLoop:
    """
    Runs the agentic reasoning loop for a single chat turn.

    Args:
        llm:        The raw ChatGoogleGenerativeAI instance from LLMClient.
                    We bind tools directly on it here — LLMClient.complete()
                    is untouched.
        tools:      AgentTools instance pre-configured with user/course scope.
        settings:   ChatSettings — provides max_agent_iterations.
    """

    def __init__(
        self,
        llm:      ChatGoogleGenerativeAI,
        tools:    AgentTools,
        max_iterations: int = 10,
    ) -> None:
        self._llm_with_tools = llm.bind_tools(ALL_LC_TOOLS)
        self._tools          = tools
        self._max_iterations = max_iterations

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(
        self,
        user_query: str,
        file_ids:   list[UUID] | None = None,
        history:    list[BaseMessage] | None = None,
    ) -> AgentLoopResult:
        """
        Execute the agent loop for one chat turn.

        Args:
            user_query: The user's text query.
            file_ids:   UUIDs of attached files (injected into the first message).
            history:    Trimmed conversation history as LangChain messages.

        Returns:
            AgentLoopResult with the final answer and loop metadata.
        """
        messages = self._build_initial_messages(user_query, file_ids, history)
        
        iterations = 0

        while iterations < self._max_iterations:
            iterations += 1
            logger.debug("AgentLoop: iteration %d / %d", iterations, self._max_iterations)

            # LLM decides next action(s)
            response: AIMessage = await self._llm_with_tools.ainvoke(messages)
            messages.append(response)

            # No tool calls → LLM gave a direct response (shouldn't happen
            # given the prompt, but handle it gracefully)
            if not response.tool_calls:
                logger.warning(
                    "AgentLoop: LLM responded without tool calls at iteration %d",
                    iterations,
                )
                text = response.content if isinstance(response.content, str) else ""
                return AgentLoopResult(
                    answer=text or "I was unable to produce an answer.",
                    iterations=iterations,
                )

            # Check if finish() is among the tool calls — extract answer first
            finish_call = self._find_finish_call(response.tool_calls) # type: ignore
            if finish_call:
                answer = finish_call.get("args", {}).get("answer", "")
                logger.debug("AgentLoop: finish() called after %d iterations", iterations)
                return AgentLoopResult(answer=answer, iterations=iterations)

            # Execute all tool calls in this response in parallel
            tool_messages = await self._execute_tool_calls(response.tool_calls) # type: ignore
            messages.extend(tool_messages)

        # Hit iteration cap — try to extract a partial answer from history
        logger.warning(
            "AgentLoop: hit max_iterations (%d) without finish()", self._max_iterations
        )
        partial = self._extract_partial_answer(messages)
        return AgentLoopResult(
            answer=partial,
            iterations=iterations,
            hit_limit=True,
        )

    # ------------------------------------------------------------------
    # Private — message construction
    # ------------------------------------------------------------------

    def _build_initial_messages(
        self,
        user_query: str,
        file_ids:   list[UUID] | None,
        history:    list[BaseMessage] | None,
    ) -> list[BaseMessage]:
        messages: list[BaseMessage] = []

        # System prompt
        messages.append(SystemMessage(content=ENGINEERING_AGENT_SYSTEM_PROMPT))

        # Conversation history (already trimmed by ConversationManager)
        if history:
            messages.extend(history)

        # Current user turn — inject file_ids explicitly so the LLM
        # knows to call extract_file() for each one
        user_content = self._build_user_content(user_query, file_ids)
        messages.append(HumanMessage(content=user_content))

        return messages

    @staticmethod
    def _build_user_content(user_query: str, file_ids: list[UUID] | None) -> str:
        if not file_ids:
            return user_query

        ids_block = "\n".join(f"  - {fid}" for fid in file_ids)
        return (
            f"{user_query}\n\n"
            f"Attached files (call extract_file for each before doing anything else):\n"
            f"{ids_block}"
        )

    # ------------------------------------------------------------------
    # Private — tool execution
    # ------------------------------------------------------------------

    async def _execute_tool_calls(
        self,
        tool_calls: list[dict[str, Any]],
    ) -> list[ToolMessage]:
        """
        Execute all tool calls from one LLM response in parallel.
        Returns a list of ToolMessage objects to append to history.
        """
        async def _run_one(tc: dict[str, Any]) -> ToolMessage:
            tool_name = tc["name"]
            tool_args = tc.get("args", {})
            tool_id   = tc.get("id", tool_name)

            result_json = await self._tools.execute(tool_name, tool_args)

            logger.debug(
                "AgentLoop: tool=%s id=%s result_len=%d",
                tool_name, tool_id, len(result_json),
            )

            return ToolMessage(
                content=result_json,
                tool_call_id=tool_id,
                name=tool_name,
            )

        results = await asyncio.gather(
            *[_run_one(tc) for tc in tool_calls],
            return_exceptions=True,
        )

        tool_messages: list[ToolMessage] = []
        for i, r in enumerate(results):
            if isinstance(r, BaseException):
                tc = tool_calls[i]
                logger.error("AgentLoop: tool %s failed: %s", tc["name"], r)
                tool_messages.append(ToolMessage(
                    content=json.dumps({"error": str(r)[:200]}),
                    tool_call_id=tc.get("id", tc["name"]),
                    name=tc["name"],
                ))
            else:
                tool_messages.append(r)

        return tool_messages

    # ------------------------------------------------------------------
    # Private — helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _find_finish_call(tool_calls: list[dict[str, Any]]) -> dict | None:
        """Return the finish() tool call dict if present, else None."""
        for tc in tool_calls:
            if tc.get("name") == AgentTools.FINISH:
                return tc
        return None

    @staticmethod
    def _extract_partial_answer(messages: list[BaseMessage]) -> str:
        """
        Fallback: scan message history in reverse for any substantive
        AI text content when the loop hits the iteration cap.
        """
        for msg in reversed(messages):
            if isinstance(msg, AIMessage):
                content = msg.content
                if isinstance(content, str) and len(content.strip()) > 20:
                    return (
                        f"[Note: the agent reached its reasoning limit. "
                        f"Partial response below.]\n\n{content.strip()}"
                    )
        return (
            "I was unable to complete the answer within the allowed number "
            "of reasoning steps. Please try with a more specific question."
        )
