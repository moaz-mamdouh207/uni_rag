from __future__ import annotations
import asyncio
import logging
from typing import TYPE_CHECKING
from uuid import UUID
import json

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field, ConfigDict, PrivateAttr


from db.vector.schemas import SearchQuery
from modules.chat.schemas import CitationMetaData


if TYPE_CHECKING:
    pass
from db.relational.constants import ChunkType
from modules.chat.config import ChatSettings
from modules.retrieval.service import RetrievalService
from db.vector.schemas import SearchResult
from modules.chat.utils.temp import AgentState

logger = logging.getLogger(__name__)


class RetrieveQuery(BaseModel):
    query: str = Field(
        ...,
        min_length=1,
        description="The search query used to retrieve relevant chunks."
    )

    chunk_type: ChunkType = Field(
        ...,
        description=(
            "Filter results by chunk type. "
            "Use 'theory' for conceptual background, definitions, and formulas. "
            "Use 'solved_question' for worked examples from the reference book. "
        )
    )

    context_hint: str | None = Field(
        default=None,
        description=(
            "Short topic label prepended to the query to narrow the embedding search. "
            "E.g. 'fluid mechanics', 'beam bending', 'thermodynamics'."
        )
    )


class RetrieveInput(BaseModel):
    queries: list[RetrieveQuery] = Field(
        ...,
        min_length=1,
        description="List of retrieval queries. At least one query must be provided."
    )


class RetrievedChunk(BaseModel):
    id: str
    chunk_type: ChunkType
    content: str


class RetrieveTool(BaseTool):
    name: str = "retrieve"
    description: str = (
        "Search the knowledge base for relevant content. "
        "Accepts a single query or multiple queries (run in parallel). "
        "Use multiple queries to cover different aspects of a complex question."
    )
    args_schema: type[BaseModel] = RetrieveInput
    

    retrieval_service: RetrievalService
    state: AgentState
    settings: ChatSettings
    user_id: UUID
    course_id: UUID
    documents_ids: list[UUID] | None = None
    _retrieved_ids: set[str] = PrivateAttr(default_factory=set)
    _index: int = PrivateAttr(default=0)

    model_config = ConfigDict(arbitrary_types_allowed=True)


    async def _arun(self, queries: list[RetrieveQuery] ) -> str:
        tasks = [self._retrieve_one(q) for q in queries]
        outcomes = await asyncio.gather(*tasks, return_exceptions=True)

        all_results= []

        for i, outcome in enumerate(outcomes):
            if isinstance(outcome, BaseException):
                logger.warning("retrieve: query %d failed: %s", i, outcome)
                continue
            all_results.extend(outcome)

        results = [r.model_dump() for r in all_results]
        return json.dumps(results)


    async def _retrieve_one(self, inp: RetrieveQuery) -> list[RetrievedChunk]:
        current_chunks: list[RetrievedChunk] = []

        query_text = f"{inp.context_hint}: {inp.query}" if inp.context_hint else inp.query

        search_query = SearchQuery(
            query=query_text,
            top_k=self.settings.top_k,
            score_threshold=self.settings.score_threshold,
            rerank=self.settings.rerank,
        )

        response = await self.retrieval_service.retrieve(
            request=search_query,
            user_id=self.user_id,
            course_id=self.course_id,
            documents_ids=self.documents_ids,
            type=inp.chunk_type,
        )

        self._register_and_dedup(
            results=response.results,
            chunk_type=inp.chunk_type,
            current_chunks=current_chunks
        )

        return current_chunks


    def _register_and_dedup(
        self,
        results: list[SearchResult],
        chunk_type: ChunkType,
        current_chunks: list[RetrievedChunk]
    ) -> None:
        """
        Register new chunks from a single query's results into the shared cache.

        Iterates over search results, skipping any chunk whose UUID has already
        been seen across all queries this turn. For new chunks, assigns a
        short sequential ID (s1, s2, ...), stores the citation metadata in
        chunk_cache keyed by that ID, and appends a RetrievedChunk to
        current_chunks for inclusion in the tool's response to the agent.

        Args:
            results:        Raw search results returned by the retrieval service.
            chunk_type:     The chunk type filter used in the originating query,
                            carried through to the RetrievedChunk for the agent.
            current_chunks: Accumulator list mutated in place — new chunks are
                            appended here rather than returned.
        """
        for r in results:
            cid = str(r.chunk_id)

            if cid in self._retrieved_ids:
                continue

            self._retrieved_ids.add(cid)
            self._index += 1
            short_id = f"s{self._index}"

            self.state.chunk_cache[short_id] =  CitationMetaData(
                document_id = UUID(r.document_id),
                starting_page = r.starting_page,
                end_page = r.end_page
            )
            
            current_chunks.append( 
                RetrievedChunk(
                    id=short_id,
                    content=r.content,
                    chunk_type=chunk_type
                )
            )


    def _run(self, **kwargs):
        "Required by langchain"
        raise NotImplementedError("The agent is designed to be used async only")
