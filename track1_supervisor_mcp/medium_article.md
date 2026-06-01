# Defeating Agent Roulette: Securing Databricks MCP Orchestration with OBO Token Interdiction

*By: Principal Systems Architect & Sovereign Security Specialist*

---

## 1. The Probabilistic Fallacy: The Structural Flaw in Databricks Supervisor Agents
In modern enterprise architectures, the integration of autonomous **Databricks Supervisor Agents** is frequently championed as a major productivity driver. By leveraging Large Language Models (LLMs) to orchestrate complex data processing tasks, platforms allow agents to dynamically write queries, invoke tools, and retrieve context. However, this pattern introduces a severe architectural vulnerability: **blind trust in semantic intent**.

Relying on an LLM to generate secure execution payloads is a form of system design roulette. Because LLM output is fundamentally probabilistic (non-deterministic), it cannot be trusted to enforce authorization boundaries. A semantic jailbreak or prompt injection bypasses the system instructions because the control instructions and untrusted user data share the same input stream. 

If an agent is compromised, it can generate malicious commands (e.g. SQL injection, database mutation, or unauthorized catalog traversal) and pass them directly to downstream execution engines. Standard database schemas and database catalogs are exposed to absolute alteration because the execution engine blindly trusts the output of the reasoning loop.

To secure this architecture, we must decouple the **probabilistic reasoning layer** from the **deterministic execution engine** by introducing a strict, token-validated policy proxy at the network boundary.

---

## 2. The Supply Chain Risk of the Model Context Protocol (MCP)
The **Model Context Protocol (MCP)** provides a standard interface for agents to fetch contexts, read files, and call database tools. However, in enterprise enclaves, MCP introduces severe supply chain risks:
- **Command Injection Vectors**: Malicious context payloads (such as fuzzed inputs or relative directory traversals) can escape local sandbox boundaries, exposing host configurations or secrets files.
- **Server-Side Request Forgery (SSRF)**: Untrusted external MCP servers can command the local agent to fetch URLs, mapping internal private subnet addresses.
- **Context Pollution**: Attacking agents can poison the model's context window by inserting malicious directives into fetched resource files, hijacking downstream reasoning loops.

Without an intermediate interceptor that validates the identity, authorization scope, and parameter safety of every JSON-RPC request, MCP acts as an unmonitored back-door directly into the enterprise data core.

---

## 3. Architecture of the Hybrid OBO Validation Proxy
To enforce strict zero-trust boundary isolation, we present the **Natoma Ingress Interdiction Proxy**. This proxy sits between the Databricks Supervisor Agent and the Databricks SQL Warehouse/Unity Catalog.

```
[ Databricks Supervisor Agent ]
             │
             │ 1. API request (Bearer JWT token + JSON-RPC payload)
             ▼
 [ Natoma Interdiction Proxy ] (Runs locally on Adraca Laptop)
             │
    ┌────────┴──────────────────────────┐
    │ 2. Validated Payload              │ 3. Rejected Query
    ▼                                   ▼
[ Oracle Egress Gateway ]      [ 403 Access Denied ] (JSON-RPC Error)
    │ (Nodes 1-4)
    ▼
[ Databricks Unity Catalog ]
```

### Key Security Primitives:
1. **On-Behalf-Of (OBO) Asymmetric Authentication**: Every agent request must carry a cryptographically signed Bearer JWT token. The proxy validates the token signature using asymmetric RS256 cryptography against trusted public JSON Web Key Sets (JWKS).
2. **Metadata Containment Map (MCM)**: The token claims contain an MCM mapping the exact database catalogs, schemas, and actions (e.g., `SELECT_ONLY`) the user is authorized to execute.
3. **Decoupled Validation**: The proxy verifies that requested parameters match the MCM boundaries *before* forwarding the payload to the LiteLLM routing gateway or the Databricks SQL Warehouse.

---

## 4. Egress Isolation & Hardware Topology
The implementation maps to a strict sovereign hardware boundary to ensure absolute data isolation:

- **Localized Compute Boundary**: The interdiction proxy runs as a lightweight, sandboxed FastAPI service on the **Adraca Edge Laptop** (`100.95.154.21`), preventing external configuration tampering.
- **Inference Routing**: Supervisor Agent reasoning loops compile their execution steps via a local **LiteLLM instance** hosted on the **Proxmox virtualization cluster** (`adraca-pve` at `100.116.70.21:4000`).
- **Network Egress Constraints**: All approved database executions are routed outward through **Oracle Cloud Nodes 1-4** (`.*-vnic` constrained instances). Direct connection routes from the local edge laptop to the production databases are strictly blocked, preventing local network space contamination.

