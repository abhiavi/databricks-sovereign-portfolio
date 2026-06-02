---
marp: true
theme: default
paginate: true
_paginate: false
header: 'Natoma Ingress Interdiction Proxy'
footer: 'Track 1 Architecture | Databricks Sovereign AI Portfolio'
style: |
  section {
    font-family: 'Inter', system-ui, -apple-system, sans-serif;
    background: radial-gradient(circle at 0% 0%, #ffffff 0%, #f4f7fa 100%);
    color: #1d1d1f;
    padding: 60px;
    display: flex;
    flex-direction: column;
    justify-content: center;
  }
  h1 {
    background: linear-gradient(135deg, #0072ff 0%, #00c6ff 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    font-size: 2.8rem;
    font-weight: 800;
    margin-bottom: 20px;
  }
  h2 {
    color: #86868b;
    font-size: 1.4rem;
    font-weight: 500;
    margin-top: -10px;
    margin-bottom: 30px;
  }
  .card {
    background: rgba(255, 255, 255, 0.4);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    border: 1px solid rgba(255, 255, 255, 0.6);
    border-radius: 16px;
    padding: 24px;
    box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.04);
    margin-top: 10px;
  }
  .highlight {
    color: #0072ff;
    font-weight: 700;
  }
  ul {
    font-size: 1.1rem;
    line-height: 1.6;
  }
  li {
    margin-bottom: 8px;
  }
---

# Slide 1: Killing Agent Roulette
## The Probabilistic Fallacy of Agentic DB Execution

<div class="card">

- Deploying autonomous LLM agents with direct database access is <span class="highlight">architectural suicide</span>.
- Relying on probabilistic prompt templates to enforce catalog permissions invites rogue execution.
- LLM agentic tool-calls must be governed by deterministic, zero-trust gatekeepers.

</div>

---

# Slide 2: The MCP Security Gap
## How Semantic Jailbreaks Bypass Gateways

<div class="card">

- Model Context Protocol (MCP) payloads are generated dynamically by probabilistic models.
- Upstream prompt injections alter SQL parameters or request paths (e.g., `drop_table`, `../../tenant_id`).
- Without inline interdiction, the target database receives a validly formatted but <span class="highlight">highly malicious payload</span>.

</div>

---

# Slide 3: OBO Token Interdiction
## The Natoma Edge Architecture

<div class="card">

- We deploy a localized **Natoma Ingress Interdiction Proxy** at the edge boundary.
- Intercepted bearer tokens undergo asymmetric <span class="highlight">RS256 JWT validation</span> mimicking the Unity Catalog endpoint.
- Validated payloads are matched against a strict Metadata Containment Map before outbound routing.

</div>

---

# Slide 4: Deterministic Containment
## Proof of Isolation

<div class="card">

- Verified zero-bypass boundaries using our integration test harness:
  - **Valid Read Queries**: Executed and routed cleanly via Oracle Egress nodes.
  - **SQL Injection Attacks**: Blocked instantly returning strict JSON-RPC 403 errors.
  - **Cross-Tenant Directory Traversal**: Prevented at the proxy containment layer.

</div>

---

# Slide 5: Secure Your Enclaves
## Get the Sovereign Architecture Code

<div class="card">

- Stop trusting generative intent; enforce **Zero-Trust, Zero-Hop** gateway boundaries.
- Read the full architectural whitepaper containing FastAPI and OBO validator configurations.
- Access the production-ready code repository:
  - <span class="highlight">Link to GitHub & Full Article in Comments Below!</span>

</div>
