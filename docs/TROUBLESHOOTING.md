# Enterprise Policy AI — Troubleshooting Guide

Comprehensive guide for diagnosing and resolving common operational issues across the Enterprise Policy AI platform.

---

## 1. Local LLM Service (Ollama) Issues

### Symptom: *"Ollama daemon is offline"* or *"Unable to generate an answer"*
- **Diagnosis**: The local Ollama daemon is either stopped or listening on a different port.
- **Resolution**:
  1. Start the Ollama background service in a separate terminal:
     ```bash
     ollama serve
     ```
  2. Verify the daemon is responding:
     ```bash
     curl http://127.0.0.1:11434/api/tags
     ```
  3. Ensure the required model is pulled:
     ```bash
     ollama pull llama3.2:3b
     ```
  4. If running in Docker, verify `OLLAMA_BASE_URL=http://host.docker.internal:11434` in your `.env` file.

---

## 2. Vector Index (FAISS) Issues

### Symptom: *"Vector database not built"* or *"Zero vectors in knowledge base"*
- **Diagnosis**: Documents have been uploaded but have not been processed into chunks, or the FAISS index has not been built yet.
- **Resolution**:
  1. Go to the **Documents** tab and ensure all uploaded documents have `status: processed`. If pending, click the Play button to process them.
  2. Go to the **Knowledge Base** tab and click **Build Knowledge Base**.
  3. Wait for the notification confirming vectors are serialized to `backend/vectorstore/index.faiss`.

---

## 3. Database Connection Issues

### Symptom: *"Database connection check failed"*
- **Diagnosis**: PostgreSQL is stopped, credentials in `.env` are mismatched, or port 5432 is blocked.
- **Resolution**:
  1. Check PostgreSQL service status:
     ```bash
     # Docker:
     docker compose ps postgres
     # Local Windows:
     Get-Service -Name postgresql*
     ```
  2. Fallback Mode: Notice that the application automatically falls back to local SQLite (`enterprise_rag.db`) if PostgreSQL is temporarily unreachable.
  3. Verify `DATABASE_URL` format in `.env`:
     ```ini
     DATABASE_URL=postgresql://postgres:EnterpriseSecurePass2026!@localhost:5432/enterprise_rag
     ```

---

## 4. Frontend / Backend Connectivity

### Symptom: *"Cannot reach server at http://localhost:8000"*
- **Diagnosis**: The FastAPI backend is not running or CORS blocked the request.
- **Resolution**:
  1. Check that the backend is active:
     ```bash
     curl http://localhost:8000/api/health
     ```
  2. If running locally, launch the backend:
     ```bash
     cd backend
     python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
     ```
  3. Check that your frontend origin (e.g. `http://localhost:5173`) is listed under `CORS_ORIGINS` in `.env`.

---

## 5. Document Ingestion Failures

### Symptom: *"Document processing failed: unsupported file type"*
- **Diagnosis**: File extension is not `.pdf`, `.docx`, or `.txt`, or file exceeds size limits.
- **Resolution**:
  1. Verify the file extension is one of the supported types (`.pdf`, `.docx`, `.txt`).
  2. Ensure the file size is under the configured limit (`MAX_UPLOAD_SIZE_MB=25`).
  3. For scanned PDFs containing images without embedded text, ensure `ENABLE_OCR=true` is configured in `.env` and `tesseract` is installed on your system path.
