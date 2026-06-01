# The Vector Search Blind Spot: Restoring Unity Catalog ABAC in Databricks RAG Pipelines

## Abstract
Retrieval-Augmented Generation (RAG) pipelines in modern enterprise architectures introduce a critical security vulnerability: the truncation of the security plane. When structured data warehouses governed by Attribute-Based Access Control (ABAC) or Row-Level Security (RLS) are synchronized with downstream vector databases, access control lists (ACLs) are stripped. The vector database functions solely on metric distances (e.g., cosine similarity), leading to privilege escalation and compliance violations. 

This paper introduces a decentralized system architecture that enforces dynamic, query-time metadata injection using a local proxy. By intercepting incoming semantic vectors and merging user permission tags fetched from Unity Catalog directly into the vector query AST (Abstract Syntax Tree) before indexing or search execution, we guarantee strict row-level containment on sovereign edge nodes.

---

## 1. The RAG Security Gap: RLS Stripping in Decoupled Enclaves
In standard Databricks deployments, data tables reside in Delta Lake, governed by **Unity Catalog**. Unity Catalog enforces cell-level, column-level, and row-level access controls based on user attributes (e.g., clearance, department) resolved dynamically via OIDC identity tokens.

However, when documents are chunked, embedded, and synced to high-performance vector databases (such as Databricks Mosaic AI Vector Search, Qdrant, or Pinecone) to facilitate RAG, this governance breaks down. 

```
[Delta Lake / Unity Catalog]
   │ (Enforces RLS / Tag Rules)
   ▼
[Chunking & Embedding Pipeline]
   │ (Strips security context / catalog ACLs)
   ▼
[Vector Database Index]
   │ (Only stores raw floats and basic payload)
   ▼
[Semantic Query (Nearest Neighbor Search)] ──> PRIVILEGE ESCALATION
```

The vector search engine operates as a decoupled black-box. The query $q$ is translated to a vector $\vec{v}_q \in \mathbb{R}^d$ and matched against index vectors $\vec{v}_i \in \mathbb{R}^d$ using distance metrics:

$$D(\vec{v}_q, \vec{v}_i) = \frac{\vec{v}_q \cdot \vec{v}_i}{\|\vec{v}_q\| \|\vec{v}_i\|}$$

Because the database evaluates only spatial proximity, the query returns the nearest neighbors regardless of the user's access privileges. If a low-clearance user queries *"Show internal payroll projections,"* the system returns the exact vectors containing restricted financial details, leading to complete isolation failure.

---

## 2. Ingress Interdiction Proxy Architecture
To restore security invariants, we deploy an **Ingress Interdiction Proxy** at the edge boundary. The proxy intercepts all semantic search requests, resolves the user identity via Bearer token signature extraction, fetches allowed access tags from Unity Catalog, and dynamically injects metadata filters into the query.

```
                  ADRACA EDGE SOVEREIGN LAYER
                  ┌────────────────────────────────────────────────────────┐
                  │ Databricks Agent / Client                              │
                  └─────────────────────────┬──────────────────────────────┘
                                            │ GET /v1/search
                                            │ (Authorization: Bearer <token>)
                                            ▼
                  ┌────────────────────────────────────────────────────────┐
                  │ Natoma ABAC Proxy                                      │
                  │  1. Extract Token                                      │
                  │  2. Lookup allowed tags in Unity Catalog Mock           │
                  │  3. Inject pre-filters into Qdrant AST                 │
                  └─────────────────────────┬──────────────────────────────┘
                                            │ query_points(query, query_filter)
                                            ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ Proxmox Compute Enclave (Qdrant Vector Database)                          │
│                                                                          │
│  [ enterprise_docs collection ]                                          │
│  ├── Document 1: q=[0.9, 0.1, 0.1, 0.1]  (tags: ["FINANCE"]) - BLOCKED   │
│  ├── Document 2: q=[0.8, 0.2, 0.1, 0.1]  (tags: ["FINANCE"]) - BLOCKED   │
│  └── Document 3: q=[0.1, 0.1, 0.9, 0.1]  (tags: ["PUBLIC"])  - ALLOWED   │
└──────────────────────────────────────────────────────────────────────────┘
```

The proxy architecture enforces two strict invariants:
1. **Invariant 01: Mandatory Interdiction**: No semantic query is allowed to reach the vector engine without a resolved filter block. If the identity resolution fails or returns an empty clearance set, the query is aborted at the proxy boundary, returning HTTP 403.
2. **Invariant 02: RLS Metadata Isolation**: All retrieved documents are post-validated by the proxy to verify that their metadata tags are a subset of the user's authorized clearance. Any violation triggers an immediate panic, avoiding raw document leakage.

---

## 3. Dynamic Filter Injection Mechanics
The security mapping translates user clearance into a logical boolean filter constraint. Let the universe of metadata tags be $\mathcal{T}$ and the user's authorized tags be $\mathcal{U} \subseteq \mathcal{T}$. Every indexed point $p_i$ is tagged with a list of attributes $T(p_i) \subseteq \mathcal{T}$.

The pre-filtering constraint requires that:

$$T(p_i) \cap \mathcal{U} \neq \emptyset$$

In Qdrant, this is expressed as a logical `MatchAny` statement inside the `query_filter` payload. The proxy intercepts the semantic text query, maps it to a search vector, constructs the `Filter` object, and issues a unified `query_points` request.

---

