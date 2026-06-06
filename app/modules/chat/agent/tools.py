from __future__ import annotations

import ast
import asyncio
import logging
import time
from typing import TYPE_CHECKING, Any
from uuid import UUID

from db.vector.schemas import SearchQuery, SearchResult
from modules.chat.agent.tool_schemas import (
    CalculateInput,
    CalculateOutput,
    ClarifyQuestionInput,
    ClarifyQuestionOutput,
    FinishOutput,
    RetrieveInput,
    RetrieveMultiInput,
    RetrieveMultiOutput,
    RetrieveOutput,
    RetrieveResultItem,
)
from modules.chat.schemas import CitedSource
from shared.tracing import observe, safe_truncate

if TYPE_CHECKING:
    from modules.chat.config import ChatSettings
    from modules.retrieval.service import RetrievalService

logger = logging.getLogger(__name__)


class AgentTools:
    RETRIEVE         = "retrieve"
    RETRIEVE_MULTI   = "retrieve_multi"
    CALCULATE        = "calculate"
    CLARIFY_QUESTION = "clarify_question"
    FINISH           = "finish"

    ALL_TOOL_NAMES = {RETRIEVE, RETRIEVE_MULTI, CALCULATE, CLARIFY_QUESTION, FINISH}

    def __init__(
        self,
        retrieval_service: RetrievalService,
        settings:          ChatSettings,
        user_id:           UUID,
        course_id:         UUID,
        documents_ids:     list[UUID] | None = None,
    ) -> None:
        self._retrieval  = retrieval_service
        self._settings   = settings
        self._user_id    = user_id
        self._course_id  = course_id
        self._doc_ids    = documents_ids
        self._all_retrieved: list[RetrieveResultItem] = []

    # ------------------------------------------------------------------
    # Dispatch — each tool call gets its own span, nested automatically
    # under whatever observe() context the loop opened for this iteration
    # ------------------------------------------------------------------

    async def execute(self, tool_name: str, tool_input: dict) -> str:
        with observe(f"tool/{tool_name}", input=safe_truncate(tool_input)) as span:
            t0 = time.perf_counter()
            try:
                if tool_name == self.RETRIEVE:
                    result = await self._retrieve(RetrieveInput(**tool_input))
                elif tool_name == self.RETRIEVE_MULTI:
                    result = await self._retrieve_multi(RetrieveMultiInput(**tool_input))
                elif tool_name == self.CALCULATE:
                    result = await asyncio.to_thread(self._calculate, CalculateInput(**tool_input))
                elif tool_name == self.CLARIFY_QUESTION:
                    result = self._clarify_question(ClarifyQuestionInput(**tool_input))
                elif tool_name == self.FINISH:
                    result = FinishOutput(**tool_input)
                else:
                    error_msg = f"Unknown tool: {tool_name}"
                    span.update(output={"error": error_msg})
                    return f'{{"error": "{error_msg}"}}'

                result_json = result.model_dump_json()
                span.update(
                    output=safe_truncate(result.model_dump()),
                    metadata={
                        "duration_ms": int((time.perf_counter() - t0) * 1000),
                        "result_chars": len(result_json),
                        "success": True,
                    },
                )
                return result_json

            except Exception as exc:
                logger.warning("Tool '%s' raised: %s", tool_name, exc, exc_info=True)
                span.update(
                    output={"error": str(exc)[:300]},
                    metadata={
                        "duration_ms": int((time.perf_counter() - t0) * 1000),
                        "success": False,
                    },
                )
                return f'{{"error": "{tool_name} failed: {str(exc)[:200]}"}}'

    # ------------------------------------------------------------------
    # Citation collection
    # ------------------------------------------------------------------

    def collect_cited_sources(self) -> list[CitedSource]:
        seen: dict[str, CitedSource] = {}
        for r in sorted(self._all_retrieved, key=lambda x: x.score, reverse=True):
            if r.chunk_id not in seen:
                seen[r.chunk_id] = CitedSource(
                    document_id=r.document_id,
                    chunk_index=r.index,
                    chunk_id=r.chunk_id,
                    score=r.score,
                    content_preview=r.content[:200],
                )
        return list(seen.values())

    # ------------------------------------------------------------------
    # retrieve
    # ------------------------------------------------------------------

    async def _retrieve(self, inp: RetrieveInput) -> RetrieveOutput:
        query_text = (
            f"{inp.context_hint}: {inp.query}" if inp.context_hint else inp.query
        )

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

        items = self._format_results(response.results)
        self._all_retrieved.extend(items)

        logger.debug(
            "retrieve: query=%r hint=%r results=%d scores=%s",
            inp.query,
            inp.context_hint,
            len(items),
            [round(r.score, 3) for r in items],
        )

        return RetrieveOutput(query=inp.query, results=items, total=len(items))

    # ------------------------------------------------------------------
    # retrieve_multi
    # ------------------------------------------------------------------

    async def _retrieve_multi(self, inp: RetrieveMultiInput) -> RetrieveMultiOutput:
        tasks = [
            self._retrieve(RetrieveInput(query=q.query, context_hint=q.context_hint))
            for q in inp.queries
        ]
        outcomes = await asyncio.gather(*tasks, return_exceptions=True)

        all_results: list[RetrieveResultItem] = []
        queries_run = 0

        for i, outcome in enumerate(outcomes):
            if isinstance(outcome, BaseException):
                logger.warning("retrieve_multi: query %d failed: %s", i, outcome)
                continue
            all_results.extend(outcome.results)
            queries_run += 1

        deduped = self._dedup(all_results)
        for idx, r in enumerate(deduped):
            r.index = idx + 1

        return RetrieveMultiOutput(queries_run=queries_run, results=deduped, total=len(deduped))

    # ------------------------------------------------------------------
    # calculate
    # ------------------------------------------------------------------

    def _calculate(self, inp: CalculateInput) -> CalculateOutput:
        expression = inp.expression.strip()
        logger.debug("calculate: expression=%r", expression)

        try:
            sympy_ns = self._build_sympy_namespace()

            if expression.startswith("solve("):
                result = self._handle_solve(expression, sympy_ns)
            elif ";" in expression or (
                "=" in expression and not expression.startswith("solve")
            ):
                result = self._handle_multi_statement(expression, sympy_ns)
            else:
                from sympy import sympify
                # Use sympy_ns only as locals (not merged into a mutable ctx)
                parsed = sympify(expression, locals=sympy_ns)
                try:
                    result = str(round(float(parsed.evalf()), 6))
                except (AttributeError, TypeError):
                    result = str(parsed)

            logger.debug("calculate: result=%r", result)
            return CalculateOutput(expression=expression, result=result, success=True)

        except Exception as exc:
            logger.warning("calculate: failed for '%s': %s", expression, exc)
            return CalculateOutput(
                expression=expression, result="", success=False, error=str(exc)[:300]
            )

    @staticmethod
    def _build_sympy_namespace() -> dict:
        import sympy
        ns: dict = {}
        for name in sympy.__all__:
            try:
                ns[name] = getattr(sympy, name)
            except AttributeError:
                pass
        return ns

    @staticmethod
    def _handle_solve(expression: str, sympy_ns: dict) -> str:
        from sympy import sympify, solve

        inner = expression[len("solve("):-1].strip()

        try:
            parsed_args = ast.parse(f"({inner})", mode="eval").body
            if not isinstance(parsed_args, ast.Tuple) or len(parsed_args.elts) != 2:
                raise ValueError("solve() requires exactly two arguments.")
            eq_str  = ast.unparse(parsed_args.elts[0])
            var_str = ast.unparse(parsed_args.elts[1])
        except Exception:
            parts = [p.strip() for p in inner.rsplit(",", 1)]
            if len(parts) != 2:
                raise ValueError(f"Could not parse solve() arguments: '{inner}'")
            eq_str, var_str = parts

        eq  = sympify(eq_str,  locals=sympy_ns)
        var = sympify(var_str, locals=sympy_ns)
        return str(solve(eq, var))

    @staticmethod
    def _handle_multi_statement(expression: str, sympy_ns: dict) -> str:
        from sympy import sympify

        # local_ctx holds ONLY user-assigned variables — never the sympy namespace.
        # sympy_ns is passed as the exec globals so sqrt/pi/exp etc. resolve,
        # but its contents never pollute local_ctx (fixes the '1.14.0' subs crash).
        local_ctx: dict = {}

        statements = [s.strip() for s in expression.split(";") if s.strip()]

        if not statements:
            raise ValueError("Empty expression after splitting on semicolons.")

        result = ""
        for i, stmt in enumerate(statements):
            is_last = (i == len(statements) - 1)

            if "=" in stmt and not stmt.startswith("["):
                exec(stmt, sympy_ns, local_ctx)  # nosec
            elif is_last:
                # Merge for sympify so user vars shadow sympy names if needed
                merged = {**sympy_ns, **local_ctx}
                parsed = sympify(stmt, locals=merged)

                if isinstance(parsed, list):
                    # Extract variable names from the list literal for clean keys
                    list_vars = [v.strip() for v in stmt.strip("[]").split(",")]
                    evaluated: dict[str, object] = {}
                    for j, sym in enumerate(parsed):
                        key = list_vars[j] if j < len(list_vars) else str(sym)
                        try:
                            evaluated[key] = round(float(sym.evalf()), 6)
                        except (AttributeError, TypeError):
                            evaluated[key] = str(sym)
                    result = str(evaluated)
                else:
                    try:
                        result = str(round(float(parsed.evalf()), 6))
                    except (AttributeError, TypeError):
                        result = str(parsed)
            else:
                exec(stmt, sympy_ns, local_ctx)  # nosec

        return result

    # ------------------------------------------------------------------
    # clarify_question
    # ------------------------------------------------------------------

    @staticmethod
    def _clarify_question(inp: ClarifyQuestionInput) -> ClarifyQuestionOutput:
        logger.debug(
            "clarify_question: text=%r interpretation=%r",
            inp.original_text[:100],
            inp.interpretation[:100],
        )
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
        items = []
        for i, r in enumerate(results):
            items.append(RetrieveResultItem(
                index=i + 1,
                content=r.content,
                score=round(r.score, 4),
                document_id=r.document_id,
                chunk_id=r.chunk_id,
                starting_page=getattr(r, "starting_page", None),
                end_page=getattr(r, "end_page", None),
            ))
        return items

    @staticmethod
    def _dedup(results: list[RetrieveResultItem]) -> list[RetrieveResultItem]:
        import hashlib
        seen: dict[str, RetrieveResultItem] = {}
        for r in results:
            key = f"{r.document_id}::{hashlib.md5(r.content[:200].lower().encode(), usedforsecurity=False).hexdigest()}"
            if key not in seen or r.score > seen[key].score:
                seen[key] = r
        return sorted(seen.values(), key=lambda x: x.score, reverse=True)