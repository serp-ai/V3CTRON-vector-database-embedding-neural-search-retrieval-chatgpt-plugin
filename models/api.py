from models.models import (
    Document,
    DocumentMetadataFilter,
    Query,
    QueryResult,
    ActiveCollection,
)
from pydantic import BaseModel
from typing import List, Optional


class UpsertRequest(BaseModel):
    collection_name: str
    documents: List[Document]


class UpsertResponse(BaseModel):
    ids: List[str]


class QueryRequest(BaseModel):
    collection_name: str
    queries: List[Query]


class QueryResponse(BaseModel):
    results: List[QueryResult]


class DeleteRequest(BaseModel):
    collection_name: Optional[str] = None
    ids: Optional[List[str]] = None
    filter: Optional[DocumentMetadataFilter] = None
    delete_all: Optional[bool] = False


class DeleteResponse(BaseModel):
    success: bool


class DeleteCollectionRequest(BaseModel):
    collection_name: str


class CreateCollectionRequest(BaseModel):
    collection_name: str
    embedding_method: str = "mpnet"
    overview: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = True


class UpdateCollectionRequest(BaseModel):
    collection_name: str
    new_collection_name: Optional[str] = None
    overview: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class UpdateCollectionResponse(BaseModel):
    collection_name: str
    overview: Optional[str] = None
    description: Optional[str] = None


class CreateCollectionResponse(BaseModel):
    success: bool


class GetActiveCollectionsResponse(BaseModel):
    collections: List[ActiveCollection]
