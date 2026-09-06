# 12. Detailed System Module Descriptions

The application architecture is decomposed into 14 cohesive, specialized modules:

---

### MODULE 1 — Authentication & Access Control (`app.api.auth`, `app.services.auth_service`)
- **Purpose:** Secure identity verification, token issuance, and role enforcement (`USER` vs `ADMIN`).
- **Input:** User credentials (username, plaintext password) or Bearer JWT token.
- **Processing:** Password verification against salted bcrypt hashes; JWT generation with HS256 algorithm; token expiration validation.
- **Output:** Encrypted access token, user profile object, or HTTP 401 Unauthorized exception.

---

### MODULE 2 — Document Management (`app.api.documents`, `app.services.document_service`)
- **Purpose:** Handling document upload lifecycle, file storage, metadata tracking, and repository queries.
- **Input:** Multipart file upload streams, document query parameters, document deletion IDs.
- **Processing:** File size checking ($\le 20\text{ MB}$), MIME type validation, file hashing, filesystem persistence in `backend/documents/`, database record insertion.
- **Output:** Document metadata entity, repository lists, deletion status.

---

### MODULE 3 — Document Processing & Parsing (`app.services.parser_service`)
- **Purpose:** Extracting clean text and structural markers from multi-format enterprise files.
- **Input:** Binary file paths for PDF, DOCX, and TXT files.
- **Processing:** PyPDF page-by-page extraction; python-docx paragraph/table parsing; UTF-8 text decoding; control character filtering and whitespace normalization.
- **Output:** Structured document text with associated page and section metadata.

---

### MODULE 4 — Text Chunking (`app.services.chunking_service`)
- **Purpose:** Segmenting lengthy extracted text into overlapping, semantically coherent passages.
- **Input:** Normalized raw text, target chunk size ($500$ chars), overlap size ($100$ chars).
- **Processing:** Recursive token/character boundary splitting; preservation of policy section numbering and bullet points; duplicate chunk suppression.
- **Output:** Sequence of `DocumentChunk` entities with sequential chunk indices and page mappings.

---

### MODULE 5 — Embedding Generation (`app.rag.embeddings`)
- **Purpose:** Converting textual chunks and search queries into high-dimensional dense vectors.
- **Input:** Batch of cleaned text strings.
- **Processing:** SentenceTransformers forward pass through `all-MiniLM-L6-v2`; $L_2$ vector normalization ($\|\mathbf{v}\|_2 = 1.0$).
- **Output:** 384-dimensional floating-point NumPy embedding matrices.

---

### MODULE 6 — Vector Storage & Indexing (`app.rag.vector_store`)
- **Purpose:** Storing, persisting, and querying dense embedding vectors.
- **Input:** Normalized embedding vectors, chunk metadata dictionaries.
- **Processing:** Insertion into FAISS `IndexFlatIP`; disk serialization (`index.faiss` and `metadata.json`); vector-to-chunk index mapping.
- **Output:** Serialized FAISS index files; nearest-neighbor search result sets.

---

### MODULE 7 — Semantic Retrieval (`app.rag.retriever`)
- **Purpose:** Finding the most relevant document chunks for a given user question.
- **Input:** User query string, search parameter $K=5$, relevance threshold $s \ge 0.35$.
- **Processing:** Query embedding generation; FAISS vector search; cosine similarity scoring; pruning candidate chunks below the relevance threshold.
- **Output:** Ranked list of qualified `RetrievedChunk` objects with similarity scores.

---

### MODULE 8 — RAG Context Construction (`app.rag.context_builder`)
- **Purpose:** Assembling retrieved chunks into a bounded, deduplicated context block for LLM prompting.
- **Input:** List of retrieved chunks, maximum character ceiling ($6000$ chars), maximum chunk limit ($5$).
- **Processing:** Content deduplication; adjacent chunk boundary expansion; source identifier assignment (`[S1]`, `[S2]`).
- **Output:** Formatted context string and structured `SourceCitation` metadata list.

---

### MODULE 9 — Local LLM Generation (`app.llm.service`, `app.llm.ollama_client`)
- **Purpose:** Executing local foundation model inference to synthesize answers from context.
- **Input:** Assembled context block, user query, temperature ($0.1$), target model (`llama3.2:3b`).
- **Processing:** Prompt template assembly with strict anti-injection delimiters; HTTP REST call to local Ollama daemon; timeout management ($120\text{s}$).
- **Output:** Raw natural-language generated answer text.

---

### MODULE 10 — Source Citation & Response Parsing (`app.llm.response_parser`)
- **Purpose:** Validating that all citations in the generated answer map to actual retrieved context chunks.
- **Input:** Raw LLM answer text, retrieved source citations.
- **Processing:** Regex citation parsing; removal of fabricated source markers; grounding verification.
- **Output:** Sanitized answer text paired with verified interactive source citations.

---

### MODULE 11 — Chat & Session Management (`app.api.chat`, `app.models.chat`)
- **Purpose:** Managing multi-turn conversation sessions, persisting message logs, and capturing user ratings.
- **Input:** Chat messages, session IDs, user feedback ratings (thumbs up/down).
- **Processing:** Relational persistence of queries, answers, latency metrics, and feedback into PostgreSQL.
- **Output:** Message response payloads, historical session transcripts.

---

### MODULE 12 — Scientific Evaluation Engine (`app.evaluation.runner`, `app.evaluation.metrics`)
- **Purpose:** Automated benchmarking of retrieval quality, answer accuracy, and latency.
- **Input:** Curated 35-question evaluation dataset (`dataset.py`).
- **Processing:** Automated batch execution of retrieval and generation; calculation of Top-K hit rates, Precision@K, Recall@K, faithfulness, and P95 latency.
- **Output:** Summary evaluation metrics exported to JSON and CSV artifacts.

---

### MODULE 13 — System Administration (`app.api.knowledge_base`, `app.api.documents`)
- **Purpose:** Administrative maintenance of knowledge base state and vector indices.
- **Input:** Admin rebuild triggers, document deletion requests.
- **Processing:** Index re-synchronization; orphan chunk garbage collection; vector count validation.
- **Output:** Knowledge base status reports and operation confirmation payloads.

---

### MODULE 14 — System Health Monitoring (`app.api.system`)
- **Purpose:** Diagnostic health probing of all backend sub-services.
- **Input:** Health probe HTTP GET requests.
- **Processing:** PostgreSQL connection ping; FAISS index read probe; Ollama `/api/tags` connection test.
- **Output:** Structured JSON health status with overall status (`healthy`, `degraded`, `unavailable`) and component latencies.
