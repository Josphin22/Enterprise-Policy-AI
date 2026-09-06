# 9. System Architecture

The Local Enterprise Policy Assistant employs a decoupled, multi-tiered architecture that strictly isolates the presentation layer, the API gateway, the persistent relational data layer, the vector retrieval engine, and the local inference runtime.

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                            REACT 18 FRONTEND (Vite)                         │
│  - Dashboard  - Document Repository  - Policy Assistant  - Evaluation Suite │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ HTTP / REST (JSON)
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           FASTAPI ASYNC API GATEWAY                         │
│  - JWT Auth & RBAC  - Request Validation (Pydantic)  - CORS & Middleware    │
└──────────────┬───────────────────────┬──────────────────────┬───────────────┘
               │                       │                      │
               ▼                       ▼                      ▼
┌────────────────────────────┐  ┌──────────────┐  ┌───────────────────────────┐
│    POSTGRESQL RELATIONAL   │  │  PARSER &    │  │    RAG RETRIEVAL ENGINE   │
│          DATABASE          │  │  CHUNKER     │  │                           │
│ - users (auth & roles)     │  │ - PyPDF      │  │ - SentenceTransformers    │
│ - documents & metadata     │  │ - docx / txt │  │   (all-MiniLM-L6-v2, 384d)│
│ - document_chunks          │  │ - Normalizer │  │ - FAISS (IndexFlatIP)     │
│ - chat_sessions & messages │  │ - Overlap    │  │ - Top-K & Score Threshold │
│ - feedback & audit_logs    │  │   Chunking   │  │ - Context Assembly        │
└────────────────────────────┘  └──────────────┘  └───────────┬───────────────┘
                                                              │
                                                              ▼
                                                  ┌───────────────────────────┐
                                                  │    LOCAL OLLAMA ENGINE    │
                                                  │ - llama3.2:3b Quantized   │
                                                  │ - Anti-Injection Prompt   │
                                                  │ - Grounded Generation     │
                                                  └───────────────────────────┘
```

## Architectural Subsystems:

1. **Client Tier (React Frontend):** Single-page application built with React 18, Vite, and modern CSS. Manages UI state, navigation, real-time query submission, chat history rendering, and interactive source modal popups.
2. **API Gateway Tier (FastAPI):** High-throughput asynchronous ASGI server handling incoming HTTP requests, user authentication, payload validation, security filtering, and endpoint routing.
3. **Relational Persistence Tier (PostgreSQL / SQLAlchemy):** ACID-compliant database storing structured entity records, document metadata, chunk text, conversation logs, and user feedback ratings.
4. **Vector Retrieval Tier (FAISS + SentenceTransformers):** In-memory and disk-serialized vector database executing cosine similarity comparisons on 384-dimensional dense vectors.
5. **Generative Inference Tier (Ollama):** Local on-premise execution environment hosting the quantized `llama3.2:3b` model over a local REST socket (`http://localhost:11434`).
