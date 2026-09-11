# Enterprise Policy AI — Production Deployment & Infrastructure Guide

Comprehensive guide for deploying, operating, persisting, backing up, and restoring the Enterprise Policy AI RAG platform across production environments.

---

## 1. Architecture Overview

```
[ User Browser / Client ]
            │  (Port 80 / 443)
            ▼
┌────────────────────────────────────────────────────────┐
│  Nginx Reverse Proxy & Static Asset Server (Frontend) │
│  - Serves compiled React / Vite static bundle          │
│  - SPA fallback routing (try_files $uri /index.html)   │
│  - Gzip compression & security headers                 │
│  - Proxies /api/* to Backend ASGI service              │
└───────────────────────────┬────────────────────────────┘
                            │
              (Internal Network Port 8000)
                            ▼
┌────────────────────────────────────────────────────────┐
│  FastAPI Production ASGI Backend (Uvicorn 2 Workers)   │
│  - Non-root user (appuser:10000)                       │
│  - Guardrails & Hallucination Diagnostics              │
│  - RBAC & JWT Authentication                           │
│  - Sentence Transformers Embeddings (all-MiniLM-L6-v2) │
└───────┬───────────────────┬───────────────────┬────────┘
        │                   │                   │
        ▼                   ▼                   ▼
┌────────────────┐ ┌────────────────┐ ┌────────────────────────┐
│ PostgreSQL 16  │ │ FAISS Vector   │ │ Ollama LLM Service     │
│ Database       │ │ Index Store    │ │ (Host or Container)    │
│ (User, Doc,    │ │ (384-dim L2/IP │ │ llama3.2:3b / llama3   │
│ Audit metadata)│ │ persistent)    │ │ Port 11434             │
└────────────────┘ └────────────────┘ └────────────────────────┘
```

---

## 2. Prerequisites

1. **Docker Engine**: Version 24.0+
2. **Docker Compose**: Version 2.20+ (with `docker compose` V2 syntax)
3. **Hardware Recommendations**:
   - CPU: 4+ cores
   - RAM: 8 GB minimum (16 GB recommended when running local LLMs)
   - Disk: 20 GB+ SSD storage for documents and vector embeddings
4. **Ollama**:
   - Installed locally on the host machine (`ollama serve`), or
   - Run via Docker Compose profile (`--profile with-ollama`)

---

## 3. Environment Configuration

1. Copy the production environment example template:
   ```bash
   cp .env.example .env
   ```

2. Configure core production parameters in `.env`:
   - `JWT_SECRET`: Generate a strong, unique 64-character random string:
     ```bash
     openssl rand -hex 32
     ```
   - `POSTGRES_PASSWORD`: Set a strong database password.
   - `ADMIN_PASSWORD`: Configure the default seeded administrator password.
   - `OLLAMA_BASE_URL`:
     - **Windows / macOS Host**: `http://host.docker.internal:11434`
     - **Linux Host (Default Bridge)**: `http://172.17.0.1:11434` or use host gateway
     - **Containerized Ollama**: `http://ollama:11434`

---

## 4. Production Deployment Commands

### Option A: Standard Deployment (Backend + Frontend + Postgres + Host Ollama)
This is the recommended setup for low overhead and maximum inference performance on host hardware.

1. Ensure Ollama is running and the model is pulled on the host:
   ```bash
   ollama pull llama3.2:3b
   ollama serve
   ```

2. Build and start all services in detached mode:
   ```bash
   docker compose up -d --build
   ```

3. Check service container statuses and healthchecks:
   ```bash
   docker compose ps
   ```

4. Stream application logs:
   ```bash
   docker compose logs -f backend
   ```

### Option B: All-in-One Deployment (with Containerized Ollama)
Use this option if you want Ollama isolated in a container alongside other services:

```bash
docker compose --profile with-ollama up -d --build
```

Pull model into container:
```bash
docker compose exec ollama ollama pull llama3.2:3b
```

---

## 5. Persistent Storage & Volumes

All mutable data is mounted to persistent volumes to guarantee zero data loss upon container restart or upgrade:

| Volume Name | Target Path | Contents |
| :--- | :--- | :--- |
| `postgres_data` | `/var/lib/postgresql/data` | PostgreSQL database files, users, chats, audit logs |
| `document_storage` | `/app/documents` | Uploaded enterprise policies (PDF, DOCX, TXT) |
| `vector_storage` | `/app/vectorstore` | FAISS vector index files (`index.faiss`) and metadata (`index.pkl`) |
| `ollama_models` | `/root/.ollama` | Local LLM model weights (when using containerized Ollama) |

---

## 6. Health Checks & Verification

