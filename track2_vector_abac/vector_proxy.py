import os
import json
import logging
from typing import List, Optional
from fastapi import FastAPI, Header, HTTPException, Query, Depends, status
from pydantic import BaseModel
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchAny

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("vector_proxy")

app = FastAPI(title="Dynamic ABAC Vector Injection Proxy")

# Path to mock Unity Catalog permissions
UNITY_MOCK_PATH = "unity_mock.json"

# Dependency to get Qdrant Client
def get_qdrant_client() -> QdrantClient:
    # Connects to the local persistent directory created by setup_qdrant.py
    return QdrantClient(path="./qdrant_data")

# Helper to load permissions
def load_permissions() -> dict:
    if not os.path.exists(UNITY_MOCK_PATH):
        logger.error(f"Permissions file '{UNITY_MOCK_PATH}' not found.")
        return {}
    try:
        with open(UNITY_MOCK_PATH, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error reading permissions file: {e}")
        return {}

# Extract and validate token, returning the list of allowed tags
def get_allowed_tags(authorization: Optional[str] = Header(None)) -> List[str]:
    if not authorization:
        logger.warning("Missing Authorization header.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header."
        )
    
    if not authorization.startswith("Bearer "):
        logger.warning("Invalid Authorization header format. Must be Bearer <token>.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header format. Must be Bearer <token>."
        )
    
    token = authorization.split(" ")[1].strip()
    permissions = load_permissions()
    
    if token not in permissions:
        logger.warning(f"Unauthorized or invalid token: {token}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access Denied: Invalid or unauthorized token."
        )
        
    allowed_tags = permissions[token]
    logger.info(f"Token '{token}' authorized with allowed tags: {allowed_tags}")
    return allowed_tags

# GET /v1/search
@app.get("/v1/search")
def search(
    vector: str = Query(..., description="Comma-separated vector floats, e.g., '0.1,0.2,0.3,0.4'"),
    collection: str = Query("enterprise_docs", description="Qdrant collection name"),
    limit: int = Query(5, ge=1, description="Max number of results"),
    allowed_tags: List[str] = Depends(get_allowed_tags),
    client: QdrantClient = Depends(get_qdrant_client)
):
    try:
        # Parse vector from query parameter
        vector_floats = [float(x.strip()) for x in vector.split(",")]
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid vector format. Must be comma-separated floats, e.g., '0.1,0.2,0.3,0.4'."
        )
        
    logger.info(f"Executing GET semantic search in collection '{collection}' with dynamic filter injection: {allowed_tags}")
    
    # Invariant 01: Mandatory Interdiction
    qdrant_filter = Filter(
        must=[
            FieldCondition(
                key="tags",
                match=MatchAny(any=allowed_tags)
            )
        ]
    )
    
    try:
        results = client.search(
            collection_name=collection,
            query_vector=vector_floats,
            query_filter=qdrant_filter,
            limit=limit
        )
        
        # Format output and enforce security invariants
        search_results = []
        for res in results:
            payload = res.payload or {}
            retrieved_tags = payload.get("tags", [])
            
            # Invariant 02: RLS Metadata Isolation Check (Post-query validation)
            if not any(tag in allowed_tags for tag in retrieved_tags):
                logger.critical(
                    f"CRITICAL SECURITY VIOLATION: Retrieved point {res.id} "
                    f"with tags {retrieved_tags} but user clearance is {allowed_tags}!"
                )
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Security system panic: Row-Level Security metadata isolation violation detected."
                )
                
            search_results.append({
                "id": res.id,
                "score": res.score,
                "title": payload.get("title"),
                "content": payload.get("content"),
                "tags": retrieved_tags
            })
            
        logger.info(f"Search query returned {len(search_results)} points successfully.")
        return {"results": search_results}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error querying Qdrant: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Error connecting to vector database: {str(e)}"
        )

# POST /v1/search
class SearchRequest(BaseModel):
    collection: str = "enterprise_docs"
    vector: List[float]
    limit: int = 5

@app.post("/v1/search")
def search_post(
    request: SearchRequest,
    allowed_tags: List[str] = Depends(get_allowed_tags),
    client: QdrantClient = Depends(get_qdrant_client)
):
    logger.info(f"Executing POST semantic search in collection '{request.collection}' with dynamic filter injection: {allowed_tags}")
    
    # Invariant 01: Mandatory Interdiction
    qdrant_filter = Filter(
        must=[
            FieldCondition(
                key="tags",
                match=MatchAny(any=allowed_tags)
            )
        ]
    )
    
    try:
        results = client.search(
            collection_name=request.collection,
            query_vector=request.vector,
            query_filter=qdrant_filter,
            limit=request.limit
        )
        
        search_results = []
        for res in results:
            payload = res.payload or {}
            retrieved_tags = payload.get("tags", [])
            
            # Invariant 02 validation
            if not any(tag in allowed_tags for tag in retrieved_tags):
                logger.critical(
                    f"CRITICAL SECURITY VIOLATION: Retrieved point {res.id} "
                    f"with tags {retrieved_tags} but user clearance is {allowed_tags}!"
                )
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Security system panic: Row-Level Security metadata isolation violation detected."
                )
                
            search_results.append({
                "id": res.id,
                "score": res.score,
                "title": payload.get("title"),
                "content": payload.get("content"),
                "tags": retrieved_tags
            })
            
        logger.info(f"Search query returned {len(search_results)} points successfully.")
        return {"results": search_results}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error querying Qdrant: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Error connecting to vector database: {str(e)}"
        )

# Admin Endpoints for permissions
@app.get("/v1/admin/permissions")
def get_permissions():
    return load_permissions()

@app.post("/v1/admin/permissions")
def update_permissions(new_permissions: dict):
    try:
        with open(UNITY_MOCK_PATH, "w") as f:
            json.dump(new_permissions, f, indent=2)
        logger.info("Permissions updated successfully.")
        return {"status": "success", "permissions": new_permissions}
    except Exception as e:
        logger.error(f"Error updating permissions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not update permissions: {str(e)}"
        )
