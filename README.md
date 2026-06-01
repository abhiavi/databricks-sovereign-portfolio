# Databricks Sovereign AI Architecture Portfolio

## Executive Summary
This repository contains a suite of five production-hardened proxy and middleware engines designed to solve Databricks' most critical architecture vulnerabilities when deployed in sovereign, air-gapped, or highly regulated enterprise environments. By decoupling security validation from standard cloud-plane layers, these engines eliminate systemic risks in agentic execution, vector database row-level security (RLS) stripping, serverless memory starvation, ingestion schema drifts, and PII model memorization. 

Every engine in this portfolio is built with strict edge isolation in mind, implementing local in-memory analytical storage, direct cgroup event polling, and pre-query AST manipulation.

---

## The 5 Security and Performance Tracks

*   **Track 1: [Ingress Interdiction Proxy for Databricks Supervisor Agents (track1_supervisor_mcp)](file:///home/abhishek/ObsidianVault/03_Active_Projects/databricks_sovereign_portfolio/track1_supervisor_mcp/)**
    *   *Problem*: Databricks Supervisor Agents blindly trust LLM-generated tool-call intents, exposing network egress channels to prompt injection and malicious commands.
    *   *Solution*: Intercepts and parses Model Context Protocol (MCP) JSON-RPC payloads at the edge, enforcing OBO (On-Behalf-Of) asymmetric RS256 JWT signature verification and a hardcoded Metadata Containment Map.
    *   *Whitepaper*: [Defeating Agent Roulette: Securing Databricks MCP Orchestration with OBO Token Interdiction (medium_article.md)](file:///home/abhishek/ObsidianVault/03_Active_Projects/databricks_sovereign_portfolio/track1_supervisor_mcp/medium_article.md)
*   **Track 2: [Dynamic ABAC Vector Injection Proxy (track2_vector_abac)](file:///home/abhishek/ObsidianVault/03_Active_Projects/databricks_sovereign_portfolio/track2_vector_abac/)**
    *   *Problem*: Syncing Delta Lake tables governed by Unity Catalog to downstream vector search engines strips Row-Level Security (RLS) data, causing privilege escalation.
    *   *Solution*: Intercepts semantic queries, resolves user clearance permissions, and dynamically injects metadata filters into the Qdrant `query_points` AST at runtime, ensuring strict mathematical isolation.
    *   *Whitepaper*: [The Vector Search Blind Spot: Restoring Unity Catalog ABAC in Databricks RAG Pipelines (track2_medium.md)](file:///home/abhishek/ObsidianVault/03_Active_Projects/databricks_sovereign_portfolio/track2_vector_abac/track2_medium.md)
*   **Track 3: [Serverless Kubernetes NeonVM Cgroups Monitor (track3_neonvm_scaling)](file:///home/abhishek/ObsidianVault/03_Active_Projects/databricks_sovereign_portfolio/track3_neonvm_scaling/)**
    *   *Problem*: Kubernetes metrics-server polling latency (15-60s) fails to detect sudden memory spikes during agentic query loads, leading to fatal Out-Of-Memory (OOM) database crashes.
    *   *Solution*: A localized daemon that bypasses the container orchestration plane by polling Linux kernel cgroups v2 event descriptors (`memory.events`) at 5ms intervals, executing in-place memory limit increases in microseconds.
    *   *Whitepaper*: [The Database Auto-Scaling Crash: Sub-Millisecond NeonVM Scaling via Linux Cgroups (track3_medium.md)](file:///home/abhishek/ObsidianVault/03_Active_Projects/databricks_sovereign_portfolio/track3_neonvm_scaling/track3_medium.md)
*   **Track 4: [Zerobus Ingestion Sandbox with Automated Schema Drift Fallback (track4_zerobus_ingest)](file:///home/abhishek/ObsidianVault/03_Active_Projects/databricks_sovereign_portfolio/track4_zerobus_ingest/)**
    *   *Problem*: Legacy message broker ingestion stacks (Kafka $\rightarrow$ Spark $\rightarrow$ Delta) introduce severe latency and operational costs, but direct database ingestion is highly vulnerable to schema-drift crashes.
    *   *Solution*: An in-process validation proxy that runs at the edge and utilizes strict Pydantic schemas to validate JSON event streams. Non-compliant records are automatically captured and routed to a DuckDB Dead-Letter Queue (DLQ) without pipeline interruption or data loss.
    *   *Whitepaper*: [Zero-Hop Resilience: Bypassing the Kafka Tax in Databricks Ingestion Pipelines (track4_medium.md)](file:///home/abhishek/ObsidianVault/03_Active_Projects/databricks_sovereign_portfolio/track4_zerobus_ingest/track4_medium.md)
*   **Track 5: [Automated Inference Table PII Sanitization Pipeline (track5_inference_sanitization)](file:///home/abhishek/ObsidianVault/03_Active_Projects/databricks_sovereign_portfolio/track5_inference_sanitization/)**
    *   *Problem*: Logging raw prompts and model completions to inference tables results in downstream LLMs memorizing and leaking personal identifiers (PAN, Aadhaar), violating data protection acts (DPDP, EU AI Act).
    *   *Solution*: An asynchronous sanitization daemon that queries unprocessed database records, applies optimized regular expressions, and performs physically-destructive updates in place to redact PII before instruction fine-tuning occurs.
    *   *Whitepaper*: [The Inference Paradox: Air-Gapping PII from Databricks LLM Fine-Tuning Pipelines (track5_medium.md)](file:///home/abhishek/ObsidianVault/03_Active_Projects/databricks_sovereign_portfolio/track5_inference_sanitization/track5_medium.md)

---

## Architecture Philosophy

The design of the Databricks Sovereign AI Portfolio is governed by three fundamental engineering mandates:

1.  **Zero-Trust Boundaries**: Raw execution tokens, query payloads, and model telemetry are treated as untrusted. Authorization and validation must occur at the edge prior to egress or relational commit operations.
2.  **Zero-Hop Ingestion**: Collapsing intermediate broker infrastructure reduces operational complexity and latency, using local embedded engines (DuckDB/SQLite) to maintain localized data sovereignty.
3.  **Mathematically Verified Containment**: Security boundaries are subjected to deterministic integration testing. Invariants—such as metric space query pruning and complete data preservation ($N_{\text{valid}} + N_{\text{dlq}} = N_{\text{total}}$)—are verified programmatically.
