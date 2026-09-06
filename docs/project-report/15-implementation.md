# 13. Implementation Procedure

The end-to-end implementation followed a rigorous 16-step engineering workflow:

```text
Step 1: Environment & Dependency Installation
  - Python 3.14 virtual environment setup; installation of FastAPI, PyTorch, FAISS, SentenceTransformers, SQLAlchemy.
  - Node.js 22 environment setup; Vite & React 18 installation.

Step 2: Database Schema & Migration Configuration
  - Defined declarative SQLAlchemy models (`User`, `Document`, `DocumentChunk`, `ChatSession`, `ChatMessage`, `ChatFeedback`).
  - Configured Alembic for versioned schema migrations.

Step 3: Local LLM Configuration (Ollama)
  - Installed Ollama local runtime; pulled `llama3.2:3b` model weights.
  - Verified local daemon response on port 11434.

Step 4: Document Ingestion & Multi-Format Parsing
  - Built parsers for PDF (`pypdf`), Word (`python-docx`), and TXT files.
  - Implemented filename sanitization and MIME-type validation.

Step 5: Semantic Chunking Engine
  - Implemented recursive text splitting with a 500-character window and 100-character overlap.
  - Preserved clause numbers (e.g., Section 4.1) across chunk splits.

Step 6: Dense Embedding Pipeline
  - Integrated `sentence-transformers/all-MiniLM-L6-v2`.
  - Configured batch embedding processing and $L_2$ unit normalization.

Step 7: FAISS Vector Database Setup
  - Initialized FAISS `IndexFlatIP` (384 dimensions).
  - Implemented index persistence (`index.faiss`) and metadata mapping (`metadata.json`).

Step 8: Top-K Vector Retrieval & Threshold Filtering
  - Implemented cosine similarity search returning Top-5 nearest neighbors.
  - Configured relevance threshold cutoff ($s \ge 0.35$).

Step 9: Anti-Hallucination & Anti-Injection Context Assembly
  - Constructed prompt templates isolating context inside XML tags (`<CONTEXT_DOCUMENTATION>`).
  - Implemented safe refusal mechanisms for unanswerable or out-of-domain queries.

Step 10: Local Ollama Orchestration
  - Built an asynchronous HTTP client connecting to Ollama `/api/generate`.
  - Configured deterministic sampling (temperature = 0.1, top_p = 0.9).

Step 11: Response Parsing & Source Attribution
  - Implemented citation validation cross-referencing answer citations with retrieved chunks.
  - Formatted chunk metadata (document name, page number, chunk ID).

Step 12: Chat Session Persistence
  - Recorded user queries, AI responses, latency breakdowns, and feedback ratings in PostgreSQL.

Step 13: Administrative & Monitoring Endpoints
  - Created `/api/system/health`, `/api/knowledge-base/status`, and index rebuild endpoints.

Step 14: Modern React Single-Page Application
  - Developed responsive UI with Dashboard, Documents, Assistant Chat, History, Knowledge Base, and Evaluation tabs.

Step 15: Automated Test Suite Construction
  - Authored 94 comprehensive Pytest unit and integration tests achieving 100% pass rate.

Step 16: Empirical Benchmarking & Verification
  - Executed 35-query evaluation runner to record empirical accuracy, precision, recall, and latency metrics.
```

---

## 14. Important Implementation Code References

### 1. Dense Embedding Initialization (`backend/app/rag/embeddings.py`)
```python
class EmbeddingService:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self.model = SentenceTransformer(model_name)
        self.dimension = self.model.get_sentence_embedding_dimension()

    def embed_text(self, text: str) -> np.ndarray:
        if not text.strip():
            return np.zeros(self.dimension, dtype=np.float32)
        vec = self.model.encode(text, convert_to_numpy=True)
        norm = np.linalg.norm(vec)
        return vec / norm if norm > 0 else vec
```

### 2. FAISS Similarity Search (`backend/app/rag/vector_store.py`)
```python
class FAISSVectorStore:
    def search(self, query_vector: np.ndarray, top_k: int = 5) -> List[Dict[str, Any]]:
        query_vector = np.ascontiguousarray(query_vector.reshape(1, -1).astype(np.float32))
        scores, indices = self.index.search(query_vector, top_k)
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx != -1 and idx < len(self.metadata):
                meta = self.metadata[idx].copy()
                meta["similarity_score"] = float(score)
                results.append(meta)
        return results
```

### 3. Context Grounding Prompt Template (`backend/app/llm/prompt_builder.py`)
```python
GROUNDED_SYSTEM_PROMPT = """You are the enterprise policy assistant.
Answer the question using ONLY the provided documentation context below.
If the answer cannot be found in the context, reply:
"I cannot find sufficient policy documentation to answer this question accurately."
Do NOT fabricate rules or assume policies not stated in the context."""
```
