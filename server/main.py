import os
from typing import Optional
import uvicorn
import uuid
from fastapi import FastAPI, File, Form, HTTPException, Depends, Body, UploadFile, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles

from datastore.factory import get_datastore
from services.file import get_document_from_file

from fastapi.middleware.cors import CORSMiddleware

from models.models import DocumentMetadata, Source

from transformers import AutoTokenizer, AutoModel

from db import *
from models.api import *


bearer_scheme = HTTPBearer(auto_error=False)


def validate_api_key(credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer(auto_error=False)), db = Depends(get_db)):
    api_key = credentials.credentials
    if credentials.scheme != "Bearer" or not authenticate_user(api_key, db=db):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing API key")
    return api_key


app = FastAPI()
app.mount("/.well-known", StaticFiles(directory=".well-known"), name="static")

# Create a sub-application, in order to access just the query endpoint in an OpenAPI schema, found at http://0.0.0.0:8000/sub/openapi.json when the app is running locally
sub_app = FastAPI(
    title="SERP AI Retrieval Plugin",
    description="A retrieval API for querying and filtering documents based on natural language queries and metadata",
    version="1.0.0",
    servers=[{"url": "https://v3ctron.serp.ai"}]
)
app.mount("/sub", sub_app)


@app.post(
    "/create-collection",
    response_model=CreateCollectionResponse,
)
async def create_collection(
    api_key: str = Depends(validate_api_key),
    db = Depends(get_db),
    request: CreateCollectionRequest = Body(...),
):
    try:
        assert request.embedding_method in ["mpnet", "openai"], "Invalid embedding method"
        _uuid = uuid.uuid4()
        collection_name = request.collection_name + "_" + str(_uuid)
        collection_name = collection_name.replace(" ", "_").replace("-", "_")
        response = await datastore.create_collection(collection_name, request.embedding_method)
        if response == True:
            response = await add_collection_to_db(api_key, request.collection_name, collection_name, request.embedding_method, request.overview, request.description, request.is_active, db=db)
        return CreateCollectionResponse(success=response)
    except Exception as e:
        print("Error:", e)
        raise HTTPException(status_code=500, detail="Internal Service Error")


@app.post(
    "/update-collection",
    response_model=UpdateCollectionResponse,
)
async def update_collection(
    api_key: str = Depends(validate_api_key),
    db = Depends(get_db),
    request: UpdateCollectionRequest = Body(...),
):
    try:
        response = await update_collection_in_db(api_key, request.collection_name, request.new_collection_name, request.overview, request.description, request.is_active, db=db)
        return UpdateCollectionResponse(success=response)
    except Exception as e:
        print("Error:", e)
        raise HTTPException(status_code=500, detail="Internal Service Error")
    

@app.get(
    "/get-active-collections",
    response_model=GetActiveCollectionsResponse,
)
async def get_active_collections(
    api_key: str = Depends(validate_api_key),
    db = Depends(get_db),
):
    try:
        collections = await get_collections_from_db(api_key, db=db)
        for collection in collections:
            collection['collection_name'] = collection.pop('name')
        return GetActiveCollectionsResponse(collections=collections)
    except Exception as e:
        print("Error:", e)
        raise HTTPException(status_code=500, detail="Internal Service Error")
    
@sub_app.get(
    "/get-active-collections",
    response_model=GetActiveCollectionsResponse,
    # NOTE: We are describing the shape of the API endpoint input due to a current limitation in parsing arrays of objects from OpenAPI schemas. This will not be necessary in the future.
    description="Returns a list of active collections and overviews of what they are used for and/or what they contain.",
)
async def get_active_collections(
    api_key: str = Depends(validate_api_key),
    db = Depends(get_db),
):
    try:
        collections = await get_collections_from_db(api_key, db=db)
        return GetActiveCollectionsResponse(collections=collections)
    except Exception as e:
        print("Error:", e)
        raise HTTPException(status_code=500, detail="Internal Service Error")


@app.post(
    "/upsert-file",
    response_model=UpsertResponse,
)
async def upsert_file(
    api_key: str = Depends(validate_api_key),
    db = Depends(get_db),
    file: UploadFile = File(...),
    metadata: Optional[str] = Form(None),
    collection_name: str = Form(None),
):
    try:
        metadata_obj = (
            DocumentMetadata.parse_raw(metadata)
            if metadata
            else DocumentMetadata(source=Source.file)
        )
    except:
        metadata_obj = DocumentMetadata(source=Source.file)

    document = await get_document_from_file(file, metadata_obj)

    try:
        collection = await get_collection_from_db(api_key, collection_name, db=db)
    except Exception as e:
        print("Error:", e)
        raise HTTPException(status_code=500, detail="Internal Service Error")
    if collection is None:
        raise HTTPException(status_code=500, detail="Invalid collection name")
    try:
        collection_name, mode = collection
        ids = await datastore.upsert([document], mode=mode, model=model, tokenizer=tokenizer, collection_name=collection_name)
        return UpsertResponse(ids=ids)
    except Exception as e:
        print("Error:", e)
        raise HTTPException(status_code=500, detail=f"str({e})")