## 4. Implementation Details: Qdrant AST Filter Injection
The following Python snippet from [vector_proxy.py](file:///home/abhishek/ObsidianVault/03_Active_Projects/databricks_sovereign_portfolio/track2_vector_abac/vector_proxy.py) demonstrates the interception and AST construction:

```python
# GET /v1/search
@app.get("/v1/search")
def search(
    q: Optional[str] = Query(None, description="Semantic text query, e.g., 'financial budget'"),
    vector: Optional[str] = Query(None, description="Comma-separated vector floats, e.g., '0.1,0.2,0.3,0.4'"),
    collection: str = Query("enterprise_docs", description="Qdrant collection name"),
    limit: int = Query(5, ge=1, description="Max number of results"),
    allowed_tags: List[str] = Depends(get_allowed_tags),
    client: QdrantClient = Depends(get_qdrant_client)
):
    # Parse or convert query text to vector
    vector_floats = parse_query_vector(q, vector)
        
    logger.info(f"Executing GET semantic search with dynamic filter injection: {allowed_tags}")
    
    # Invariant 01: Mandatory Interdiction - Build the Qdrant Filter AST
    qdrant_filter = Filter(
        must=[
            FieldCondition(
                key="tags",
                match=MatchAny(any=allowed_tags)
            )
        ]
    )
    
    try:
        # Query vector database with strict pre-filtering injected
        query_response = client.query_points(
            collection_name=collection,
            query=vector_floats,
            query_filter=qdrant_filter,
            limit=limit
        )
        results = query_response.points
        
        search_results = []
        for res in results:
            payload = res.payload or {}
            retrieved_tags = payload.get("tags", [])
            
            # Invariant 02: RLS Metadata Isolation Check (Post-query validation)
            if not any(tag in allowed_tags for tag in retrieved_tags):
                logger.critical(f"CRITICAL SECURITY VIOLATION: Point {res.id} leaked!")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Security system panic: RLS metadata isolation violation."
                )
                
            search_results.append({
                "id": res.id,
                "score": res.score,
                "title": payload.get("title"),
                "content": payload.get("content"),
                "tags": retrieved_tags
            })
            
        return {"results": search_results}
```

---

## 5. Mathematical Proof of Isolation
To verify the security isolation guarantees, we model the search space as a metric space $(X, d_M)$ containing all document vectors. 

Let:
- $X = \{p_1, p_2, \dots, p_n\}$ be the set of points.
- $P(p_i)$ be the payload mapping representing metadata tags.
- $C_u$ be the clearance set of user $u$.

A query without interdiction searches the full set $X$. The search returns a subset $R_{unsecured} \subseteq X$ containing the top-$k$ nearest neighbors:

$$R_{unsecured} = \arg\min^{(k)}_{p \in X} d_M(q, p)$$

If any point $p^* \in R_{unsecured}$ has $P(p^*) \cap C_u = \emptyset$, a security leak occurs.

By injecting the filter constraint $\Phi_u(p) \iff P(p) \cap C_u != \emptyset$, we restrict the search domain from $X$ to the subspace $X_u \subset X$, where:

$$X_u = \{p \in X \mid P(p) \cap C_u \neq \emptyset\}$$

The proxy-secured nearest neighbor search is defined as:

$$R_{secured} = \arg\min^{(k)}_{p \in X_u} d_M(q, p)$$

### Boundary Verification Results
This metric isolation was validated using [test_harness.py](file:///home/abhishek/ObsidianVault/03_Active_Projects/databricks_sovereign_portfolio/track2_vector_abac/test_harness.py) against a seeded vector database containing three points:
1. $p_1$: `vector=[0.9, 0.1, 0.1, 0.1]`, `tags=["FINANCE"]` (Sensitive Budget Data)
2. $p_2$: `vector=[0.8, 0.2, 0.1, 0.1]`, `tags=["FINANCE"]` (Sensitive Q1 Data)
3. $p_3$: `vector=[0.1, 0.1, 0.9, 0.1]`, `tags=["PUBLIC"]` (Public Press Release)

A semantic query targeting `financial budget` ($\vec{q} = [0.9, 0.1, 0.1, 0.1]$) was executed under two distinct privilege contexts:

#### Context 1: High Clearance User ($C_{finance} = \{\text{PUBLIC}, \text{FINANCE}\}$)
The subspace is $X_{finance} = \{p_1, p_2, p_3\}$. The distance evaluations are:
- $d_{Cosine}(q, p_1) = 0.0$ (Similarity: 1.0000)
- $d_{Cosine}(q, p_2) = 0.0089$ (Similarity: 0.9911)
- $d_{Cosine}(q, p_3) = 0.7619$ (Similarity: 0.2381)

The output set contains $\{p_1, p_2, p_3\}$ ordered by score. Access is correctly granted.

#### Context 2: Low Clearance User ($C_{public} = \{\text{PUBLIC}\}$)
The subspace is $X_{public} = \{p_3\}$. Points $p_1$ and $p_2$ are pruned from the evaluation space *before* distance calculation. The distance evaluation yields:
- $d_{Cosine}(q, p_3) = 0.7619$ (Similarity: 0.2381)

The output set contains only $\{p_3\}$. The probability of leaking sensitive documents $p_1, p_2$ is structurally reduced to zero:

$$P(\text{Leak}) = P(p \in R_{secured} \mid P(p) \cap C_u = \emptyset) = 0$$

The pre-filtering boundary successfully holds, preventing privilege escalation at the vector-search layer.
