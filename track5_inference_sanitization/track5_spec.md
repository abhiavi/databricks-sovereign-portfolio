# Sovereign System Specification: Automated Inference Table PII Sanitization Pipeline

**Classification**: Sovereign Architecture Design Specification (VP-Ready)  
**Status**: Approved for Design  
**Target Path**: `/home/abhishek/ObsidianVault/03_Active_Projects/databricks_sovereign_portfolio/track5_inference_sanitization/track5_spec.md`

---

## 1. Executive Summary & Hardware Topology

This specification defines the architecture, data structures, and regulatory invariants for the **Automated Inference Table PII Sanitization Pipeline**.

Enterprise AI deployments log all user prompts and model completions to inference history tables for auditability and downstream model fine-tuning. However, users frequently leak Personal Identifiable Information (PII) into prompts, violating data sovereignty regulations (e.g., India's Digital Personal Data Protection Act, or DPDP Act). This pipeline runs as a localized asynchronous worker at the edge. It continuously monitors incoming inference logs, scans for PII leaks (specifically Aadhaar card numbers and PAN card numbers), performs in-place redaction, and flags the sanitized records as approved for downstream fine-tuning.

```
                  LOCAL EDGE COMPUTE BOUNDARY
┌────────────────────────────────────────────────────────────────────────┐
│                        Inference Logger Client                         │
│  - Captures prompts & completions (with potential PII)                 │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ SQL INSERTS (is_sanitized = FALSE)
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                   Local DuckDB Delta-Store Replica                     │
│  - Table: 'inference_logs'                                             │
└───────────────┬────────────────────────────────────────▲───────────────┘
                │ Reads Unprocessed Rows                 │ Writes Redacted Text
                ▼ (is_sanitized = FALSE)                 │ (is_sanitized = TRUE)
┌────────────────────────────────────────────────────────┴───────────────┐
│                   PII Sanitization Daemon                              │
│  - Continuously scans prompts & completions using regex workers         │
│  - Target Aadhaar Format: \d{4}[ -]?\d{4}[ -]?\d{4}                    │
│  - Target PAN Format: [A-Z]{5}\d{4}[A-Z]                               │
└────────────────────────────────────────────────────────────────────────┘
```

### Hardware Constraints:
1. **Local Compute**: The Sanitization Engine runs as a background process locally on **edge hardware**, maintaining data boundary sovereignty.
2. **Database Engine**: We will simulate Databricks Delta tables using a local **DuckDB analytical database** (`sanitizer.duckdb`).
3. **Regulatory Context**: Designed to comply with DPDP Act mandates (Right to Erasure and Purpose Limitation) before fine-tuning datasets are constructed.

---

## 2. In-Place Redaction & Detection Logic

### 2.1 The Downstream Leakage Threat
Model fine-tuning pipelines consume raw tables of historical completions. If a user prompts: *"My Aadhaar is 1234 5678 9012, please check my application,"* and the raw log is fed to training, the LLM will memorize the Aadhaar association. The model will subsequently leak the credential to unrelated users under semantic prompts.

### 2.2 Asynchronous Sanitization Workers
The sanitization daemon executes a continuous scan loop:
1. **Selection Query**: Retrieves unprocessed rows from the database:
   ```sql
   SELECT id, prompt, completion FROM inference_logs WHERE is_sanitized = FALSE;
   ```
2. **Regex Evaluation**: Applies compiled regular expressions to identify target patterns:
   - **Aadhaar Numbers**: 12-digit Indian national identity numbers. Supported formats include 12 consecutive digits (`\d{12}`) or three blocks of four digits separated by spaces (`\d{4}\s\d{4}\s\d{4}`) or hyphens (`\d{4}-\d{4}-\d{4}`).
     - Regex: `\b\d{4}[ -]?\d{4}[ -]?\d{4}\b`
   - **Permanent Account Numbers (PAN)**: 10-digit alphanumeric Indian tax IDs.
     - Regex: `\b[A-Z]{5}\d{4}[A-Z]\b`
3. **In-Place Redaction**: If a match is found, the text is overwritten directly replacing the matched string with `[REDACTED_AADHAAR]` or `[REDACTED_PAN]`.
4. **State Commit**: Overwrites the row in the table, setting `is_sanitized = TRUE` and saving the timestamp.

---

## 3. Required Python Modules & Dependencies

The sanitization pipeline requires:
- **`duckdb`**: In-process database storage.
- **`re`**: Python built-in regular expression library with compiled regex optimization.
- **`logging`**: Precise logging of sanitization events, execution metrics, and throughput.
- **`time` / `datetime`**: Telemetry and poll interval mapping.

---

## 4. Mock Inference Data Generator Design

To test the resilience of the pipeline, the data generator populates the `inference_logs` table with:
1. **Clean Records**: Standard business interactions without PII.
2. **Aadhaar Leakage Records**: User prompts containing formatted Aadhaar numbers in different spacing variations.
3. **PAN Leakage Records**: Completions or prompts containing PAN tax IDs.
4. **Multi-PII Records**: Prompts containing both PAN and Aadhaar records in the same block.

---

## 5. DPDP Act Compliance & Security Invariants

### Invariant 01: Zero Leaked PII in Fine-Tuning Corpus
> Fine-tuning pipelines MUST only query rows where `is_sanitized = TRUE`. Any row processed by the pipeline must have zero matches when scanned by the Aadhaar or PAN regex patterns.

### Invariant 02: Asymmetric In-Place Redaction (Right to Erasure)
> The original PII text MUST be completely overwritten in the database file. Merely masking the text in view layers is insufficient; raw data must be purged from the storage layer.

### Invariant 03: Processing SLA
> The sanitization daemon must process new rows within a configurable target SLA (e.g., $< 1.0\text{ second}$ of insert).
