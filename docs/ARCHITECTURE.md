# Enterprise Policy AI — Architecture Specification

This document provides a detailed specification of the architecture, design principles, and component interactions in the Enterprise Policy AI platform.

---

## 1. High-Level System Architecture

```
                  ┌────────────────────────────────────────┐
                  │                 USERS                  │
                  │   (Employees, Managers, Administrators)│
                  └───────────────────┬────────────────────┘
                                      │
                                      ▼
                  ┌────────────────────────────────────────┐
                  │           REACT 19 FRONTEND            │
                  │   Vite + SPA Routing + Glassmorphism   │
                  │   Dashboard • Ingestion • Assistant    │
                  │   Knowledge Base • Evaluation • Admin  │
                  └───────────────────┬────────────────────┘
                                      │
                         REST APIs / Bearer Token
                                      │
                                      ▼
                  ┌────────────────────────────────────────┐
                  │          FASTAPI ASGI CORE             │
                  │   Pydantic V2 • Uvicorn • Lifespan     │
                  │   Rate Limiting • Guardrails • RBAC    │
                  └───────┬──────────────┬─────────────┬───┘
                          │              │             │
                          ▼              ▼             ▼
                 ┌───────────────┐ ┌───────────┐ ┌───────────────┐
                 │  PostgreSQL   │ │   FAISS   │ │  Ollama LLM   │
                 │   16 + ORM    │ │VectorStore│ │ (Local Daemon)│
                 └───────┬───────┘ └─────┬─────┘ └───────┬───────┘
                         │               │               │
                         └───────────────┼───────────────┘
                                         ▼
                             ┌───────────────────────┐
                             │  RAG RETRIEVAL & QA   │
                             │  - Hybrid Fusion      │
                             │  - Relevance Cutoff   │
                             │  - Context Bounding   │
                             │  - Citation Validator │
                             │  - Audit Logging      │
                             └───────────────────────┘
```

---

## 2. End-to-End Ingestion & Query Lifecycle

### 2.1 Ingestion Flow
1. **Document Upload**: Multi-part upload receives `.pdf`, `.docx`, or `.txt` files up to 25 MB.
2. **Text Extraction**:
   - PDF: Structured extraction via `pypdf` with fallback to OCR via `pytesseract` for scanned image pages.
   - DOCX: Paragraph, heading, and table cell extraction preserving formatting.
   - TXT: Direct UTF-8 stream normalization.
3. **Text Cleaning**: Normalization of whitespace, removal of control characters, preservation of numerical identifiers, legal citations, and section headings.
4. **Semantic Chunking**: Recursive character splitting (`CHUNK_SIZE=900`, `CHUNK_OVERLAP=120`) respecting sentence boundaries and section delimiters.
5. **Relational Persistence**: Documents and chunks are persisted in PostgreSQL with chunk indices, page references, section headers, and token counts.
6. **Dense Embedding**: Chunks are embedded using SentenceTransformers (`all-MiniLM-L6-v2`, 384 dimensions) with L2 unit normalization.
7. **Vector Indexing**: Embedded vectors are indexed in FAISS (`IndexFlatIP`) for exact inner-product similarity (cosine equivalence) and stored on disk.

### 2.2 RAG Retrieval & Inference Flow
1. **Query Ingestion**: Natural language query received with optional conversation thread ID and document scoping.
2. **Conversation Memory Fusion**: Follow-up questions are resolved against prior dialogue history to maintain multi-turn context.
3. **Hybrid Search & Permission Filtering**:
   - Vector similarity query against FAISS.
   - Exact keyword match across PostgreSQL chunks.
   - Reciprocal Rank Fusion (RRF) merging with permission checks (USER vs. ADMIN document visibility).
4. **Relevance Cutoff & Hallucination Guardrail**:
   - Relevance threshold ($0.35$) applied.
   - If maximum similarity $< 0.35$, the system safely refuses without executing LLM inference.
5. **Context Packaging**: Top candidates are assembled into XML-bounded context (`<CONTEXT_DOCUMENTATION>`) with source IDs `[S1]`, `[S2]`.
6. **Prompt Construction & Injection Defense**: Context is isolated from system instructions to prevent prompt injection.
7. **Local LLM Synthesis**: Prompt sent to local Ollama runner (`llama3.2:3b`) with deterministic sampling (`temperature=0.1`).
8. **Citation Verification & Scrubbing**: Synthesized answer parsed to ensure all inline citations exist in retrieved context.
9. **Persistence & Audit**: Answer, latency metrics, and audit event logged to database.

---

## 3. Security, RBAC & Privacy Architecture
- **Zero Cloud Leakage**: All inference occurs 100% locally on premise using Ollama and local CPU embeddings.
- **RBAC Matrix**:
  - `USER`: Chat, own conversation sessions, organization-wide policy documents.
  - `MANAGER`: Team-shared documents and team analytics.
  - `ADMIN`: Full document management, index rebuilds, user roles, system health, audit logs.
- **Token Security**: Stateless JWTs using HMAC-SHA256 with configurable expiration. Passwords hashed using bcrypt.
