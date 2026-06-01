import os
import httpx
from fastapi import FastAPI, Request, Header, HTTPException, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from obo_validator import JWTValidator

app = FastAPI(title="Natoma Databricks Ingress Interdiction Proxy", version="v1.0.0")

# Instantiate global validator on startup
validator = JWTValidator()

class JSONRPCRequest(BaseModel):
    jsonrpc: str = "2.0"
    method: str
    params: Dict[str, Any] = Field(default_factory=dict)
    id: Optional[Any] = None

# Hardcoded metadata containment rules for sanity checks
HARDCODED_CONTAINMENT_MAP = {
    "forbidden_sql_keywords": ["drop", "truncate", "delete", "insert", "update", "alter", "create", "union", ";"]
}

# Standardized JSON-RPC exception handler for HTTPExceptions
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if isinstance(exc.detail, dict) and "jsonrpc" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "jsonrpc": "2.0",
            "error": {
                "code": -32000,
                "message": str(exc.detail)
            },
            "id": None
        }
    )

def get_auth_token(authorization: Optional[str] = Header(None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail={
                "jsonrpc": "2.0",
                "error": {
                    "code": -32001,
                    "message": "Unauthorized: Missing Bearer Token"
                },
                "id": None
            }
        )
    return authorization.split("Bearer ")[1].strip()

def is_safe_sql(sql_query: str) -> bool:
    if not sql_query:
        return True
    sql_lower = sql_query.lower()
    return not any(keyword in sql_lower for keyword in HARDCODED_CONTAINMENT_MAP["forbidden_sql_keywords"])

@app.get("/v1/jwks")
def get_jwks():
    """Exposes public JWKS for Unity Catalog authentication integration."""
    return validator.get_jwks()

@app.post("/v1/mcp/tools/list")
async def list_tools(request: JSONRPCRequest, token: str = Depends(get_auth_token)):
    try:
        claims = validator.decode_and_verify(token)
    except Exception as e:
        return JSONResponse(
            status_code=403,
            content={
                "jsonrpc": "2.0",
                "error": {
                    "code": -32002,
                    "message": f"Unauthorized: JWT validation failed: {str(e)}"
                },
                "id": request.id
            }
        )
    
    # Return tools allowed under the client's token containment map
    allowed_catalogs = claims.get("metadata_containment", {}).get("allowed_catalogs", [])
    
    return {
        "jsonrpc": "2.0",
        "result": {
            "tools": [
                {
                    "name": "query_unity_catalog",
                    "description": "Execute a SQL query inside Databricks Unity Catalog",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "catalog": {"type": "string", "enum": allowed_catalogs},
                            "sql_query": {"type": "string"}
                        },
                        "required": ["catalog", "sql_query"]
                    }
                }
            ]
        },
        "id": request.id
    }

@app.post("/v1/mcp/tools/call")
async def call_tool(request: JSONRPCRequest, token: str = Depends(get_auth_token)):
    # 1. Authenticate Token
    try:
        claims = validator.decode_and_verify(token)
    except Exception as e:
        return JSONResponse(
            status_code=403,
            content={
                "jsonrpc": "2.0",
                "error": {
                    "code": -32002,
                    "message": f"Unauthorized: JWT validation failed: {str(e)}"
                },
                "id": request.id
            }
        )

    # 2. Extract containment maps from JWT claims
    containment = claims.get("metadata_containment", {})
    allowed_catalogs = containment.get("allowed_catalogs", [])
    allowed_actions = containment.get("allowed_actions", [])

    # 3. Intercept & validate parameters for "query_unity_catalog" tool
    if request.method == "tools/call":
        tool_name = request.params.get("name")
        arguments = request.params.get("arguments", {})
        
        if tool_name == "query_unity_catalog":
            catalog = arguments.get("catalog")
            sql_query = arguments.get("sql_query", "")

            # A. Check catalog boundary (prevent traversal)
            if catalog not in allowed_catalogs:
                return JSONResponse(
                    status_code=403,
                    content={
                        "jsonrpc": "2.0",
                        "error": {
                            "code": -32003,
                            "message": f"Access Denied: Catalog '{catalog}' is outside of authorized Metadata Containment Map scope."
                        },
                        "id": request.id
                    }
                )

            # B. Check Action validation (e.g. read-only checks)
            if "SELECT_ONLY" in allowed_actions:
                if not is_safe_sql(sql_query):
                    return JSONResponse(
                        status_code=403,
                        content={
                            "jsonrpc": "2.0",
                            "error": {
                                "code": -32004,
                                "message": "Access Denied: Write/Mutation statements or SQL injection indicators detected in read-only scope."
                            },
                            "id": request.id
                        }
                    )

            # 4. Mock routing representing the Oracle Egress boundary
            print(f"[INFO] Routing query to Oracle Node 1 egress gateway: {sql_query}")
            
            if "TIMEOUT_TEST" in sql_query:
                raise HTTPException(
                    status_code=502,
                    detail={
                        "jsonrpc": "2.0",
                        "error": {
                            "code": -32099,
                            "message": "Bad Gateway: Network timeout communicating with Oracle Egress Boundary."
                        },
                        "id": request.id
                    }
                )
            
            return {
                "jsonrpc": "2.0",
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Success: Query executed via Oracle Nodes egress boundary inside catalog '{catalog}'."
                        }
                    ]
                },
                "id": request.id
            }

    return JSONResponse(
        status_code=400,
        content={
            "jsonrpc": "2.0",
            "error": {
                "code": -32601,
                "message": "Method not found or invalid tool action"
            },
            "id": request.id
        }
    )
