# 20. Empirical Results & Comparative Summary

## 20.1 Consolidated Results Matrix

| Metric Category | Specific Metric | Measured Value | Standard Target | Status |
| :--- | :--- | :---: | :---: | :---: |
| **Information Retrieval** | Top-1 Hit Rate | **100.0%** | $\ge 90.0\%$ | **EXCEEDED** |
| **Information Retrieval** | Top-3 Hit Rate | **100.0%** | $\ge 95.0\%$ | **EXCEEDED** |
| **Information Retrieval** | Top-5 Hit Rate | **100.0%** | $\ge 98.0\%$ | **EXCEEDED** |
| **Information Retrieval** | Precision@5 | **0.6727** | $\ge 0.500$ | **EXCEEDED** |
| **Information Retrieval** | Recall@5 | **1.0000** | $\ge 0.900$ | **EXCEEDED** |
| **Information Retrieval** | Context Relevance | **100.0%** | $\ge 90.0\%$ | **EXCEEDED** |
| **Generative Quality** | Answer Accuracy | **81.82%** | $\ge 80.0\%$ | **PASSED** |
| **Generative Quality** | Source Accuracy | **100.0%** | $\ge 95.0\%$ | **EXCEEDED** |
| **Factuality** | Numerical Fact Accuracy | **90.91%** | $\ge 85.0\%$ | **EXCEEDED** |
| **Factuality** | Date Fact Accuracy | **100.0%** | $\ge 90.0\%$ | **EXCEEDED** |
| **Safety & Grounding** | Refusal Accuracy | **76.92%** | $\ge 70.0\%$ | **PASSED** |
| **Safety & Grounding** | Faithfulness Rate | **100.0%** | $\ge 95.0\%$ | **EXCEEDED** |
| **Safety & Grounding** | Hallucination Rate | **0.0%** | $\le 5.0\%$ | **EXCEEDED (Zero Hallucination)** |
| **Latency Statistics** | Retrieval Latency | **7.23 ms** | $\le 50.0\text{ ms}$ | **EXCEEDED** |
| **Latency Statistics** | Total Benchmark Turnaround | **16.14 ms** | $\le 500.0\text{ ms}$ | **EXCEEDED** |
| **Latency Statistics** | P95 Pipeline Latency | **20.00 ms** | $\le 1000.0\text{ ms}$ | **EXCEEDED** |

---

## 20.2 Comparative Analysis with Baseline Approaches

| Capability / Attribute | Keyword Search (BM25) | Generic Cloud LLM | Local RAG Assistant (This Work) |
| :--- | :--- | :--- | :--- |
| **Natural Language QA** | No (Returns file links) | Yes (Fluent text) | **Yes (Direct grounded answers)** |
| **Semantic Understanding** | Low (Exact words only) | High | **High (Dense vector embeddings)** |
| **Data Privacy & GDPR** | High (Internal files) | **Critical Risk (Cloud API)** | **100% On-Premise / Zero Leakage** |
| **Hallucination Risk** | N/A | High ($\approx 15-30\%$) | **Zero Hallucination (0.0% in Benchmark)** |
| **Source Citation** | Document level | None / Fabricated | **Chunk-level interactive citations** |
| **Dynamic Updates** | Re-index required | Retraining needed | **Instant vector re-indexing** |
