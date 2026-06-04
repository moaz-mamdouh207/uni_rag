"""
Tool executors for the engineering RAG agent.

Each method in AgentTools corresponds to one tool the LLM can call.
This class holds all the dependencies needed to execute tools and is
passed into the agent loop.

Tool execution is fully decoupled from the loop controller (loop.py) —
the loop only knows about tool names and JSON; this class does the work.
"""
from __future__ import annotations

import asyncio
import logging
import re
from typing import TYPE_CHECKING
from uuid import UUID
import ast

from sympy import sympify, solve, SympifyError, Symbol, abc
from sympy.core.sympify import SympifyError

from db.vector.schemas import SearchQuery, SearchResult
from modules.chat.agent.tool_schemas import (
    CalculateInput,
    CalculateOutput,
    ClarifyQuestionInput,
    ClarifyQuestionOutput,
    ExtractFileInput,
    ExtractFileOutput,
    FinishInput,
    FinishOutput,
    RetrieveInput,
    RetrieveMultiInput,
    RetrieveMultiOutput,
    RetrieveOutput,
    RetrieveResultItem,
)

if TYPE_CHECKING:
    from modules.chat.config import ChatSettings
    from modules.chat.file_processor import FileProcessor
    from modules.retrieval.service import RetrievalService

logger = logging.getLogger(__name__)


