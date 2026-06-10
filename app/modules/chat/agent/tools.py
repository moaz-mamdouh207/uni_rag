from __future__ import annotations

import ast
import asyncio
import logging
import re
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
from modules.chat.schemas import  CitedSource
from db.relational.constants  import ChunkType
from shared.tracing import observe, safe_truncate

if TYPE_CHECKING:
    from modules.chat.config import ChatSettings
    from modules.retrieval.service import RetrievalService

logger = logging.getLogger(__name__)

# Regex that matches the citation block appended by the agent in finish()
_CITATION_BLOCK_RE = re.compile(
    r"%%CITATIONS%%\s*(.*?)\s*%%END_CITATIONS%%",
    re.DOTALL,
)
# Matches one citation line: [N] citation_id=<id> type=<type>
_CITATION_LINE_RE = re.compile(
    r"\[(\d+)\]\s+citation_id=([\w\-]+)\s+type=(\w+)"
)


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
        settings:          "ChatSettings",
        user_id:           UUID,
        course_id:         UUID,
        documents_ids:     list[UUID] | None = None,
    ) -> None:
        self._retrieval  = retrieval_service
        self._settings   = settings
        self._user_id    = user_id
        self._course_id  = course_id
        self._doc_ids    = documents_ids

        # Keyed by citation_id (chunk_id as str) -> RetrieveResultItem.
        # Indices are globally monotonic across the whole turn so [N] in the
        # agent's answer always maps to a unique chunk.
        self._retrieved_by_id: dict[str, RetrieveResultItem] = {}
        self._global_index: int = 0  # incremented for every new unique chunk

    # ------------------------------------------------------------------
    # Dispatch
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
    # Citation parsing  (called from AgentLoop after finish())
    # ------------------------------------------------------------------

    def parse_answer_and_citations(self, raw_answer: str) -> tuple[str, list[CitedSource]]:
        """
        Extract the %%CITATIONS%% block from the agent's raw finish() answer.

        Returns:
            clean_answer  — answer text with the citation block stripped out
            cited_sources — CitedSource list built from the declared chunk IDs,
                            ordered by inline index
        """
        match = _CITATION_BLOCK_RE.search(raw_answer)
        if not match:
            # Agent didn't append a citation block — return as-is with no sources
            logger.warning("AgentTools: no %%CITATIONS%% block found in answer")
            return raw_answer, []

        # Strip the block (and any leading blank line before it) from the answer
        clean_answer = _CITATION_BLOCK_RE.sub("", raw_answer).rstrip()

        cited: list[CitedSource] = []
        seen_chunk_ids: set[str] = set()

        for line in match.group(1).splitlines():
            line = line.strip()
            if not line:
                continue
            m = _CITATION_LINE_RE.match(line)
            if not m:
                logger.warning("AgentTools: unrecognised citation line: %r", line)
                continue

            inline_index = int(m.group(1))
            chunk_id     = str(m.group(2))   # always str — matches _retrieved_by_id keys
            chunk_type   = m.group(3)

            if chunk_id in seen_chunk_ids:
                logger.warning("AgentTools: duplicate chunk_id %r in citation block, skipping", chunk_id)
                continue
            seen_chunk_ids.add(chunk_id)

            item = self._retrieved_by_id.get(chunk_id)
            if item is None:
                logger.warning(
                    "AgentTools: agent cited chunk_id=%r which was never retrieved — "
                    "known ids: %s",
                    chunk_id,
                    list(self._retrieved_by_id.keys())[:10],   # log first 10 for debugging
                )
                continue

            cited.append(CitedSource(
                inline_index=inline_index,
                chunk_id=chunk_id,
                document_id=item.document_id,
                chunk_type=chunk_type,
                score=item.score,
                full_content=item.content,
                content_preview=item.content[:200],
                starting_page=item.starting_page,
                end_page=item.end_page,
            ))

        # Sort by order of appearance in the text, not by score
        cited.sort(key=lambda s: s.inline_index)
        return clean_answer, cited

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
            type=inp.chunk_type,
        )

        items = self._register_results(response.results, inp.chunk_type)

        logger.debug(
            "retrieve: query=%r hint=%r type=%r results=%d scores=%s",
            inp.query,
            inp.context_hint,
            inp.chunk_type,
            len(items),
            [round(r.score, 3) for r in items],
        )

        return RetrieveOutput(query=inp.query, results=items, total=len(items))

    # ------------------------------------------------------------------
    # retrieve_multi
    # ------------------------------------------------------------------

    async def _retrieve_multi(self, inp: RetrieveMultiInput) -> RetrieveMultiOutput:
        tasks = [
            self._retrieve(RetrieveInput(
                query=q.query,
                chunk_type=q.chunk_type,
                context_hint=q.context_hint,
            ))
            for q in inp.queries
        ]
        outcomes = await asyncio.gather(*tasks, return_exceptions=True)

        all_results: list[RetrieveResultItem] = []
        queries_run = 0

        for i, outcome in enumerate(outcomes):
            if isinstance(outcome, BaseException):
                logger.warning("retrieve_multi: query %d failed: %s", i, outcome)
                continue
            # Items are already registered with global indices by _retrieve;
            # just collect them for the combined output.
            all_results.extend(outcome.results)
            queries_run += 1

        # Deduplicate across queries while preserving the already-assigned indices.
        deduped = self._dedup_preserve_index(all_results)

        return RetrieveMultiOutput(
            queries_run=queries_run,
            results=deduped,
            total=len(deduped),
        )

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
                merged = {**sympy_ns, **local_ctx}
                parsed = sympify(stmt, locals=merged)

                if isinstance(parsed, list):
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
    # Internal registration — assigns globally unique indices
    # ------------------------------------------------------------------

    def _register_results(
        self,
        results: list[SearchResult],
        chunk_type: ChunkType | None,
    ) -> list[RetrieveResultItem]:
        """
        Convert SearchResult objects to RetrieveResultItems.
        citation_id is always stored as a plain str so dict lookups are reliable
        regardless of whether the retrieval service returns str or UUID objects.
        The `index` field is a sequential counter used only for display order in
        the tool result -- the agent does NOT use it as [N] in citations.
        """
        items: list[RetrieveResultItem] = []
        for r in results:
            cid = str(r.chunk_id)  # normalise to str -- UUID objects won't match str keys
            if cid in self._retrieved_by_id:
                items.append(self._retrieved_by_id[cid])
                continue

            self._global_index += 1
            resolved_type = chunk_type or getattr(r, "chunk_type", None)

            item = RetrieveResultItem(
                index=self._global_index,
                content=r.content,
                score=round(r.score, 4),
                citation_id=cid,
                document_id=str(r.document_id),
                chunk_type=resolved_type,
                starting_page=getattr(r, "starting_page", None),
                end_page=getattr(r, "end_page", None),
            )
            self._retrieved_by_id[cid] = item
            items.append(item)
        return items

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _dedup_preserve_index(
        results: list[RetrieveResultItem],
    ) -> list[RetrieveResultItem]:
        """
        Deduplicate by chunk_id, keeping the item with the higher score.
        Preserves already-assigned indices — does NOT re-index.
        """
        seen: dict[str, RetrieveResultItem] = {}
        for r in results:
            if r.citation_id not in seen or r.score > seen[r.citation_id].score:
                seen[r.citation_id] = r
        return sorted(seen.values(), key=lambda x: x.score, reverse=True)