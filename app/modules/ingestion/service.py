from __future__ import annotations
from typing import  TYPE_CHECKING
from uuid import UUID
import logging
from pathlib import Path


from modules.ingestion.parser import PdfParser, DocxParser, PptxParser
from shared.enums import FileType

from db.relational.schemas import  DocumentUpdate
from db.relational.constants import DocumentStatus
from db.vector.schemas import ChunkMetaData
import time


if TYPE_CHECKING:
    from db.relational.repositories.document_repository import SyncDocumentRepository
    from db.relational.repositories.chunk_repository import SyncChunkRepository

    from shared.embedder import Embedder

    from db.vector.base import SyncVectorDBRepository

    from shared.llm.client import LLMClient


logger = logging.getLogger(__name__)

class IngestionService:
    def __init__(
        self,
        document_repo: SyncDocumentRepository,
        chunk_repo: SyncChunkRepository,
        embedder: Embedder,
        vector_repo: SyncVectorDBRepository,
        llm_client: LLMClient
        
    ):
        self.document_repo = document_repo
        self.chunk_repo = chunk_repo
        self.embedder = embedder
        self.vector_repo = vector_repo
        self.llm_client = llm_client

  
    def process_file(
            self,
            user_id: UUID,
            course_id: UUID,
            document_id: UUID,
        ) :

        document = self.document_repo.get_by_id(document_id=document_id)

        data = DocumentUpdate(
            status=DocumentStatus.EXTRACTING
        )

        self.document_repo.update(
            document=document,
            data=data
        )

        if document.type == FileType.PPT or document.type == FileType.PPTX :
            parser = PptxParser(llm_client=self.llm_client)
        elif document.type == FileType.DOC or document.type == FileType.DOCX :
            parser = DocxParser(llm_client=self.llm_client)
        else :
            parser = PdfParser(llm_client=self.llm_client)
        
        
        chunks = parser.load(file_path = Path(document.file_path))

        chunks = self.chunk_repo.bulk_add(
            data=chunks,
            document_id=document.id
        )
 
        chunks_count = len(chunks)

        data = DocumentUpdate(
            status=DocumentStatus.CHUNKED,
            chunks_count=chunks_count,
        )

        self.document_repo.update(
            document=document,
            data=data
        )

        chunks_ids: list[UUID] = [c.id for c in chunks]
        chunks_content: list[str] = [c.content for c in chunks]
        chunks_metadatas = [ ChunkMetaData(
            user_id=user_id,
            course_id=course_id,
            document_id=c.document_id,
            content=c.content,
            type=c.type,
            index=c.index,
            starting_page=c.starting_page, # type: ignore
            end_page=c.end_page, # type: ignore
        ) 
        for c in chunks]

        
        return  chunks_ids, chunks_content, chunks_metadatas


    def index_file(
            self,
            ids: list[UUID],
            contents: list[str],
            metadatas: list[ChunkMetaData],
    ) -> int:

        if len(ids) != len(contents) or len(ids) != len(metadatas):
            raise ValueError("Length of ids, contents, and metadatas must be the same received: ids=%s, contents=%s, metadatas=%s", len(ids), len(contents), len(metadatas))
        
        vectors = []

        for i in range(0, len(contents), 50):
            chunks_partial = contents[i:i + 50]
            vectors.extend(self.embedder.embed(chunks_partial)) 
            time.sleep(60) # moaz: to avoid rate limit, look for better approach
            

        self.vector_repo.upsert(ids=ids, vectors=vectors, metadatas=metadatas)

        document = self.document_repo.get_by_id(document_id=metadatas[0].document_id)

        data = DocumentUpdate(
            status=DocumentStatus.INDEXED
        )

        self.document_repo.update(
            document=document,
            data=data
        )

        return len(ids)