class AgentTools:
    """
    Executes all tool calls on behalf of the agent loop.

    Args:
        retrieval_service: For retrieve / retrieve_multi.
        file_processor:    For extract_file.
        settings:          ChatSettings — top_k, score_threshold, rerank.
        user_id:           Scopes retrieval to the current user.
        course_id:         Scopes retrieval to the current course.
        documents_ids:     Optional doc filter passed to retrieval.
    """

    # Tool name constants — single source of truth used by loop.py
    EXTRACT_FILE       = "extract_file"
    RETRIEVE           = "retrieve"
    RETRIEVE_MULTI     = "retrieve_multi"
    CALCULATE          = "calculate"
    CLARIFY_QUESTION   = "clarify_question"
    FINISH             = "finish"

    ALL_TOOL_NAMES = {
        EXTRACT_FILE,
        RETRIEVE,
        RETRIEVE_MULTI,
        CALCULATE,
        CLARIFY_QUESTION,
        FINISH,
    }

    def __init__(
        self,
        retrieval_service: RetrievalService,
        file_processor:    FileProcessor,
        settings:          ChatSettings,
        user_id:           UUID,
        course_id:         UUID,
        documents_ids:     list[UUID] | None = None,
    ) -> None:
        self._retrieval    = retrieval_service
        self._file_proc    = file_processor
        self._settings     = settings
        self._user_id      = user_id
        self._course_id    = course_id
        self._doc_ids      = documents_ids

    # ------------------------------------------------------------------
    # Dispatch — called by the loop for every tool call
    # ------------------------------------------------------------------

    async def execute(self, tool_name: str, tool_input: dict) -> str:
        """
        Dispatch a tool call by name and return the result as a JSON string
        ready to be injected into the agent message history.

        Returns an error JSON string on failure rather than raising —
        the agent should see the error and decide how to recover.
        """
        try:
            if tool_name == self.EXTRACT_FILE:
                result = await self._extract_file(ExtractFileInput(**tool_input))
            elif tool_name == self.RETRIEVE:
                result = await self._retrieve(RetrieveInput(**tool_input))
            elif tool_name == self.RETRIEVE_MULTI:
                result = await self._retrieve_multi(RetrieveMultiInput(**tool_input))
            elif tool_name == self.CALCULATE:
                result = self._calculate(CalculateInput(**tool_input))
            elif tool_name == self.CLARIFY_QUESTION:
                result = self._clarify_question(ClarifyQuestionInput(**tool_input))
            elif tool_name == self.FINISH:
                result = FinishOutput(**tool_input)
            else:
                return f'{{"error": "Unknown tool: {tool_name}"}}'

            return result.model_dump_json()

        except Exception as exc:
            logger.warning("Tool '%s' raised: %s", tool_name, exc, exc_info=True)
            return f'{{"error": "{tool_name} failed: {str(exc)[:200]}"}}'

    # ------------------------------------------------------------------
    # extract_file
    # ------------------------------------------------------------------

    async def _extract_file(self, inp: ExtractFileInput) -> ExtractFileOutput:
        print("extract file")
        extractions = await self._file_proc.process([inp.file_id])
        print(extractions)
        print("\n######"*5)

        if not extractions:
            return ExtractFileOutput(
                file_id=inp.file_id,
                file_type="unknown",
                markdown_content="NO_ITEMS_FOUND",
                item_count=0,
            )

        extraction = extractions[0]
        item_count  = len(re.findall(r"^## Item", extraction.markdown_content, re.MULTILINE))

        return ExtractFileOutput(
            file_id=extraction.file_id,
            file_type=extraction.file_type,
            markdown_content=extraction.markdown_content,
            item_count=item_count,
        )

    # ------------------------------------------------------------------
    # retrieve
    # ------------------------------------------------------------------

    async def _retrieve(self, inp: RetrieveInput) -> RetrieveOutput:
        query_text = (
            f"{inp.context_hint}: {inp.query}"
            if inp.context_hint
            else inp.query
        )
        print("retrieve")
        print(query_text)
        print("\n######"*5)

        search_query = SearchQuery(
            query=query_text,
            top_k=self._settings.top_k,
            score_threshold=self._settings.score_threshold,
            rerank=self._settings.rerank,
        )

        response = await self._retrieval.retrieve(
            request=search_query,
            user_id=self._user_id,
            course_id=self._course_id,
            documents_ids=self._doc_ids,
        )

        return RetrieveOutput(
            query=inp.query,
            results=self._format_results(response.results),
            total=len(response.results),
        )

    # ------------------------------------------------------------------
    # retrieve_multi
    # ------------------------------------------------------------------

    async def _retrieve_multi(self, inp: RetrieveMultiInput) -> RetrieveMultiOutput:
        tasks = [
            self._retrieve(RetrieveInput(
                query=q.query,
                context_hint=q.context_hint,
            ))
            for q in inp.queries
        ]

        outcomes = await asyncio.gather(*tasks, return_exceptions=True)

        all_results: list[RetrieveResultItem] = []
        queries_run = 0

        for i, outcome in enumerate(outcomes):
            if isinstance(outcome, BaseException):
                logger.warning(
                    "retrieve_multi: query %d failed: %s",
                    i, outcome
                )
                continue
            all_results.extend(outcome.results)
            queries_run += 1

        # Deduplicate by (document_id, content prefix), keep highest score
        deduped = self._dedup(all_results)

        # Re-index after dedup
        for idx, r in enumerate(deduped):
            r.index = idx + 1

        return RetrieveMultiOutput(
            queries_run=queries_run,
            results=deduped,
            total=len(deduped),
        )

    # ------------------------------------------------------------------
    # calculate
    # ------------------------------------------------------------------

    def _calculate(self, inp: CalculateInput) -> CalculateOutput:
        """
        Evaluate a mathematical expression via sympy.
        Supports: arithmetic, algebra, solve(), and multi-statement assignments/evaluations.
        Single Expression: calculate(expression="4 - 4 / (z * w)")

        Solve Systems: solve([eq1, eq2], [var1, var2])

        Multi-Statement / Variable Assignments: 
        Separate each assignment and the final target expression array with a semicolon ;. Keep everything on a single line.
        Example: calculate(expression="z = 1/sqrt(1 + pi**2); w = sqrt(1 + pi**2); M = 1 / (2 * z * w); K = M * w**2; [M, K, z]")
        """
        expression = inp.expression.strip()
        print("calc")
        print(expression)

        try:
            if expression.startswith("solve("):
                result = self._handle_solve(expression)
            
            # Handle multi-statement execution or assignment code strings
            elif ";" in expression or "=" in expression:
                # Create a local execution context containing all standard sympy functions
                import sympy
                local_context = {cls: getattr(sympy, cls) for cls in sympy.__all__}
                
                # Split the statements by semicolon and strip whitespace
                statements = [s.strip() for s in expression.split(";") if s.strip()]
                
                result = ""
                for i, stmt in enumerate(statements):
                    if "=" in stmt:
                        # Execute assignment statements to store variables in local_context
                        exec(stmt, {}, local_context)
                    else:
                        # If it's the last statement and an expression, evaluate it
                        if i == len(statements) - 1:
                            parsed = sympify(stmt, locals=local_context)
                            # Attempt to evaluate numerically if possible
                            try:
                                result = str(parsed.evalf())
                            except AttributeError:
                                result = str(parsed)
                        else:
                            # Fallback/intermediate expression execution
                            exec(stmt, {}, local_context)
            
            else:
                # Standard single expression fallback
                parsed = sympify(expression)
                evaluated = parsed.evalf()
                result = str(evaluated)

            print(f"\n{result}")
            print("\n######" * 5)
            return CalculateOutput(
                expression=expression,
                result=result,
                success=True,
                )

        except Exception as exc:
            logger.warning("calculate: failed for '%s': %s", expression, exc)
            return CalculateOutput(
                expression=expression,
                result="",
                success=False,
                error=str(exc),
            )

    @staticmethod
    def _handle_solve(expression: str) -> str:
        """
        Parse and execute solve() calls for single equations or systems of equations.
        Examples:
        solve(x**2 - 4, x)
        solve([4 - 4/(z*w), 1 - 3/(w*sqrt(1-z**2))], [z, w])
        """
        # Strip "solve(" prefix and ")" suffix
        inner = expression[len("solve("):-1].strip()

        try:
            # Wrap the inner contents in brackets to parse it safely as a standard Python tuple
            # e.g., "eq, var" or "[eq1, eq2], [var1, var2]" -> ([eq1, eq2], [var1, var2])
            parsed_args = ast.parse(f"({inner})", mode="eval").body
            
            if not isinstance(parsed_args, ast.Tuple) or len(parsed_args.elts) != 2:
                raise ValueError("solve() requires two main arguments: equation(s) and variable(s).")
                
            # Convert the AST nodes back into raw strings to pass to sympify
            # unparse() is available in Python 3.9+
            eq_str = ast.unparse(parsed_args.elts[0])
            var_str = ast.unparse(parsed_args.elts[1])

        except Exception:
            # Fallback to your original logic if AST parsing fails completely
            parts = [p.strip() for p in inner.rsplit(",", 1)]
            if len(parts) != 2:
                raise ValueError(f"Could not parse solve arguments: '{inner}'")
            eq_str, var_str = parts

        # Now sympify both parts safely
        eq = sympify(eq_str)
        var = sympify(var_str)
        
        result = solve(eq, var)
        return str(result)

    # ------------------------------------------------------------------
    # clarify_question
    # ------------------------------------------------------------------

    @staticmethod
    def _clarify_question(inp: ClarifyQuestionInput) -> ClarifyQuestionOutput:
        """Pure context injection — records interpretation, no I/O."""
        return ClarifyQuestionOutput(
            recorded=True,
            original_text=inp.original_text,
            interpretation=inp.interpretation,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _format_results(results: list[SearchResult]) -> list[RetrieveResultItem]:
        return [
            RetrieveResultItem(
                index=i + 1,
                content=r.content,
                score=round(r.score, 4),
                document_id=r.document_id,
            )
            for i, r in enumerate(results)
        ]

    @staticmethod
    def _dedup(results: list[RetrieveResultItem]) -> list[RetrieveResultItem]:
        """Keep highest-score occurrence of each chunk, sort descending."""
        import hashlib
        seen: dict[str, RetrieveResultItem] = {}
        for r in results:
            key = f"{r.document_id}::{hashlib.md5(r.content[:200].lower().encode(), usedforsecurity=False).hexdigest()}"
            if key not in seen or r.score > seen[key].score:
                seen[key] = r
        return sorted(seen.values(), key=lambda x: x.score, reverse=True)
