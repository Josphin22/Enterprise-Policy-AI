# Enterprise Policy AI — Administrator Guide

This guide covers administrative procedures, security configurations, document management, user role management, system diagnostics, and audit log analysis.

---

## 1. Accessing the Admin Portal

1. Navigate to the **Admin Portal** tab in the sidebar.
2. If not logged in as an administrator, enter your enterprise admin credentials:
   - **Default Email**: `admin@enterprise.com`
   - **Default Password**: `Admin@Enterprise2026!`
3. Once authenticated, the **ADMIN** badge activates, unlocking all operational tabs.

---

## 2. Managing Policy Documents

1. Go to the **Documents** page.
2. **Uploading Documents**: Drag and drop or browse to upload `.pdf`, `.docx`, or `.txt` policy files.
3. **Processing Documents**: Click the Play icon on newly uploaded files to run text extraction, normalization, and semantic chunking.
4. **Inspecting Chunks**: Click the Chunks badge on any processed document to view individual chunk text, token counts, and section tags.
5. **Document Previews**: Click the Eye icon to view the parsed document structure (pages, tables, and sections).
6. **Deleting Documents**: Click the Trash icon to remove a document. Chunks and FAISS vectors are purged automatically.

---

## 3. Knowledge Base Maintenance & Index Rebuilds

1. Go to the **Knowledge Base** page.
2. Review the status card displaying total indexed documents, chunks, vectors, and the timestamp of the last index build.
3. To rebuild the index after adding or modifying documents, click **Rebuild Knowledge Base**.
4. The system will atomically re-embed all processed chunks in PostgreSQL via SentenceTransformers and serialize the new `index.faiss` and `metadata.json` stores to disk.

---

## 4. User Role Management (RBAC)

1. Open **Admin Portal** > **User Management**.
2. Search users by email or filter by role (`ADMIN`, `MANAGER`, `USER`).
3. **Changing Roles**: Click the role pill next to any user to promote or demote permissions.
4. **Account Status**: Click the active/inactive toggle to immediately enable or disable an account without deleting data.

---

## 5. System Health Diagnostics & Monitoring

1. Open **Admin Portal** > **System Health**.
2. Review real-time status cards:
   - **FastAPI Core**: Microservice latency and route availability.
   - **PostgreSQL Database**: Connection pool status and table counts.
   - **FAISS Vector Engine**: Dimension verification (384d) and disk persistence.
   - **Ollama LLM Engine**: Daemon availability and loaded model identifier (`llama3.2:3b`).

---

## 6. Audit Logging & Compliance

1. Open **Admin Portal** > **Audit Logs**.
2. Filter logs by event category: `USER_LOGIN`, `DOCUMENT_UPLOAD`, `DOCUMENT_PROCESS`, `INDEX_REBUILD`, `CHAT_QUERY`.
3. Audit records capture timestamp, requesting user, IP address, action type, target resource, and detailed event metadata.
