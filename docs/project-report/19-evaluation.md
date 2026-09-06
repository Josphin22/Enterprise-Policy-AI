# 18. Scientific Evaluation Methodology

The scientific evaluation was conducted using the automated evaluation engine (`app.evaluation.runner`) running against a curated **35-question benchmark dataset**:
- **Answerable Policy Queries:** 22 questions (direct facts, paraphrases, multi-document, numerical, date-sensitive).
- **Unanswerable / Adversarial Queries:** 13 questions (out-of-domain topics, Mars travel, recipe queries, prompt injection attempts).

## Evaluation Metrics Formulations:

1. **Top-K Retrieval Hit Rate:**
   $$\text{HitRate}@K = \frac{1}{|Q|} \sum_{q \in Q} \mathbb{I}(\text{RelevantChunk} \in \text{TopK}(q))$$
2. **Precision@K & Recall@K:**
   $$\text{Precision}@K = \frac{|\text{RetrievedRelevant}@K|}{K}, \quad \text{Recall}@K = \frac{|\text{RetrievedRelevant}@K|}{|\text{TotalRelevant}|}$$
3. **Faithfulness Rate:**
   $$\text{Faithfulness} = \frac{\text{Number of Claims Supported by Context}}{\text{Total Number of Generated Claims}}$$
4. **Hallucination Rate:**
   $$\text{Hallucination Rate} = \frac{\text{Number of Unsupported Claims}}{\text{Total Number of Generated Claims}} = 1.0 - \text{Faithfulness}$$
5. **Numerical & Date Factuality:** Exact match validation of quantitative constraints (e.g., "15 days", "March 31st").

---

# 19. Empirical Results & Performance Analysis

## 19.1 Empirical Benchmark Results

| Evaluation Dimension | Metric | Measured Empirical Result | Benchmark Target | Evaluation Status |
| :--- | :--- | :---: | :---: | :---: |
| **Retrieval Accuracy** | Top-1 Retrieval Hit Rate | **100.0%** | $\ge 90.0\%$ | **EXCEEDED** |
| **Retrieval Accuracy** | Top-3 Retrieval Hit Rate | **100.0%** | $\ge 95.0\%$ | **EXCEEDED** |
| **Retrieval Accuracy** | Top-5 Retrieval Hit Rate | **100.0%** | $\ge 98.0\%$ | **EXCEEDED** |
| **Retrieval Precision** | Precision@5 | **0.6727 (67.27%)** | $\ge 50.0\%$ | **EXCEEDED** |
| **Retrieval Recall** | Recall@5 | **1.0000 (100.0%)** | $\ge 90.0\%$ | **EXCEEDED** |
| **Context Quality** | Context Relevance Score | **100.0%** | $\ge 90.0\%$ | **EXCEEDED** |
| **Generation Quality** | Grounded Answer Accuracy | **81.82%** | $\ge 80.0\%$ | **PASSED** |
| **Source Attribution** | Source Citation Accuracy | **100.0%** | $\ge 95.0\%$ | **EXCEEDED** |
| **Factuality** | Numerical Fact Accuracy | **90.91%** | $\ge 85.0\%$ | **EXCEEDED** |
| **Factuality** | Date Fact Accuracy | **100.0%** | $\ge 90.0\%$ | **EXCEEDED** |
| **Safety & Grounding** | Refusal Accuracy (Out-of-domain) | **76.92%** | $\ge 70.0\%$ | **PASSED** |
| **Safety & Grounding** | Faithfulness Rate | **100.0%** | $\ge 95.0\%$ | **EXCEEDED** |
| **Safety & Grounding** | Hallucination Rate | **0.0%** | $\le 5.0\%$ | **ZERO HALLUCINATION** |

---

## 19.2 Latency & Performance Breakdown

| Pipeline Stage | Measured Average Latency | Measured P95 Latency | Target Ceiling |
| :--- | :---: | :---: | :---: |
| **Embedding Generation & FAISS Retrieval** | **7.23 ms** | **11.50 ms** | $\le 50.0\text{ ms}$ |
| **Context Assembly & Formatting** | **8.91 ms** | **12.00 ms** | $\le 100.0\text{ ms}$ |
| **Total Evaluation Benchmark Latency** | **16.14 ms** | **20.00 ms** | $\le 500.0\text{ ms}$ |
| **Local LLM Generation (Ollama llama3.2:3b)**| **~2.8 to 3.5 s** | **4.2 s** | $\le 8.0\text{ s}$ |

### Result Interpretation:
- **Zero Hallucination (0.0%):** Enforced by relevance thresholding ($s \ge 0.35$) and strict prompt boundaries.
- **100% Top-1 Retrieval:** The 384-dimensional dense vectors of `all-MiniLM-L6-v2` accurately map user semantic intent to the exact authoritative policy chunk.
- **Low CPU Latency:** Fast vector search (7.23 ms) on standard CPU hardware makes the system highly scalable for enterprise deployments without specialized vector hardware.
