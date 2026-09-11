# Enterprise Policy AI — REST API Reference

Comprehensive reference for core REST endpoints exposed by the Enterprise Policy AI FastAPI service.

---

## 1. Authentication Endpoints

### `POST /api/auth/register`
Create a new user account with default `USER` role.
- **Request Body**: `{"email": "user@example.com", "username": "johndoe", "password": "SecurePassword123!"}`
- **Response**: `201 Created`
  ```json
  {
    "access_token": "eyJhbGciOi...",
    "token_type": "bearer",
    "user": {
      "id": "usr-123",
      "email": "user@example.com",
      "username": "johndoe",
      "role": "USER"
    }
  }
  ```

### `POST /api/auth/login`
Authenticate an existing user and obtain a JWT bearer token.
- **Request Body**: `{"email": "admin@enterprise.com", "password": "Admin@Enterprise2026!"}`
- **Response**: `200 OK` with `access_token` and user profile.

---

## 2. Document Ingestion Endpoints

### `GET /api/documents`
List all uploaded documents with status, chunk counts, and file sizes.
- **Response**: `200 OK`
  ```json
  {
    "total": 3,
    "documents": [
      {
        "id": "doc-uuid",
        "filename": "Leave_Policy.pdf",
        "file_type": "pdf",
        "size": 154200,
        "status": "processed",
        "chunk_count": 18,
        "uploaded_at": "2026-09-10T12:00:00Z"
      }
    ]
  }
  ```

### `POST /api/documents/upload`
Upload a new policy document (`multipart/form-data`).
- **Form Data**: `file` (`.pdf`, `.docx`, or `.txt`)
- **Response**: `201 Created`

### `POST /api/documents/{id}/process`
Extract and semantically chunk the specified document.
- **Response**: `200 OK` with extracted chunk count.

### `GET /api/documents/{id}/preview`
Inspect extracted document content (pages, sections, and structured tables).

### `DELETE /api/documents/{id}`
Delete a document and cascade deletion of all associated chunks and embeddings.

---

## 3. Knowledge Base & Vector Index Endpoints

### `GET /api/knowledge-base/status`
Inspect FAISS vector database status, vector counts, model dimensions, and last build timestamp.
- **Response**: `200 OK`
  ```json
  {
    "status": "ready",
    "documents": 3,
    "processed_documents": 3,
    "chunks": 42,
    "vectors": 42,
    "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
    "embedding_dimension": 384,
    "vector_database": "FAISS",
    "last_built": "2026-09-10T12:30:00Z"
  }
  ```

### `POST /api/knowledge-base/rebuild`
Re-embed all processed document chunks and reconstruct the FAISS vector index atomically.

### `POST /api/knowledge-base/search`
Perform semantic similarity search against indexed document chunks.
- **Request Body**: `{"query": "How many vacation days?", "top_k": 5, "min_score": 0.35}`

---

## 4. Chat & RAG Endpoints

### `POST /api/chat`
Execute grounded RAG inference using the local Ollama LLM.
- **Request Body**:
  ```json
  {
    "message": "What is the paid sick leave entitlement?",
    "conversation_id": "conv-uuid-optional",
    "top_k": 5,
    "document_id": null
  }
  ```
- **Response**: `200 OK`
  ```json
  {
    "success": true,
    "status": "success",
    "answer": "Full-time employees receive 10 days of paid sick leave annually [S1].",
    "conversation_id": "conv-uuid",
    "sources": [
      {
        "source_id": "S1",
        "document": "Leave_Policy.pdf",
        "page": 2,
        "section": "Sick Leave",
        "score": 0.88,
        "snippet": "Full-time employees receive 10 days of paid sick leave annually..."
      }
    ],
    "retrieval_duration_ms": 32.5,
    "llm_duration_ms": 845.2,
    "total_duration_ms": 877.7
  }
  ```

### `POST /api/chat/messages/{messageId}/feedback`
Submit user feedback rating (`positive` or `negative`) on an assistant response.

---

## 5. Enterprise Admin Endpoints

### `GET /api/admin/dashboard`
Aggregated executive overview of users, documents, vectors, and query volume (ADMIN only).

### `GET /api/admin/users`
List enterprise users with role filtering and pagination.

### `PATCH /api/admin/users/{userId}/role`
Update user role between `USER`, `MANAGER`, and `ADMIN`.

### `GET /api/admin/audit-logs`
Query immutable audit trail logs for security and compliance monitoring.

### `GET /api/admin/system-health`
Comprehensive diagnostic checks for FastAPI, PostgreSQL, FAISS, and Ollama.
