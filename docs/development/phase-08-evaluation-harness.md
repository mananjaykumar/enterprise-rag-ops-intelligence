# Phase 08: Evaluation & Test Harness
## Engineering Specification & Implementation Guide

**Phase:** 08  
**Status:** Completed ✅  
**Prerequisites:** Phase 01: Foundation | Phase 02: Auth & RBAC | Phase 03: Document Ingestion | Phase 04: Hybrid Retrieval | Phase 05: Grounded RAG | Phase 06: Secure Text-to-SQL | Phase 07: Stateful Agent Orchestrator  
**Objective:** Build an enterprise evaluation suite with a golden benchmark dataset, automated retrieval and generation metrics (Hit Rate@K, MRR, Faithfulness, Answer Relevance), Text-to-SQL AST verification, and a regression test harness with automated quality gates.

---

## 1. Architectural Philosophy & Strategy

Enterprise AI systems cannot be deployed or iterated upon safely without empirical evaluation. Relying on casual manual prompting leads to silent regressions in retrieval quality, citation hallucination, and agent routing degradation.

Phase 08 establishes a **Three-Dimensional Evaluation Harness**:
1. **Dimension 1: L1 Retrieval Quality (Deterministic Component Metrics)**
   - *Hit Rate@K (K=1, 3, 5):* Measures whether the ground-truth document chunk appears in the top $K$ retrieved results.
   - *Mean Reciprocal Rank (MRR):* Evaluates the ranking position of the primary target document chunk ($\frac{1}{\text{rank}}$).
2. **Dimension 2: L2 Generation Groundedness & Faithfulness (Semantic Model-as-a-Judge)**
   - *Faithfulness / Groundedness:* Measures whether every statement in the generated answer is directly backed by the retrieved document chunks, identifying hallucinations.
   - *Answer Relevance:* Evaluates whether the generated response directly answers the user's question without extraneous filler.
   - *Unsupported Claims Detection:* Extracts specific sentences that lack context evidence.
3. **Dimension 3: Text-to-SQL & Agent Routing Integrity**
   - *AST Security & Validity Rate:* Confirms 100% adherence to single-statement read-only SELECT rules.
   - *Table Whitelist Enforcement:* Rejects queries targeting sensitive non-operational tables (e.g. `users`, `document_chunks`).
   - *Intent Routing Precision:* Confirms queries are correctly classified into RAG, SQL, or Hybrid pathways.

```text
                           Golden Evaluation Dataset (JSON)
           ┌──────────────────────────────┼──────────────────────────────┐
           ▼                              ▼                              ▼
    [ Document Queries ]          [ SQL Queries ]               [ Hybrid Queries ]
           │                              │                              │
           ▼                              ▼                              ▼
   Hybrid Retrieval Engine       Text-to-SQL Engine          LangGraph State Machine
           │                              │                              │
           ├─────────────────────┬────────┴────────────┬─────────────────┤
           ▼                     ▼                     ▼                 ▼
     Hit Rate & MRR       Groundedness Judge     SQL AST & Whitelist Routing Accuracy
     (Ranked Chunks)      (Faithfulness Score)   (Row Match Rate)   (Route Alignment)
           │                     │                     │                 │
           └─────────────────────┴─────────┬───────────┴─────────────────┘
                                           ▼
                           Evaluation Report & Quality Gate
                             (Pass >= Target Thresholds)
```

---

## 2. Implementation Summary

| Component | Module | Responsibility |
|---|---|---|
| Benchmark Dataset | `data/evaluation/golden_dataset.json` | Golden test cases across document policies, operational SQL queries, and hybrid comparative prompts. |
| Evaluation Schemas | `src/schemas/evaluation.py` | Pydantic contracts for benchmark datasets, retrieval scores, groundedness metrics, and executive summary reports. |
| Evaluation Engine | `src/services/evaluation.py` | L1 mathematical metrics (Hit Rate@K, MRR), L2 LLM-as-a-Judge structured groundedness scoring, AST validation, and quality gates. |
| Unit Test Suite | `tests/unit/test_evaluation.py` | Automated tests verifying mathematical correctness, AST security checks, synthetic hallucination detection, and threshold decisions. |
| CLI Benchmark Runner | `scripts/run_evaluation.py` | Standalone CLI utility generating executive console summaries and exporting JSON artifacts for CI/CD pipelines. |

