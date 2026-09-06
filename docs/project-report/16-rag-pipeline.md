# 15. The RAG Pipeline & Anti-Hallucination Architecture

```text
               User Policy Question
                        │
                        ▼
      [Query Normalization & Validation]
                        │
                        ▼
        [Dense Vector Embedding (384d)]
      (sentence-transformers/all-MiniLM-L6-v2)
                        │
                        ▼
         [FAISS Cosine Similarity Search]
             (IndexFlatIP, Top-K = 5)
                        │
                        ▼
          [Relevance Threshold Filter]
         (Prune candidates if score < 0.35)
                        │
           ┌────────────┴────────────┐
           ▼                         ▼
   [Score < 0.35]            [Score >= 0.35]
(Insufficient Context)      (Qualified Chunks)
           │                         │
           ▼                         ▼
    [Safe Refusal]          [Deduplication & Bounding]
(Zero Hallucination)        (Max 5 chunks, 6000 chars)
                                     │
                                     ▼
                            [Prompt Assembly]
                       (<CONTEXT_DOCUMENTATION>)
                                     │
                                     ▼
                            [Local LLM Inference]
                           (Ollama: llama3.2:3b)
                                     │
                                     ▼
                         [Response Citation Parser]
                      (Cross-reference [S#] markers)
                                     │
                                     ▼
                        [Grounded Answer Output]
```

## Why RAG is Preferred Over Direct LLM Querying:
1. **Dynamic Policy Updates:** When a policy is amended, replacing the document instantly updates the knowledge base without retraining the model.
2. **Zero Factual Hallucination:** By restricting the LLM to synthesized context chunks, the model is prevented from guessing non-existent corporate rules.
3. **Auditable Verifiability:** Every generated claim includes an interactive citation linking back to the exact chunk and document source.
4. **Data Security:** Proprietary documents remain in local vector storage and are never uploaded to commercial public LLM clouds.
