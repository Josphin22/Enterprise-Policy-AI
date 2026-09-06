# 4. Proposed System

The proposed **Local Enterprise Policy Assistant** is a modular, high-performance, and privacy-preserving RAG platform running 100% locally. The system eliminates hallucination and guarantees factual compliance by grounding every generative output in real-time retrieved enterprise documentation.

```text
Enterprise Documents (PDF, DOCX, TXT)
               │
               ▼
       [Text Extraction]  (PyPDF, python-docx, TxtLoader)
               │
               ▼
        [Text Cleaning]   (Whitespace normalization, Clause preservation)
               │
               ▼
       [Semantic Chunking] (CHUNK_SIZE=500, OVERLAP=100)
               │
               ▼
    [Relational Storage]  (PostgreSQL / SQLite: documents, chunks)
               │
               ▼
   [Embedding Generation] (SentenceTransformers all-MiniLM-L6-v2, 384d)
               │
               ▼
      [FAISS Vector Store] (IndexFlatIP Exact Normalized Inner Product)
               │
               │◄─────────────────── User Natural-Language Query
               ▼
     [Semantic Retrieval]  (Top-K=5 Cosine Similarity Search)
               │
               ▼
   [Relevance Filtering]  (Threshold score cutoff s >= 0.35)
               │
               ▼
   [Context Construction] (Bound to 5 chunks / 6000 chars, deduplication)
               │
               ▼
    [Local LLM Inference] (Ollama llama3.2:3b Quantized Local Runtime)
               │
               ▼
     [Grounded Generation] (Anti-hallucination prompt boundary)
               │
               ▼
   [Interactive Citations] (Verifiable document name, chunk ID, page number)
```

### Key Stages of the Pipeline:
1. **Multi-Format Ingestion:** Ingests `.pdf`, `.docx`, and `.txt` files with strict MIME type validation and file-size guardrails ($\le 20\text{ MB}$).
2. **Text Cleaning & Normalization:** Removes non-printable control characters while preserving alphanumeric policy clauses (e.g., "Section 4.1.2").
3. **Recursive Overlapping Chunking:** Splits long text into 500-character segments with 100-character overlap, maintaining boundary continuity.
4. **Vector Embedding:** Maps chunks into 384-dimensional dense vectors using `sentence-transformers/all-MiniLM-L6-v2` with $L_2$ normalization.
5. **Vector Indexing:** Persists normalized vectors into FAISS `IndexFlatIP` for sub-millisecond similarity lookup.
6. **Query Retrieval & Relevance Filtering:** Identifies Top-5 chunks; discards candidates below score $0.35$; safely refuses out-of-domain queries.
7. **Prompt Assembly & Local LLM Synthesis:** Packages qualified context inside structured XML delimiters and prompts the local Ollama LLM (`llama3.2:3b`).
8. **Citation Verification:** Enforces that all citations in the generated response correspond to actual context chunks.