@app.post(
    "/upsert",
    response_model=UpsertResponse,
)
async def upsert_main(
    api_key: str = Depends(validate_api_key),
    db = Depends(get_db),
    request: UpsertRequest = Body(...),
):
    try:
        collection = await get_collection_from_db(api_key, request.collection_name, db=db)
    except Exception as e:
        print("Error:", e)
        raise HTTPException(status_code=500, detail="Internal Service Error")
    if collection is None:
        raise HTTPException(status_code=500, detail="Invalid collection name")
    try:
        collection_name, mode = collection
        ids = await datastore.upsert(request.documents, mode=mode, model=model, tokenizer=tokenizer, collection_name=collection_name)
        return UpsertResponse(ids=ids)
    except Exception as e:
        print("Error:", e)
        raise HTTPException(status_code=500, detail="Internal Service Error")
    
@sub_app.post(
    "/upsert",
    response_model=UpsertResponse,
    # NOTE: We are describing the shape of the API endpoint input due to a current limitation in parsing arrays of objects from OpenAPI schemas. This will not be necessary in the future.
    description="Save chat information. Accepts a collection name and an array of documents with text (potential questions + conversation text), metadata (source 'chat' and timestamp, no ID as this will be generated). Confirm with the user before saving, ask for more details/context.",
)
async def upsert(
    api_key: str = Depends(validate_api_key),
    db = Depends(get_db),
    request: UpsertRequest = Body(...),
):
    try:
        collection = await get_collection_from_db(api_key, request.collection_name, db=db)
    except Exception as e:
        print("Error:", e)
        raise HTTPException(status_code=500, detail="Internal Service Error")
    if collection is None:
        raise HTTPException(status_code=500, detail="Invalid collection name")
    try:
        collection_name, mode = collection
        ids = await datastore.upsert(request.documents, mode=mode, model=model, tokenizer=tokenizer, collection_name=collection_name)
        return UpsertResponse(ids=ids)
    except Exception as e:
        print("Error:", e)
        raise HTTPException(status_code=500, detail="Internal Service Error")


@app.post(
    "/query",
    response_model=QueryResponse,
)
async def query_main(
    api_key: str = Depends(validate_api_key),
    db = Depends(get_db),
    request: QueryRequest = Body(...),
):
    try:
        collection = await get_collection_from_db(api_key, request.collection_name, db=db)
    except Exception as e:
        print("Error:", e)
        raise HTTPException(status_code=500, detail="Internal Service Error")
    if collection is None:
        raise HTTPException(status_code=500, detail="Invalid collection name")
    try:
        collection_name, mode = collection
            
        results = await datastore.query(
            request.queries,
            mode=mode,
            model=model,
            tokenizer=tokenizer,
            collection_name=collection_name,
        )
        return QueryResponse(results=results)
    except Exception as e:
        print("Error:", e)
        raise HTTPException(status_code=500, detail="Internal Service Error")


@sub_app.post(
    "/query",
    response_model=QueryResponse,
    # NOTE: We are describing the shape of the API endpoint input due to a current limitation in parsing arrays of objects from OpenAPI schemas. This will not be necessary in the future.
    description="Accepts a collection name and an objects array with each item having a search query and an optional filter. Break down complex queries into sub-queries. Refine results by criteria, e.g. time / source, don't do this often. Split queries if ResponseTooLargeError occurs.",
)
async def query(
    api_key: str = Depends(validate_api_key),
    db = Depends(get_db),
    request: QueryRequest = Body(...),
):
    try:
        collection = await get_collection_from_db(api_key, request.collection_name, db=db)
    except Exception as e:
        print("Error:", e)
        raise HTTPException(status_code=500, detail="Internal Service Error")
    if collection is None:
        raise HTTPException(status_code=500, detail="Invalid collection name")
    try:
        collection_name, mode = collection
            
        results = await datastore.query(
            request.queries,
            mode=mode,
            model=model,
            tokenizer=tokenizer,
            collection_name=collection_name,
        )
        return QueryResponse(results=results)
    except Exception as e:
        print("Error:", e)
        raise HTTPException(status_code=500, detail="Internal Service Error")


@app.delete(
    "/delete",
    response_model=DeleteResponse,
)
async def delete(
    api_key: str = Depends(validate_api_key),
    db = Depends(get_db),
    request: DeleteRequest = Body(...),
):
    if not (request.ids or request.filter or request.delete_all):
        raise HTTPException(
            status_code=400,
            detail="One of ids, filter, or delete_all is required",
        )
    try:
        collection_name, mode = await get_collection_from_db(api_key, request.collection_name, db=db)
        success = await datastore.delete(
            ids=request.ids,
            filter=request.filter,
            delete_all=request.delete_all,
            collection_name=collection_name,
        )
        return DeleteResponse(success=success)
    except Exception as e:
        print("Error:", e)
        raise HTTPException(status_code=500, detail="Internal Service Error")
    

@sub_app.delete_collection(
    "/delete-collection",
    response_model=DeleteResponse,
    description="Delete a collection and all its data. This is irreversible.",
)
async def delete_collection(
    api_key: str = Depends(validate_api_key),
    db = Depends(get_db),
    request: DeleteCollectionRequest = Body(...),
):
    try:
        success = await datastore.delete_collection(request.collection_name)
        if success:
            success = await delete_collection_from_db(api_key, request.collection_name, db=db)
        return DeleteResponse(success=success)
    except Exception as e:
        print("Error:", e)
        raise HTTPException(status_code=500, detail="Internal Service Error")


@app.on_event("startup")
async def startup():
    global datastore
    global model
    global tokenizer
    datastore = await get_datastore()
    tokenizer = AutoTokenizer.from_pretrained('sentence-transformers/all-mpnet-base-v2')
    model = AutoModel.from_pretrained('sentence-transformers/all-mpnet-base-v2')


def start():
    uvicorn.run("server.main:app", host="0.0.0.0", port=8000, reload=True)
