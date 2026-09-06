# 26. Appendix

## Appendix A: Complete REST API Endpoint Inventory

| Endpoint Route | HTTP Method | Functionality | Auth / Role Required |
| :--- | :---: | :--- | :---: |
| `/api/auth/register` | `POST` | Register a new enterprise user | Public |
| `/api/auth/login` | `POST` | Authenticate user & issue signed JWT | Public |
| `/api/auth/me` | `GET` | Retrieve authenticated user profile | Bearer JWT |
| `/api/documents` | `GET` | List all ingested policy documents | Bearer JWT |
| `/api/documents/upload` | `POST` | Upload and validate PDF/DOCX/TXT file | ADMIN |
| `/api/documents/{id}` | `GET` | Get metadata & chunk count for document | Bearer JWT |
| `/api/documents/{id}` | `DELETE` | Delete document and purge vector index | ADMIN |
| `/api/documents/{id}/process` | `POST` | Manually trigger parsing & chunking | ADMIN |
| `/api/knowledge-base/status` | `GET` | Query FAISS index size, vectors, dimension | Bearer JWT |
| `/api/knowledge-base/build` | `POST` | Rebuild FAISS index from stored chunks | ADMIN |
| `/api/rag/retrieve` | `POST` | Direct vector search returning Top-K chunks | Bearer JWT |
| `/api/chat` | `POST` | End-to-end RAG chat query and answer | Bearer JWT |
| `/api/chat/history` | `GET` | Retrieve past conversation transcripts | Bearer JWT |
| `/api/chat/feedback` | `POST` | Submit thumbs up/down user rating | Bearer JWT |
| `/api/evaluation/summary` | `GET` | Query latest empirical evaluation metrics | ADMIN |
| `/api/evaluation/run` | `POST` | Trigger 35-question automated evaluation | ADMIN |
| `/api/system/health` | `GET` | System health probe (Postgres, FAISS, Ollama)| Public |

---

## Appendix B: Database Entity-Relationship Schema

```text
┌───────────────────┐       ┌──────────────────────┐       ┌─────────────────────┐
│       users       │       │      documents       │       │  document_metadata  │
├───────────────────┤       ├──────────────────────┤       ├─────────────────────┤
│ id (PK)           │◄──┐   │ id (PK)              │◄──┐   │ id (PK)             │
│ username (UNIQUE) │   │   │ filename             │   │   │ document_id (FK)────┼──┐
│ hashed_password   │   │   │ file_path            │   └───┤ title               │  │
│ role (USER/ADMIN) │   │   │ file_size_bytes      │       │ author / department │  │
│ created_at        │   │   │ status (PROCESSED)   │       │ page_count          │  │
└───────────────────┘   │   │ file_hash (MD5)      │       └─────────────────────┘  │
                        │   │ created_at           │                                │
                        │   └──────────┬───────────┘                                │
                        │              │ 1:N                                        │
                        │              ▼                                            │
                        │   ┌──────────────────────┐                                │
                        │   │   document_chunks    │                                │
                        │   ├──────────────────────┤                                │
                        │   │ id (PK)              │                                │
                        │   │ document_id (FK)─────┼────────────────────────────────┘
                        │   │ chunk_index          │
                        │   │ text_content         │
                        │   │ char_count           │
                        │   │ page_number          │
                        │   └──────────────────────┘
                        │
                        │ 1:N
                        ▼
┌───────────────────┐       ┌──────────────────────┐       ┌─────────────────────┐
│   chat_sessions   │       │    chat_messages     │       │    chat_feedback    │
├───────────────────┤       ├──────────────────────┤       ├─────────────────────┤
│ id (PK)           │◄──┐   │ id (PK)              │◄──┐   │ id (PK)             │
│ user_id (FK)      │   └───┤ session_id (FK)      │   └───┤ message_id (FK)     │
│ title             │       │ sender (USER/AI)     │       │ rating (+1 / -1)    │
│ created_at        │       │ message_text         │       │ comment             │
└───────────────────┘       │ citations (JSON)     │       │ created_at          │
                            │ latency_ms           │       └─────────────────────┘
                            │ created_at           │
                            └──────────────────────┘
```
