from abc import ABC, abstractmethod
from typing import Dict, List, Optional
import asyncio

from models.models import (
    Document,
    DocumentChunk,
    DocumentMetadataFilter,
    Query,
    QueryResult,
    QueryWithEmbedding,
)
from services.chunks import get_document_chunks
from services.openai import get_embeddings
from services.mpnet import get_mpnet_embeddings


class DataStore(ABC):
    async def upsert(
        self, documents: List[Document], chunk_token_size: Optional[int] = None, mode='openai', model=None, tokenizer=None, collection_name=None
    ) -> List[str]:
        """
        Takes in a list of documents and inserts them into the database.
        First deletes all the existing vectors with the document id (if necessary, depends on the vector db), then inserts the new ones.
        Return a list of document ids.
        """
        # Delete any existing vectors for documents with the input document ids
        await asyncio.gather(
            *[
                self.delete(
                    filter=DocumentMetadataFilter(
                        document_id=document.id,
                    ),
                    delete_all=False,
                )
                for document in documents
                if document.id
            ]
        )

        chunks = get_document_chunks(documents, chunk_token_size, mode, model, tokenizer)

        return await self._upsert(chunks, collection_name=collection_name, mode=mode)

    @abstractmethod
    async def _upsert(self, chunks: Dict[str, List[DocumentChunk]], collection_name=None, mode='mpnet') -> List[str]:
        """
        Takes in a list of list of document chunks and inserts them into the database.
        Return a list of document ids.
        """

        raise NotImplementedError

    async def query(self, queries: List[Query], mode='openai', model=None, tokenizer=None, collection_name=None) -> List[QueryResult]:
        """
        Takes in a list of queries and filters and returns a list of query results with matching document chunks and scores.
        """
        # get a list of of just the queries from the Query list
        query_texts = [query.query for query in queries]
        if mode == 'openai':
            query_embeddings = get_embeddings(query_texts)
        elif mode == 'mpnet':
            query_embeddings = get_mpnet_embeddings(query_texts, tokenizer, model)
        else:
            raise ValueError('Invalid mode')
        # hydrate the queries with embeddings
        queries_with_embeddings = [
            QueryWithEmbedding(**query.dict(), embedding=embedding)
            for query, embedding in zip(queries, query_embeddings)
        ]
        return await self._query(queries_with_embeddings, collection_name=collection_name, mode=mode)

    @abstractmethod
    async def _query(self, queries: List[QueryWithEmbedding], collection_name=None, mode='mpnet') -> List[QueryResult]:
        """
        Takes in a list of queries with embeddings and filters and returns a list of query results with matching document chunks and scores.
        """
        raise NotImplementedError

    @abstractmethod
    async def delete(
        self,
        ids: Optional[List[str]] = None,
        filter: Optional[DocumentMetadataFilter] = None,
        delete_all: Optional[bool] = None,
        collection_name: str = None,
    ) -> bool:
        """
        Removes vectors by ids, filter, or everything in the datastore.
        Multiple parameters can be used at once.
        Returns whether the operation was successful.
        """
        raise NotImplementedError