The system includes automated Docker health checks and live diagnostic endpoints:

### Automated Endpoint Testing
```bash
# 1. Full System Health Probe (checks Postgres, FAISS, and Ollama)
curl -s http://localhost/api/health | jq .

# Expected Healthy Output:
# {
#   "status": "healthy",
#   "database": "connected",
#   "faiss": "ready",
#   "ollama": "available",
#   "service": "Enterprise Policy RAG"
# }

# 2. Ollama Diagnostic Probe
curl -s http://localhost/api/health/ollama | jq .

# 3. System Subsystems Diagnostic (Admin token required)
curl -s -H "Authorization: Bearer <ADMIN_TOKEN>" http://localhost/api/admin/system-health | jq .
```

---

## 7. Database Migrations & Safe Schema Management

The backend container utilizes an entrypoint script (`backend/entrypoint.sh`) that safely checks and initializes table schemas without destructive drops:

1. **Automatic Initialization**:
   - Tables are created with `Base.metadata.create_all(bind=engine)`.
   - Existing tables, constraints, and stored records are never dropped or deleted.

2. **Manual Alembic Migrations** (if custom schema revisions are applied):
   ```bash
   # Run migrations in running backend container
   docker compose exec backend alembic upgrade head
   ```

---

## 8. Backup Strategy

To ensure business continuity, back up the three stateful components: PostgreSQL, Uploaded Documents, and the FAISS Vector Store.

### 1. PostgreSQL Database Backup
```bash
# Create timestamped database dump
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
docker compose exec -T postgres pg_dump -U postgres enterprise_rag > ./backups/postgres_backup_${TIMESTAMP}.sql
```

### 2. Document Storage Backup
```bash
# Archive documents volume
docker run --rm \
  -v enterprise_rag_document_storage:/source:ro \
  -v $(pwd)/backups:/backup \
  alpine tar -czvf /backup/documents_backup_${TIMESTAMP}.tar.gz -C /source .
```

### 3. FAISS Vector Store Backup
```bash
# Archive vector index volume
docker run --rm \
  -v enterprise_rag_vector_storage:/source:ro \
  -v $(pwd)/backups:/backup \
  alpine tar -czvf /backup/vectorstore_backup_${TIMESTAMP}.tar.gz -C /source .
```

---

## 9. Disaster Recovery & Restoration

To restore the system from backups on a fresh machine:

### 1. Restore PostgreSQL
```bash
# 1. Start postgres service only
docker compose up -d postgres

# 2. Restore database schema and data
cat ./backups/postgres_backup_20260910.sql | docker compose exec -T postgres psql -U postgres -d enterprise_rag
```

### 2. Restore Documents
```bash
docker run --rm \
  -v enterprise_rag_document_storage:/target \
  -v $(pwd)/backups:/backup \
  alpine tar -xzvf /backup/documents_backup_20260910.tar.gz -C /target
```

### 3. Restore FAISS Vector Index
```bash
docker run --rm \
  -v enterprise_rag_vector_storage:/target \
  -v $(pwd)/backups:/backup \
  alpine tar -xzvf /backup/vectorstore_backup_20260910.tar.gz -C /target
```

### 4. Start Full Application
```bash
docker compose up -d
```

---

## 10. Production Security & Logging Guidelines

1. **Zero Secrets in Git**: `.env` and `.db` files are strictly excluded via root and child `.gitignore`.
2. **Non-Root Execution**: Backend runs under unprivileged system user `appuser` (UID 10000).
3. **Sensitive Data Scrubbing**:
   - `ENABLE_SENSITIVE_DATA_SCRUB=true` scrubs connection strings, database passwords, JWT tokens, AWS keys, and private keys from LLM generation.
   - Logs never print authentication secrets, hashed passwords, or raw document content.
4. **CORS & Nginx Protection**:
   - Nginx enforces `X-Frame-Options`, `X-Content-Type-Options: nosniff`, and `X-XSS-Protection`.
   - Backend restricts allowed origins to configured domains in `CORS_ORIGINS`.

---

## 11. Known Deployment Limitations

1. **CPU vs. GPU Inference**:
   - When running Ollama on CPU inside a container, response generation times may range between 2 to 8 seconds depending on processor specs.
   - For high concurrency, host Ollama with NVIDIA GPU passthrough (`--gpus all`) is strongly recommended.
2. **FAISS In-Memory Search**:
   - The FAISS index is loaded into RAM upon startup. Ensure sufficient memory allocation (at least 2 GB free RAM for the backend container when processing 50k+ chunks).
3. **Single-Node Vector Store**:
   - For multi-node distributed scaling beyond 1 million documents, migrate from local FAISS to Milvus, Qdrant, or pgvector.
