graph LR
    subgraph Sovereign Edge Boundary
        B[Natoma Ingress Interdiction Proxy]
        C{Asymmetric OBO Token Validation<br>& Metadata Containment Map}
    end

    A[LLM Agent / MCP Client] -->|1. Malicious Tool Call + Token| B
    B -->|2. Intercept & Decode RS256| C
    C -->|3a. Verified: Safe Route| D[(Enterprise Data Target)]
    C -.->|3b. Jailbreak Detected| E[JSON-RPC 403: Session Aborted]

    classDef proxy fill:#121212,stroke:#0072ff,stroke-width:2px,color:#ffffff;
    classDef db fill:#0B0F19,stroke:#2ea043,stroke-width:2px,color:#ffffff;
    classDef alert fill:#2a0a0a,stroke:#ff453a,stroke-width:2px,color:#ffffff;
    
    class B,C proxy;
    class D db;
    class E alert;