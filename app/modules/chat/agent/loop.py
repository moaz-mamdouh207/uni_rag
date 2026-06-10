from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import TYPE_CHECKING, Any

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
from modules.chat.agent.tools import AgentTools
from modules.chat.schemas import CitedSource
from shared.tracing import observe, observe_generation, set_trace_attributes
from db.relational.constants import MessageRole

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# LangChain tool stubs
# ---------------------------------------------------------------------------

from langchain_core.tools import tool as lc_tool


@lc_tool
def retrieve(query: str, chunk_type: str | None = None, context_hint: str | None = None) -> str:
    """
    Search the course knowledge base for a single concept, formula, or principle.

    chunk_type: REQUIRED for targeted retrieval.
      - "theory"          → definitions, formulas, conceptual background
      - "solved_question" → worked examples from the reference book

    context_hint: the specific engineering sub-field, e.g. 'beam bending',
    'Bernoulli equation', 'Mohr circle stress'. Always provide it.

    Results include a chunk_id field — copy it exactly into your %%CITATIONS%%
    block when you cite that chunk in your answer.

    # execution: AgentTools._retrieve
    """
    ...


@lc_tool
def retrieve_multi(queries: list[dict]) -> str:
    """
    Search the knowledge base for multiple independent concepts in parallel.

    Each query object accepts:
      - "query"        (required)
      - "chunk_type"   (required: "theory" or "solved_question")
      - "context_hint" (recommended)

    For every engineering question you should issue at least two queries:
      1. chunk_type="theory"          — to get the relevant formulas/concepts
      2. chunk_type="solved_question" — to get a worked example of the same type

    Results include a chunk_id field — copy it exactly into your %%CITATIONS%%
    block when you cite that chunk in your answer. Your [N] numbers are assigned
    by you in order of first appearance in the answer, not from the result index.

    # execution: AgentTools._retrieve_multi
    """
    ...


@lc_tool
def calculate(expression: str) -> str:
    """
    Evaluate a mathematical expression with full precision using a symbolic math engine.
    Supports arithmetic, algebra, trigonometry, logarithms, square roots, and equation solving.

    Single expression:       (15 * 6**2) / 8
    Square root:             sqrt(144)
    Trig:                    sin(pi/4)
    Solve equation:          solve(x**2 - 4, x)
    Multi-step (semicolons): z = 1/sqrt(2); w = z * 3; [z, w]

    Always use ** for exponentiation, not ^.
    Always call this for any numerical computation — never compute in your head.
    # execution: AgentTools._calculate
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
    # execution: AgentTools._clarify_question
    """
    ...


@lc_tool
def finish(answer: str) -> str:
    """
    Deliver the final answer to the user and end the loop.
    Call this only when you have retrieved all necessary context and completed
    all calculations.

    CITATION FORMAT (mandatory):
    1. Inline: every time you use a retrieved chunk, write [N] at the end of
       the sentence, where N is the `index` field from that chunk's result.
       Example: "Applying Ohm's law to the circuit gives V = IR [3]."

    2. Citation block: append this block at the very end of your answer,
       listing only the chunks you actually cited inline:

       %%CITATIONS%%
       [1] citation_id=<citation_id> type=<theory|solved_question>
       [2] citation_id=<citation_id> type=<theory|solved_question>
       %%END_CITATIONS%%

    Rules:
    - Only cite theory chunks you directly used for a formula or concept.
    - Only cite solved_question chunks whose worked example is structurally
      similar to the question being solved (same problem type, same unknowns).
    - Never list a chunk in %%CITATIONS%% that you did not reference inline.
    - The %%CITATIONS%% block must be the absolute last thing in the answer.

    RESPONSE STYLE:
    - Each equation gets its own line with blank lines before and after.
    - Each step opens with one sentence of intent, then shows the math.
    - Numerical results are always on their own line: "Result: ζ = 0.303"
    - Use bold for final answers: **ζ = 0.303**
    - Never write "substituting x=1 into F=ma we get F=1" — break it into three lines.
    # execution: terminates loop, answer returned to user
    """
    ...


ALL_LC_TOOLS = [retrieve, retrieve_multi, calculate, clarify_question, finish]


# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------

class AgentLoopResult(BaseModel):
    answer:        str
    iterations:    int
    hit_limit:     bool = False
    cited_sources: list[CitedSource] = []


# ---------------------------------------------------------------------------
# AgentLoop
# ---------------------------------------------------------------------------