---

## 3. Latest Benchmark Results (`data/evaluation/latest_eval_report.json`)

```text
=================================================================
       ENTERPRISE INTELLIGENCE EVALUATION SUMMARY REPORT       
=================================================================
 Total Benchmark Test Cases Evaluated : 3
 Retrieval Hit Rate@3 Threshold (>=70%): 100.0%
 Retrieval Mean Reciprocal Rank (MRR) : 1.0000
 Average Answer Faithfulness (>=75%)  : 100.0%
 Average Answer Relevance    (>=75%)  : 100.0%
 SQL AST Security Pass Rate  (==100%) : 100.0%
 Query Intent Routing Accuracy(>=80%) : 100.0%
-----------------------------------------------------------------
 OVERALL QUALITY GATE DECISION         : [ PASSED ✅ ]
=================================================================
```

---

## 4. Architectural Decisions & Trade-Offs

### Decision 1: Native Evaluation Engine vs. Heavy External Frameworks
- **Decision:** Build a native, strongly-typed evaluation service using Pydantic, `sqlglot`, and the existing `BaseLLMClient` instead of adopting heavy external evaluation libraries (like full `ragas` or `deepeval`).
- **Trade-off:** Building native evaluation requires maintaining custom judge prompts, but avoids pulling in dozens of heavy transitive dependencies (LangChain community, OpenAI SDKs, PyTorch datasets) that inflate container size and trigger API rate-limit bottlenecks.

### Decision 2: Structured Outputs for Model-as-a-Judge
- **Decision:** Utilize Gemini's native `generate_structured(response_schema=GroundednessScore)` rather than unstructured text prompts with regex parsing.
- **Trade-off:** Eliminates JSON parse errors, markdown code-fence stripping issues, and non-deterministic response structures during evaluation runs.

### Decision 3: Two-Tier Metric Separation (L1 vs. L2)
- **Decision:** Separate fast, deterministic component metrics (Hit Rate, MRR, AST syntax) from semantic LLM judge metrics.
- **Trade-off:** L1 metrics run in milliseconds without token costs, allowing rapid local testing. L2 LLM judge calls are reserved for generation validation, conserving API quotas.

---

## 5. Senior System Architect Interview Defense

### Q1: How do you mitigate Model-as-a-Judge evaluation bias?
> **Defense:** LLM judges are susceptible to position bias, verbosity bias (favoring longer responses), and self-enhancement bias. We mitigate this through:
> 1. Strict zero-temperature deterministic sampling (`temperature=0.0`).
> 2. Pydantic-enforced structured schemas separating numerical scores from evidence-backed `unsupported_claims`.
> 3. Two-pass claim verification: the judge must extract individual claims from the answer before verifying them against the context passages.

### Q2: Why calculate L1 metrics before calling L2 LLM judges?
> **Defense:** Cost and latency efficiency. If retrieval fails (Hit Rate = 0), generation will inevitably fail or hallucinate. In production CI/CD pipelines, checking L1 retrieval metrics first allows fast-fail execution: if search quality drops below acceptable thresholds, the pipeline halts immediately without wasting LLM tokens on semantic generation evaluation.

### Q3: How does this evaluation harness integrate into a production CI/CD pipeline?
> **Defense:** `scripts/run_evaluation.py` is designed as a standard UNIX CLI tool. It emits machine-readable JSON artifacts (`data/evaluation/latest_eval_report.json`) and returns exit code `0` on quality gate pass and exit code `1` on failure. In GitHub Actions or GitLab CI, pull requests that cause retrieval accuracy, SQL security, or answer faithfulness to fall below configured thresholds are automatically blocked from merging.
