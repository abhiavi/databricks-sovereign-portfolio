# Sovereign System Specification: MCP Ingress Interdiction Proxy for Databricks Supervisor Agents

**Classification**: Sovereign Architecture Design Specification (VP-Ready)  
**Status**: Approved for Implementation  
**Target Path**: `/home/abhishek/ObsidianVault/03_Active_Projects/databricks_sovereign_portfolio/track1_supervisor_mcp/track1_spec.md`

---

## 1. Executive Summary & Hardware Topology
This specification defines the security boundary, endpoint interfaces, and execution invariants for the **Model Context Protocol (MCP) Ingress Interdiction Proxy** protecting Databricks Supervisor Agents. Designed to operate within a multi-node sovereign fleet, this proxy prevents unauthorized data access and enforces strict compliance boundaries before agents touch Databricks compute resources.

```
┌────────────────────────────────────────────────────────────────────────┐
│                        ADRACA EDGE LAPTOP                              │
│  - Runs MCP Ingress Interdiction Proxy (FastAPI microservice)          │
│  - Performs JWT signature verification (RS256)                         │
│  - Enforces Metadata Containment Map policies                          │
└───────────────────────────┬────────────────────────────────────────────┘
                            │
     Inference calls        │ Routes approved tool calls
     via LiteLLM            ▼
┌───────────────────────────┐          ┌─────────────────────────────────┐
│     PROXMOX CLUSTER       │          │     ORACLE CLOUD NODES 1-4      │
│  - Host: 100.116.70.21    │          │  - High-Compute Egress gateway  │
│  - Service: LiteLLM:4000  │          │  - Restricted execution pods    │
└───────────────────────────┘          └─────────────────────────────────┘
```

### Hardware Constraints:
1. **Local Compute boundary**: The Ingress Proxy runs natively as a localized service on the **Adraca Edge Laptop** (`100.95.154.21`), keeping the parsing logic close to local administrative control.
2. **Inference Routing**: Databricks Supervisor Agents send LLM inference queries to a local **LiteLLM instance** hosted on the **Proxmox cluster** (`adraca-pve` at `100.116.70.21:4000`).
3. **Network Egress Gateway**: Approved external MCP tool calls (e.g. hitting Unity Catalog APIs or Databricks SQL warehouses) must be routed outward through **Oracle Cloud Nodes 1-4** (`.*-vnic` instances).
4. **Security Isolation**: High-priority compute workloads must remain inside the sandboxed Oracle environments, bypassing the edge laptop's local filesystem.

---

## 2. Security Core: Asymmetric JWT Verification & Containment Maps

### 2.1 On-Behalf-Of (OBO) Token Authentication
To mimic the security structure of Databricks Unity Catalog, the proxy enforces asymmetric signature validation on incoming OBO tokens:
- **Algorithm**: RS256 (RSA Signature with SHA-256).
- **Public Key Retrieval**: The proxy fetches or hosts a JSON Web Key Set (JWKS) to verify signatures against trusted Databricks IDP issuers.
- **Claims Verification**:
  - `iss` (Issuer): Must match the configured Databricks workspace domain.
  - `aud` (Auditor): Must match the MCP proxy identity client ID.
  - `obo_user` (Subject User): Must be resolved and mapped to specific data access roles.

### 2.2 Metadata Containment Map (MCM)
Every authorized token maps the Supervisor Agent to a strict **Metadata Containment Map (MCM)** payload. The proxy enforces the following policies:
- **Catalog Scope**: The agent is restricted to specific catalogs (e.g., `prod_finance`, `dev_sandbox`). Attempts to query default schemas (`system`, `information_schema`) or cross-tenant databases are blocked.
- **Table Containment**: The proxy maintains a list of blocked table signatures.
- **Allowed Actions**: Restricted list of allowed commands: `SELECT_ONLY`, `DESCRIBE_ONLY`. Mutation operations (`CREATE`, `DROP`, `ALTER`) are rejected.

---

## 3. Required Python Modules & Dependencies
The localized implementation on the Adraca Edge Laptop requires the following Python package dependencies:
- **`fastapi`** / **`uvicorn`**: Ingress API server routing.
- **`pydantic`**: Data serialization and strict JSON-RPC 2.0 schema validation.
- **`PyJWT[crypto]`**: Cryptographic validation of RS256 JSON Web Tokens.
- **`httpx`**: Asynchronous HTTP client to route queries to the Proxmox LiteLLM gateway (`100.116.70.21:4000`) and handle egress through Oracle nodes.
- **`python-dotenv`**: Environment parameter management (JWKS URLs, workspace domains, secret targets).

---

## 4. FastAPI Endpoints & Interface Specification

### 4.1 `/v1/jwks` [GET]
Exposes the local proxy JSON Web Key Set containing the public keys used for mock credential handshake tests.
- **Response**: Standard JWKS structure.

### 4.2 `/v1/mcp/tools/list` [POST]
Returns a list of approved tools the Databricks Supervisor Agent is authorized to invoke, constrained by the permissions resolved from the OBO token.
- **Headers**: `Authorization: Bearer <JWT_OBO_Token>`
- **Request Body**: Empty JSON-RPC object.
- **Response**: JSON-RPC list containing allowed tool descriptions.

### 4.3 `/v1/mcp/tools/call` [POST]
Executes the target tool call. Performs inline parsing of the SQL parameters or paths to prevent SQL injection and catalog traversals.
- **Headers**: `Authorization: Bearer <JWT_OBO_Token>`
- **Request Body**:
  ```json
  {
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "query_unity_catalog",
      "arguments": {
        "catalog": "prod_finance",
        "sql_query": "SELECT * FROM sales_summary LIMIT 10"
      }
    },
    "id": 1
  }
  ```
- **Validation Flow**:
  1. Parse JWT bearer token. Verify signatures and expiration via local JWKS.
  2. Resolve Metadata Containment Map permissions.
  3. Validate that `catalog` matches the authorized scope.
  4. Parse `sql_query` to block mutation statements (`drop`, `delete`, `insert`, `alter`) and ensure query targets conform to authorized schemas.
  5. Upon success, issue the query through the outbound Oracle Gateway.

---

## 5. Security Invariants & Policy Constraints

### Invariant 01: Token Validity requirement
> Any request lacking a valid, signature-verified OBO token MUST immediately result in a `401 Unauthorized` response. The proxy will not forward the request payload to LiteLLM or Snowflake.

### Invariant 02: Explicit Scope Isolation
> If an agent attempts to target a database catalog not explicitly declared in its Metadata Containment Map (MCM), the proxy MUST immediately return an `Access Denied (-32003)` JSON-RPC error.

### Invariant 03: Egress Routing Constraint
> The proxy MUST configure its HTTP client to route all remote SQL executions and API egress calls through the IPs of Oracle Nodes 1-4 (`100.70.197.5` / workspace equivalents). Egress calls routing directly from the laptop network namespace are forbidden.