class AgentLoop:
    def __init__(
        self,
        llm:            ChatGoogleGenerativeAI,
        tools:          AgentTools,
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
        user_query:      str,
        attachment_contents: list[str] | None = None,
        history:         list = [],
        trace_metadata:  dict | None = None,
    ) -> AgentLoopResult:
        history = self._orm_history_to_lc(history)

        turn_start = time.perf_counter()
        tool_call_counts: dict[str, int] = {}

        with observe(
            name="agent_turn",
            input={
                "query":            user_query,
                "files_count":      len(attachment_contents or []),
                "history_messages": len(history or []),
            },
            metadata={
                "max_iterations": self._max_iterations,
                **(trace_metadata or {}),
            },
        ) as turn_span:

            if trace_metadata:
                set_trace_attributes(
                    user_id=trace_metadata.get("user_id"),
                    session_id=trace_metadata.get("conversation_id"),
                    metadata=trace_metadata,
                )

            messages = self._build_initial_messages(user_query, attachment_contents, history)
            iterations = 0

            while iterations < self._max_iterations:
                iterations += 1
                logger.debug("AgentLoop: iteration %d / %d", iterations, self._max_iterations)

                with observe_generation(
                    name=f"llm_call_iter_{iterations}",
                    input={
                        "messages": [
                            {
                                "role":    _msg_role(m),
                                "content": _msg_content(m)[:5000],
                            }
                            for m in messages
                        ]
                    },
                    metadata={"iteration": iterations},
                ) as llm_gen:
                    t_llm = time.perf_counter()
                    response: AIMessage = await self._llm_with_tools.ainvoke(messages)

                    usage = getattr(response, "usage_metadata", None) or {}
                    requested_tools = [tc.get("name") for tc in (response.tool_calls or [])]

                    llm_gen.update(
                        output={
                            "tool_calls_requested": requested_tools,
                            "tool_calls_count":     len(requested_tools),
                            "has_finish":           AgentTools.FINISH in requested_tools,
                            "text_content": (
                                response.content[:300]
                                if isinstance(response.content, str) and response.content.strip()
                                else None
                            ),
                        },
                        usage={
                            "input":  usage.get("input_tokens"),
                            "output": usage.get("output_tokens"),
                        },
                        metadata={
                            "iteration":   iterations,
                            "duration_ms": int((time.perf_counter() - t_llm) * 1000),
                        },
                    )

                messages.append(response)

                for name in requested_tools:
                    tool_call_counts[name] = tool_call_counts.get(name, 0) + 1

                # ── No tool calls ─────────────────────────────────────────
                if not response.tool_calls:
                    logger.warning(
                        "AgentLoop: LLM responded without tool calls at iteration %d", iterations
                    )
                    text = response.content if isinstance(response.content, str) else ""
                    clean_answer, cited = self._tools.parse_answer_and_citations(
                        text or "I was unable to produce an answer."
                    )
                    result = AgentLoopResult(
                        answer=clean_answer,
                        iterations=iterations,
                        cited_sources=cited,
                    )
                    turn_span.update(**self._turn_output(result, tool_call_counts, turn_start, "no_tool_calls"))
                    return result

                # ── finish() detected ─────────────────────────────────────
                finish_call = self._find_finish_call(response.tool_calls)  # type: ignore
                if finish_call:
                    other_calls = [
                        tc for tc in response.tool_calls  # type: ignore
                        if tc.get("name") != AgentTools.FINISH
                    ]
                    if other_calls:
                        logger.warning(
                            "AgentLoop: LLM called finish() alongside %d other tool(s) "
                            "at iteration %d — the other calls will be dropped.",
                            len(other_calls), iterations,
                        )

                    raw_answer = finish_call.get("args", {}).get("answer", "")
                    clean_answer, cited = self._tools.parse_answer_and_citations(raw_answer)

                    logger.debug(
                        "AgentLoop: finish() called after %d iterations, %d citations",
                        iterations, len(cited),
                    )
                    result = AgentLoopResult(
                        answer=clean_answer,
                        iterations=iterations,
                        cited_sources=cited,
                    )
                    turn_span.update(**self._turn_output(result, tool_call_counts, turn_start, "finish"))
                    return result

                # ── Execute tool calls ────────────────────────────────────
                tool_messages = await self._execute_tool_calls(response.tool_calls)  # type: ignore
                messages.extend(tool_messages)

            # ── Hit iteration cap ─────────────────────────────────────────
            logger.warning("AgentLoop: hit max_iterations (%d) without finish()", self._max_iterations)
            partial = self._extract_partial_answer(messages)
            clean_answer, cited = self._tools.parse_answer_and_citations(partial)
            result = AgentLoopResult(
                answer=clean_answer,
                iterations=iterations,
                hit_limit=True,
                cited_sources=cited,
            )
            turn_span.update(**self._turn_output(result, tool_call_counts, turn_start, "hit_limit"))
            return result

    # ------------------------------------------------------------------
    # Private — trace output helper
    # ------------------------------------------------------------------

    @staticmethod
    def _turn_output(
        result:             AgentLoopResult,
        tool_call_counts:   dict[str, int],
        turn_start:         float,
        termination_reason: str,
    ) -> dict:
        return {
            "output": {"answer": result.answer},
            "metadata": {
                "iterations":           result.iterations,
                "hit_limit":            result.hit_limit,
                "termination_reason":   termination_reason,
                "total_duration_ms":    int((time.perf_counter() - turn_start) * 1000),
                "tool_call_counts":     tool_call_counts,
                "total_tool_calls":     sum(tool_call_counts.values()),
                "sources_count":        len(result.cited_sources),
            },
        }

    # ------------------------------------------------------------------
    # Private — message construction
    # ------------------------------------------------------------------

    def _build_initial_messages(
        self,
        user_query:      str,
        attachment_contents: list[str] | None,
        history:         list[BaseMessage] | None,
    ) -> list[BaseMessage]:
        messages: list[BaseMessage] = [SystemMessage(content=ENGINEERING_AGENT_SYSTEM_PROMPT)]
        if history:
            messages.extend(history)
        messages.append(HumanMessage(content=self._build_user_content(user_query, attachment_contents)))
        return messages

    @staticmethod
    def _build_user_content(
        user_query:      str,
        attachment_contents: list[str] | None,
    ) -> str:
        if not attachment_contents:
            return user_query

        files_block = "\n\n".join(
            f"--- File {i+1} ---\n{c}"
            for i, c in enumerate(attachment_contents)
            if c != "NO_ITEMS_FOUND"
        )
        if not files_block:
            return user_query

        return f"{user_query}\n\n### Extracted content of the attached files\n{files_block}"

    # ------------------------------------------------------------------
    # Private — tool execution
    # ------------------------------------------------------------------

    async def _execute_tool_calls(
        self,
        tool_calls: list[dict[str, Any]],
    ) -> list[ToolMessage]:
        async def _run_one(tc: dict[str, Any]) -> ToolMessage:
            tool_name   = tc["name"]
            tool_args   = tc.get("args", {})
            tool_id     = tc.get("id", tool_name)
            result_json = await self._tools.execute(tool_name, tool_args)
            logger.debug(
                "AgentLoop: tool=%s id=%s result_len=%d",
                tool_name, tool_id, len(result_json),
            )
            return ToolMessage(content=result_json, tool_call_id=tool_id, name=tool_name)

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
        for tc in tool_calls:
            if tc.get("name") == AgentTools.FINISH:
                return tc
        return None

    @staticmethod
    def _extract_partial_answer(messages: list[BaseMessage]) -> str:
        for msg in reversed(messages):
            if isinstance(msg, AIMessage):
                content = msg.content
                if isinstance(content, str) and len(content.strip()) > 20:
                    return (
                        "[Note: the agent reached its reasoning limit. "
                        "Partial response below.]\n\n" + content.strip()
                    )
        return (
            "I was unable to complete the answer within the allowed number of "
            "reasoning steps. Please try with a more specific question."
        )
    
    @staticmethod
    def _orm_history_to_lc(history: list) -> list[BaseMessage]:
        lc: list[BaseMessage] = []
        for msg in history:
            if msg.role == MessageRole.user:
                lc.append(HumanMessage(content=msg.content))
            elif msg.role == MessageRole.assistant:
                lc.append(AIMessage(content=msg.content))
        return lc


# ---------------------------------------------------------------------------
# Message helpers
# ---------------------------------------------------------------------------

def _msg_role(msg: BaseMessage) -> str:
    if isinstance(msg, SystemMessage): return "system"
    if isinstance(msg, HumanMessage):  return "user"
    if isinstance(msg, AIMessage):     return "assistant"
    if isinstance(msg, ToolMessage):   return "tool"
    return "unknown"


def _msg_content(msg: BaseMessage) -> str:
    if isinstance(msg.content, str):
        return msg.content
    return json.dumps(msg.content)


