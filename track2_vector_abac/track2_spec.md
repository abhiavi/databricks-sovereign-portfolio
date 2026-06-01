# Sovereign System Specification: Dynamic ABAC Vector Injection Proxy

**Classification**: Sovereign Architecture Design Specification (VP-Ready)  
**Status**: Approved for Implementation  
**Target Path**: `/home/abhishek/ObsidianVault/03_Active_Projects/databricks_sovereign_portfolio/track2_vector_abac/track2_spec.md`

---

## 1. Executive Summary & Hardware Topology
This specification defines the security architecture, endpoint contracts, and compliance rules for the **Dynamic ABAC (Attribute-Based Access Control) Vector Injection Proxy**. Built for secure enclaves, the proxy intercepts semantic vector search requests and dynamically merges row-level security (RLS) policies at the query-generation layer. This prevents information leakage from vector databases (like Databricks Mosaic AI Vector Search) where raw vectors lack native tenant or row isolation.

```
┌────────────────────────────────────────────────────────────────────────┐
│                        ADRACA EDGE LAPTOP                              │
│  - Runs ABAC Vector Injection Proxy (FastAPI microservice)             │
│  - Reads local Mock Unity Catalog JSON permissions                     │
│  - Inject dynamic filters (metadata tags) into query payload           │
└───────────────────────────┬────────────────────────────────────────────┘
                            │
                            │ Queries Qdrant
                            ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        PROXMOX CLUSTER                                 │
│  - Runs Qdrant Vector Database (representing Databricks Mosaic search)  │
│  - Location: 100.116.70.21:6333                                       │
└────────────────────────────────────────────────────────────────────────┘
```

### Hardware Constraints:
1. **Local Compute boundary**: The ABAC Vector Injection Proxy runs natively as a localized service on the **Adraca Edge Laptop** (`100.95.154.21`), maintaining local control over client metadata.
2. **Vector Engine**: The proxy queries a local **Qdrant Vector Database instance** hosted on the **Proxmox virtualization cluster** (`100.116.70.21:6333`).
3. **Identity & Policy Registry**: User attributes and group classification tags are fetched locally from a mocked **Unity Catalog JSON metadata store** on the proxy host.

---

## 2. Security Core: Dynamic Vector Attribute-Based Access Control (ABAC)

### 2.1 The Vector Security Gap
Vector databases optimize for cosine distance, dot product, or Euclidean similarity metrics. Standard semantic queries return nearest neighbors based solely on vector distance, ignoring business permission boundaries. If a user queries *"Show me the latest audit logs,"* a vector engine without metadata filtering will return matching fragments across all tenant datasets, creating a critical row-level security (RLS) violation.

### 2.2 Ingress Interdiction & Filter Injection
To close this gap, the proxy interceptor executes the following query modification loop:
1. **Interception**: Captures incoming semantic search requests targeting `/v1/collections/{collection_name}/points/query`.
2. **Context Resolution**: Extracts the user's identity from the request headers and reads their access permissions from the mock **Unity Catalog JSON mapping**.
3. **Filter Generation**: Translates resolved user attributes (e.g. `allowed_departments = ["finance"]` and `clearance_level = "secret"`) into standard Qdrant query filter schemas.
4. **Dynamic Payload Injection**: Modifies the incoming request payload by injecting the compiled filters directly into Qdrant's `filter` parameters.
5. **Upstream Query Execution**: Forwards the secured query payload to the Qdrant instance. Only vectors matching the strict metadata attributes are evaluated for distance similarity.

---

## 3. Required Python Modules & Dependencies
The localized implementation on the Adraca Edge Laptop requires:
- **`fastapi`** / **`uvicorn`**: High-performance HTTP server routing.
- **`qdrant-client`**: SDK to interface with Qdrant collection APIs.
- **`pydantic`**: Parameter verification and schema model validation.
- **`httpx`**: Asynchronous HTTP client to proxy raw REST calls if necessary.

---

## 4. FastAPI Endpoints & Interface Specification

### 4.1 `/v1/search` [POST]
Receives user semantic search requests, fetches permissions, and performs filter injection before querying Qdrant.
- **Headers**:
  - `X-User-Identity: <user_id>` (representing client context)
- **Request Body**:
  ```json
  {
    "collection": "corporate_knowledge",
    "vector": [0.12, -0.43, 0.88],
    "limit": 5
  }
  ```
- **Response**: Standard filtered similarity outputs from Qdrant.

### 4.2 `/v1/admin/permissions` [GET/POST]
Reads or updates the local mock Unity Catalog permissions mapping.
- **Response**: The current JSON mapping of users to access tags.

---

## 5. Security Invariants & Policy Constraints

### Invariant 01: Mandatory Interdiction
> A semantic query MUST NOT be sent to Qdrant without a resolved filter block. If the proxy fails to look up the user's permissions, it MUST abort the query and return `403 Access Denied`.

### Invariant 02: RLS Metadata Isolation
> The proxy MUST enforce metadata containment. A query returned from Qdrant must be validated to confirm that every retrieved point possesses tags matching the user's clearance. Unfiltered results will trigger an immediate system panic.
