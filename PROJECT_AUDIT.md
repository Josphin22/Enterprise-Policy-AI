# Enterprise Policy AI — Project Audit

## Frontend
- **Framework**: React 19 (`19.2.8`), Vite (`8.2.2`)
- **Version**: `0.0.0` (Development/Academic Release 2026)
- **Main Entry Point**: [`frontend/src/main.jsx`](file:///e:/GEN%20AI/frontend/src/main.jsx) mounts [`frontend/src/App.jsx`](file:///e:/GEN%20AI/frontend/src/App.jsx)
- **Routing**: Single-Page Application (SPA) with custom responsive tab-based router in [`App.jsx`](file:///e:/GEN%20AI/frontend/src/App.jsx)
- **Pages**:
  1. **Dashboard** ([`frontend/src/pages/Dashboard.jsx`](file:///e:/GEN%20AI/frontend/src/pages/Dashboard.jsx)): System status cards, metrics, document list, recent queries.
  2. **Documents** ([`frontend/src/pages/Documents.jsx`](file:///e:/GEN%20AI/frontend/src/pages/Documents.jsx)): Multi-format file uploader (PDF, DOCX, TXT), document status table, chunk inspector modal.
  3. **AI Assistant** ([`frontend/src/pages/Assistant.jsx`](file:///e:/GEN%20AI/frontend/src/pages/Assistant.jsx)): Interactive RAG chat UI, streaming responses, inline `[S#]` citations, latency badge, source drawer.
  4. **Chat History** ([`frontend/src/pages/ChatHistory.jsx`](file:///e:/GEN%20AI/frontend/src/pages/ChatHistory.jsx)): Historical session browser, message viewer, user feedback tags.
  5. **Knowledge Base** ([`frontend/src/pages/KnowledgeBase.jsx`](file:///e:/GEN%20AI/frontend/src/pages/KnowledgeBase.jsx)): FAISS index status, vector count, rebuild trigger, test semantic search workbench.
  6. **Evaluation** ([`frontend/src/pages/Evaluation.jsx`](file:///e:/GEN%20AI/frontend/src/pages/Evaluation.jsx)): Scientific benchmark dashboard (35 questions, 10 categories), hit rates, hallucination rate, latency profile.
  7. **Settings** ([`frontend/src/pages/Settings.jsx`](file:///e:/GEN%20AI/frontend/src/pages/Settings.jsx)): Backend URL, Ollama model picker, chunking parameters, RAG retrieval thresholds.
- **API Communication Method**: Axios HTTP client configured in [`frontend/src/services/api.js`](file:///e:/GEN%20AI/frontend/src/services/api.js) connecting to `http://localhost:8000`.

## Backend
- **Framework**: FastAPI (`0.141.1`), Uvicorn (`0.52.4`), Pydantic v2 (`2.13.4`)
- **Python Version**: Python 3.14.6 (64-bit AMD64)
- **Entry Point**: [`backend/app/main.py`](file:///e:/GEN%20AI/backend/app/main.py)
- **API Structure**:
  - `/api/health`: Service health check
  - `/api/system`: Subsystem status (`/status`) and comprehensive diagnostic health (`/health`)
  - `/api/documents`: Document upload, listing, retrieval, deletion, processing, chunk inspection
  - `/api/knowledge-base`: Status, vector building/rebuilding, semantic search
  - `/api/chat`: Session creation, chat message dispatch, history retrieval, feedback
  - `/api/rag`: RAG context retrieval endpoint (`/retrieve`)
  - `/api/llm`: Ollama daemon status (`/status`) and installed model enumeration (`/models`)
  - `/api/evaluation`: Scientific evaluation summary (`/summary`), results (`/results`), run (`/run`)

## Database
- **Database Type**: SQLite default (`backend/enterprise_rag.db`) for zero-setup execution; PostgreSQL 16 Alpine containerized ready in [`docker-compose.yml`](file:///e:/GEN%20AI/docker-compose.yml)
- **Connection Method**: SQLAlchemy 2.0 ORM engine (`sqlite:///./enterprise_rag.db` / `postgresql://postgres:postgres@localhost:5432/enterprise_rag`) managed via [`backend/app/database/connection.py`](file:///e:/GEN%20AI/backend/app/database/connection.py) with Alembic migration scripts in [`backend/alembic/`](file:///e:/GEN%20AI/backend/alembic/)
- **Existing Tables / Models**:
  - `users`: User entity and role model ([`backend/app/models/user.py`](file:///e:/GEN%20AI/backend/app/models/user.py))
  - `documents`: Document repository records ([`backend/app/models/document.py`](file:///e:/GEN%20AI/backend/app/models/document.py)) (5 records verified)
  - `document_metadata`: Document file properties and attributes ([`backend/app/models/document_metadata.py`](file:///e:/GEN%20AI/backend/app/models/document_metadata.py))
  - `document_chunks`: Extracted text chunks with page and section metadata ([`backend/app/models/document_chunk.py`](file:///e:/GEN%20AI/backend/app/models/document_chunk.py)) (17 records verified)
  - `chat_sessions`: Conversational threads ([`backend/app/models/chat.py`](file:///e:/GEN%20AI/backend/app/models/chat.py)) (3 records verified)
  - `chat_messages`: User queries and assistant responses ([`backend/app/models/chat.py`](file:///e:/GEN%20AI/backend/app/models/chat.py)) (6 records verified)
  - `feedback`: Thumbs up/down user feedback logs ([`backend/app/models/feedback.py`](file:///e:/GEN%20AI/backend/app/models/feedback.py))

## Document Pipeline
- **Upload Implementation**: Multipart file upload via `POST /api/documents/upload` handled by `DocumentService.save_uploaded_file`, checking file extensions (`.pdf`, `.docx`, `.txt`) and 20MB limit.
- **PDF Extraction**: `PDFLoader` ([`backend/app/services/document_processing/pdf_loader.py`](file:///e:/GEN%20AI/backend/app/services/document_processing/pdf_loader.py)) using `pypdf`, preserving 1-indexed page numbers.
- **DOCX Extraction**: `DocxLoader` ([`backend/app/services/document_processing/docx_loader.py`](file:///e:/GEN%20AI/backend/app/services/document_processing/docx_loader.py)) using `python-docx`, parsing heading styles, paragraphs, and tables.
- **TXT Extraction**: `TxtLoader` ([`backend/app/services/document_processing/txt_loader.py`](file:///e:/GEN%20AI/backend/app/services/document_processing/txt_loader.py)) with multi-encoding fallback (`utf-8`, `utf-8-sig`, `cp1252`, `latin-1`).
- **Text Cleaning**: `TextCleaner` ([`backend/app/services/document_processing/text_cleaner.py`](file:///e:/GEN%20AI/backend/app/services/document_processing/text_cleaner.py)) normalizing whitespace, null bytes, and bullet formatting while preserving policy definitions.
- **Chunking**: `DocumentChunker` ([`backend/app/services/document_processing/chunker.py`](file:///e:/GEN%20AI/backend/app/services/document_processing/chunker.py)) using `RecursiveCharacterTextSplitter` (chunk_size=500, chunk_overlap=100) with section preservation.

## Embeddings
- **Embedding Model**: `sentence-transformers/all-MiniLM-L6-v2` loaded through `EmbeddingService` ([`backend/app/rag/embeddings.py`](file:///e:/GEN%20AI/backend/app/rag/embeddings.py))
- **Vector Dimension**: 384 dimensions (float32)
- **Normalization**: $L_2$ normalization enforced on vectors (`normalize_embeddings=True` and `faiss.normalize_L2`), ensuring inner product equals cosine similarity.

## Vector Database
- **FAISS Index Type**: `faiss.IndexFlatIP(384)` (Exact cosine similarity retrieval)
- **Persistence Path**: `backend/vectorstore/index.faiss` (26 KB binary verified on disk)
- **Metadata Storage**: `backend/vectorstore/metadata.json` (17 chunk metadata mappings verified) and `index_info.json` (diagnostic summary).

## LLM
- **Ollama Endpoint**: `http://127.0.0.1:11434`
- **Configured Model**: `llama3.2:3b`
- **Existing Integration Status**: Operational. Tested with active local Ollama daemon; `ollama list` confirms `llama3.2:3b` (2.0 GB) is pulled and available. Handled via `OllamaClient` ([`backend/app/llm/ollama_client.py`](file:///e:/GEN%20AI/backend/app/llm/ollama_client.py)) and `LLMService` ([`backend/app/llm/service.py`](file:///e:/GEN%20AI/backend/app/llm/service.py)).

## RAG
- **Retrieval Implementation**: `RAGRetriever` ([`backend/app/rag/retriever.py`](file:///e:/GEN%20AI/backend/app/rag/retriever.py)) embedding queries and executing Top-K similarity search in FAISS.
- **Top-K**: Configurable (default `5`, clamped $1 \le k \le 10$).
- **Similarity Threshold**: `min_score = 0.35`. Chunks below threshold are filtered out.
- **Context Construction**: `ContextBuilder` ([`backend/app/rag/context_builder.py`](file:///e:/GEN%20AI/backend/app/rag/context_builder.py)) applies deduplication, context character bounding (6,000 chars), and assigns source identifiers (`[S1]`, `[S2]`, etc.).
- **Answer Generation**: `LLMService.generate_grounded_answer` wraps retrieved context in an XML untrusted data fence, queries Ollama, and passes raw output to `ResponseParser` to sanitize citations.

## Chat
- **Chat API**: `POST /api/chat` ([`backend/app/api/chat.py`](file:///e:/GEN%20AI/backend/app/api/chat.py))
- **Conversation Persistence**: Managed by `ChatService` ([`backend/app/services/chat_service.py`](file:///e:/GEN%20AI/backend/app/services/chat_service.py)) with `ChatSession` records.
- **Message Persistence**: User queries and assistant responses are persisted into `chat_messages` in PostgreSQL/SQLite.

## Evaluation
- **Benchmark Implementation**: Dedicated framework in [`backend/app/evaluation/`](file:///e:/GEN%20AI/backend/app/evaluation/) testing 35 benchmark questions across 10 challenge categories ([`backend/tests/data/evaluation_dataset.json`](file:///e:/GEN%20AI/backend/tests/data/evaluation_dataset.json)).
- **Metrics**: Top-K hit rate, precision@K, recall@K, factual answer correctness, citation validity, hallucination rate, and latency breakdown.
- **Real vs. Hardcoded Verification**: REAL. Results are dynamically computed by `EvaluationRunner` ([`backend/app/evaluation/runner.py`](file:///e:/GEN%20AI/backend/app/evaluation/runner.py)) and exported to `backend/evaluation_results/`. `POST /api/evaluation/run` re-executes the benchmark live.

---

## Problems Found

| Component | Current Status | Problem | Required Fix |
|:---|:---:|:---|:---|
| **Health API** (`GET /api/health`) | PARTIAL / MOCKED | Returns static `{"status":"healthy","service":"Enterprise Policy RAG"}` without actually probing database, FAISS, or Ollama. | Update `GET /api/health` to perform live checks on database, FAISS, and Ollama, returning status `healthy` or `degraded`. |
| **LLM Status API** (`GET /api/llm/status`) | PARTIAL | Missing required `endpoint` string and boolean `available` field; hardcodes `base_url: "local"`. | Enhance schema and service to include `provider: "ollama"`, `endpoint: http://127.0.0.1:11434`, `available: True/False`, and preserve `installed_models`. |
| **Knowledge Base Status** (`GET /api/knowledge-base/status`) | WORKING | Missing `index_type` and `dimension` alias; returns `status: "ready"` instead of allowing standard `active`. | Include `index_type: "IndexFlatIP"`, `dimension: 384`, and `status: "active"` while maintaining full backward-compatibility with UI. |
| **Backend Configuration** (`backend/config.py`) | PARTIAL | Config is located at `backend/app/config.py` rather than `backend/config.py`. Missing normalized alias names for `VECTOR_STORE_PATH`, `RELEVANCE_THRESHOLD`, and `TOP_K`. | Create `backend/config.py` export wrapper and ensure all environment variables (`DATABASE_URL`, `OLLAMA_BASE_URL`, `OLLAMA_MODEL`, `EMBEDDING_MODEL`, `VECTOR_STORE_PATH`, `CHUNK_SIZE=900`, `CHUNK_OVERLAP=120`, `TOP_K=5`, `RELEVANCE_THRESHOLD=0.35`) are centralized with specified defaults. |
| **Embedding Service** | PARTIAL | Lacks `embed_texts` plural alias; does not raise an explicit error when dimension is not 384; loads lazily on first query rather than at startup. | Add `embed_texts()` method, add explicit validation raising `ValueError` if dimension != 384, and ensure model loads during FastAPI startup lifecycle. |
| **Vector Service** | PARTIAL | Implementation named `FAISSVectorStore` under `rag/vector_store.py`. Lacks unified service interface under `services/vector_service.py` with standard methods: `initialize()`, `load()`, `save()`, `add_vectors()`, `search()`, `rebuild()`, `count()`, `clear()`. | Create `VectorService` in `backend/app/services/vector_service.py` implementing exact method signatures while wrapping existing FAISS storage without data loss. |
| **Service Architecture Organization** | PARTIAL | Services are distributed across `app/services/`, `app/rag/`, and `app/llm/`. Clean unified imports from `backend/app/services/` needed without duplicating logic. | Provide unified service wrappers/exports in `app/services/` for `embedding_service`, `vector_service`, `retrieval_service`, `ollama_service`, `rag_service`, and `chat_service`. |
| **Error Handling** | PARTIAL | Exception responses are generic HTTP 500s or standard FastAPI validation errors without standardized enterprise error codes. | Implement standardized error codes (`INVALID_FILE_TYPE`, `FILE_TOO_LARGE`, `DOCUMENT_EXTRACTION_FAILED`, `EMPTY_DOCUMENT`, `EMBEDDING_MODEL_ERROR`, `FAISS_ERROR`, `OLLAMA_UNAVAILABLE`, `OLLAMA_MODEL_NOT_FOUND`, `DATABASE_ERROR`, `NO_RELEVANT_CONTEXT`). |
