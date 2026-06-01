# Sovereign System Specification: Zerobus Ingestion Sandbox with Automated Schema Drift Fallback

**Classification**: Sovereign Architecture Design Specification (VP-Ready)  
**Status**: Approved for Design  
**Target Path**: `/home/abhishek/ObsidianVault/03_Active_Projects/databricks_sovereign_portfolio/track4_zerobus_ingest/track4_spec.md`

---

## 1. Executive Summary & Hardware Topology

This specification defines the architecture, data pipeline, and fault-tolerance boundaries for the **Zerobus Ingestion Sandbox with Automated Schema Drift Fallback**. 

In enterprise data lakes governed by Unity Catalog, schema mismatches between ingestion pipelines and delta storage targets lead to failed writes, pipeline locks, or data loss. This sandboxed architecture implements a localized schema validation and fallback system. Built as a high-velocity stream processing simulator, the engine checks incoming JSON events, routes validated records to a structured analytical storage table, and intercepts schema drifts or anomalies (e.g., type mismatches, missing fields) at the application layer, routing them to a Dead-Letter Queue (DLQ) database table without interrupting the execution pipeline.

```
                     ADRACA EDGE SOVEREIGN LAPTOP
┌────────────────────────────────────────────────────────────────────────┐
│                        JSON Event Stream Generator                     │
│  - Emits mix of compliant and anomalous schema-drifted events         │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ JSON Payload Stream
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        Zerobus Ingest Engine                           │
│  - Parses incoming JSON using Pydantic schemas                         │
│  - Route records conditionally based on validation status              │
└───────────────┬────────────────────────────────────────┬───────────────┘
                │ Valid Payload                          │ Invalid / Drifted
                ▼                                        ▼
┌──────────────────────────────────┐      ┌──────────────────────────────┐
│       primary_events Table       │      │   dead_letter_queue Table    │
│  - Analytical schema-compliant   │      │  - Raw payload storage       │
│  - Local DuckDB storage          │      │  - Error tracking metadata   │
└──────────────────────────────────┘      └──────────────────────────────┘
```

### Hardware Constraints:
1. **Local Compute**: The Ingestion Engine runs locally on the **Adraca Edge Laptop**, ensuring zero network dependency during local ingestion evaluation.
2. **Database Engine**: Uses an embedded, in-process **DuckDB analytical database** instance, mimicking the target Delta Lake analytical store under Unity Catalog governance.
3. **Identity & Authorization**: Simulates table structures matching Unity Catalog columns and data types.

---

## 2. Ingestion Flow & Schema Drift Handling

### 2.1 The Schema Validation Challenge
When high-velocity microservices ingest data, incoming schemas often drift (e.g., a field changes from integer to string, or a required field is missing due to a client-side update). Direct inserts into strict target tables trigger relational database constraint violations, causing database rollback or entire ingestion pipeline crashes.

### 2.2 Dual-Target Ingestion Path
To ensure high availability and schema enforcement, the Zerobus engine implements a dual-path routing loop:
1. **Payload Interception**: Evaluates every incoming JSON event against a pre-defined **Pydantic schema** mapping to our target storage model.
2. **Path A (Strict Compliant Path)**: If validation succeeds, the parsed fields are appended directly to the structured analytical DuckDB table `primary_events`.
3. **Path B (Schema Drift / Fallback Path)**: If validation fails (due to type mismatches, missing fields, or invalid schemas), the engine catches the validation exception. The raw payload is serialized alongside the exact parsing error message and timestamp, and appended to the `dead_letter_queue` table.
4. **Auditability**: Data engineers can query the `dead_letter_queue` to audit schema anomalies, write schema correction migrations, or replay corrected payloads.

---

## 3. Required Python Modules & Dependencies

The ingestion sandbox requires the following python libraries:
- **`duckdb`**: High-performance in-memory and disk-persisted analytical database.
- **`pydantic`**: Runtime data validation and parsing using strong type declarations.
- **`logging`**: Structured logging of events, validation failures, and table writes.
- **`time` / `random`**: Simulating event ingestion delays and query triggers.

---

## 4. Simulated Event Generator Design

The event stream generator simulates three types of payloads:
1. **Valid Compliant Payloads**: Matching the strict Pydantic model structure.
2. **Type Mismatch Anomalies**: Compliant keys, but values contain incorrect types (e.g., string instead of float).
3. **Structural Drift Anomalies**: Missing mandatory fields or invalid document structures.

---

## 5. Fault-Tolerance & Integrity Invariants

### Invariant 01: Non-Blocking Ingestion
> A validation failure in a single event payload MUST NOT crash the ingestion pipeline or block the processing of subsequent events in the stream.

### Invariant 02: Zero Data Loss (Total Count Balance)
> For any sequence of $N$ ingested events, the sum of rows in the `primary_events` table ($N_{valid}$) and the `dead_letter_queue` table ($N_{dlq}$) must exactly equal $N$:
> 
> $$N_{valid} + N_{dlq} = N$$

### Invariant 03: Detailed Error Auditability
> Every record stored in the `dead_letter_queue` table MUST contain the raw payload, the exception class, the detailed error message, and a precise ingestion timestamp.