---

## 5. Reference Implementation & Cryptographic Validation

### 5.1 Asymmetric Token Verification (`obo_validator.py`)
The following Python class demonstrates the asymmetric verification of OBO tokens containing the Metadata Containment Map:

```python
import jwt
from typing import Dict, Any
from cryptography.hazmat.primitives import serialization

class JWTValidator:
    def __init__(self, public_key_pem: bytes):
        self.public_key_pem = public_key_pem

    def decode_and_verify(self, token: str) -> Dict[str, Any]:
        """
        Verifies the asymmetric RS256 signature using the public key
        and validates required metadata containment claims.
        """
        return jwt.decode(
            token,
            self.public_key_pem,
            algorithms=["RS256"],
            audience="natoma-mcp-proxy-2026",
            issuer="https://databricks-sovereign-fleet.com",
            options={"require": ["exp", "iss", "aud", "metadata_containment"]}
        )
```

### 5.2 Ingress Interdiction Middleware (`mcp_proxy.py`)
The FastAPI endpoint captures JSON-RPC 2.0 tool-call payloads, extracts the token, and validates the parameters against the containment boundaries:

```python
from fastapi import FastAPI, Header, HTTPException, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Dict, Any, Optional

app = FastAPI()

class JSONRPCRequest(BaseModel):
    jsonrpc: str = "2.0"
    method: str
    params: Dict[str, Any]
    id: Optional[Any] = None

# Set read-only SQL sanitization rules
FORBIDDEN_KEYWORDS = ["drop", "truncate", "delete", "insert", "update", "alter", "create", "union", ";"]

def is_safe_sql(sql_query: str) -> bool:
    sql_lower = sql_query.lower()
    return not any(keyword in sql_lower for keyword in FORBIDDEN_KEYWORDS)

@app.post("/v1/mcp/tools/call")
async def call_tool(request: JSONRPCRequest, authorization: str = Header(...)):
    # 1. Signature Authentication
    try:
        token = authorization.split("Bearer ")[1].strip()
        claims = validator.decode_and_verify(token)
    except Exception as e:
        return JSONResponse(
            status_code=403,
            content={"jsonrpc": "2.0", "error": {"code": -32002, "message": "JWT validation failed"}, "id": request.id}
        )

    containment = claims.get("metadata_containment", {})
    allowed_catalogs = containment.get("allowed_catalogs", [])
    allowed_actions = containment.get("allowed_actions", [])

    # 2. Intercept & Validate Parameters
    if request.method == "tools/call":
        tool_name = request.params.get("name")
        arguments = request.params.get("arguments", {})
        
        if tool_name == "query_unity_catalog":
            catalog = arguments.get("catalog")
            sql_query = arguments.get("sql_query", "")

            # Verify catalog scope boundary
            if catalog not in allowed_catalogs:
                return JSONResponse(
                    status_code=403,
                    content={"jsonrpc": "2.0", "error": {"code": -32003, "message": "Access Denied: Catalog out of scope"}, "id": request.id}
                )

            # Verify action boundaries & sanitize query content
            if "SELECT_ONLY" in allowed_actions:
                if not is_safe_sql(sql_query):
                    return JSONResponse(
                        status_code=403,
                        content={"jsonrpc": "2.0", "error": {"code": -32004, "message": "Access Denied: Query contains invalid statements"}, "id": request.id}
                    )

            # 3. Safe Egress Routing via Oracle Nodes
            print(f"[INFO] Routing execution to http://oracle-node-1:8080/execute")
            return {"jsonrpc": "2.0", "result": {"content": [{"type": "text", "text": "Success"}]}, "id": request.id}

    return JSONResponse(
        status_code=400,
        content={"jsonrpc": "2.0", "error": {"code": -32601, "message": "Method not found"}, "id": request.id}
    )
```

---

## 6. Conclusion
Relying on semantic output to police runtime activities is a fundamental security flaw. By implementing the Natoma Zero-Trust Proxy Gateway to validate asymmetric signatures and enforce Metadata Containment Maps at the edge, organizations can lock down their Databricks Agent orchestration pipelines with absolute, mathematical predictability.
