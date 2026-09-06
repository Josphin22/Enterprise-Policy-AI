# 8. System Requirements

## 8.1 Hardware Requirements

### Actual Hardware Used in Development & Testing:
- **Processor (CPU):** Intel / AMD 64-bit Multi-Core Processor (x86_64 architecture).
- **System Memory (RAM):** 16 GB DDR4/DDR5 RAM.
- **Persistent Storage:** Solid State Drive (SSD) with $\ge 10\text{ GB}$ available space.
- **Network Interface:** Local loopback interface (`localhost` / `127.0.0.1`).

### Recommended Hardware Specifications for Enterprise Production:
- **CPU:** 8+ Core modern CPU (e.g., AMD Ryzen 7 / Intel Core i7 or Xeon / EPYC).
- **RAM:** 32 GB RAM (accommodates concurrent vector indexing and in-memory LLM weights).
- **GPU (Optional for acceleration):** NVIDIA GPU with $\ge 8\text{ GB}$ VRAM (e.g., RTX 3060/4060 or T4/A10) for accelerated LLM generation.
- **Storage:** NVMe SSD for fast model loading and document parsing.

---

## 8.2 Software Requirements

### Actual Software Stack:
- **Operating System:** Windows 10/11 64-bit / Linux (Ubuntu 22.04+ LTS) / macOS.
- **Python Runtime:** Python 3.14.x (or Python 3.11/3.12).
- **Node.js Runtime:** Node.js v22.x / npm v10.x.
- **Web Framework:** FastAPI 0.141.1 + Uvicorn 0.52.4.
- **Database Engine:** PostgreSQL 16 (or SQLite for embedded lightweight tests) + SQLAlchemy 2.0.52.
- **Vector Database:** FAISS (`faiss-cpu` 1.15.0).
- **Embedding Framework:** SentenceTransformers 6.0.1 (`all-MiniLM-L6-v2`).
- **Local LLM Engine:** Ollama with `llama3.2:3b` quantized GGUF weights.
- **Frontend Framework:** React 18 with Vite 8.2.2.
- **Testing Framework:** Pytest 9.1.1.

---

## 8.3 Functional Requirements (FR)

- **FR1 — User Authentication:** Secure login via username and password with JWT token generation and bcrypt password hashing.
- **FR2 — Document Upload:** Multi-format file uploader accepting PDF, DOCX, and TXT files via drag-and-drop or file dialog.
- **FR3 — Document Validation:** Automated validation of file extensions, MIME types, and maximum file size limits ($\le 20\text{ MB}$).
- **FR4 — Document Processing:** Asynchronous extraction of clean text and structural metadata.
- **FR5 — Text Extraction:** Robust text extraction preserving paragraph structures and section headings.
- **FR6 — Chunk Generation:** Recursive semantic chunking using a 500-character window and a 100-character overlap.
- **FR7 — Embedding Generation:** Transformation of text chunks into 384-dimensional $L_2$-normalized dense vectors.
- **FR8 — FAISS Indexing:** Persistence of vectors and metadata in a local FAISS index (`IndexFlatIP`).
- **FR9 — Semantic Retrieval:** Nearest-neighbor cosine similarity search retrieving the Top-5 candidate chunks.
- **FR10 — RAG Answer Generation:** Synthesis of natural-language answers strictly conditioned on retrieved context.
- **FR11 — Source Citation:** Inline citations linking statements to specific document names, chunk IDs, and page numbers.
- **FR12 — Chat History:** Persistence and retrieval of conversation sessions and past messages in the database.
- **FR13 — Knowledge-Base Management:** Inspection of indexed document counts, chunk counts, vector dimensions, and manual index rebuilds.
- **FR14 — Evaluation:** Automated benchmarking suite for precision, recall, answer accuracy, and latency.
- **FR15 — System Health Monitoring:** Real-time health diagnostic probes for the API, database, vector store, and LLM daemon.
- **FR16 — Admin Management:** Privileged controls for document deletion, index rebuilding, and system configuration.

---

## 8.4 Non-Functional Requirements (NFR)

- **NFR1 — Security & Privacy:** 100% on-premise execution; zero telemetry or prompt transmission to third-party servers.
- **NFR2 — Performance & Latency:** Vector similarity search $< 20\text{ ms}$; P95 pipeline latency $< 100\text{ ms}$ for retrieval and context construction.
- **NFR3 — Scalability:** Decoupled service architecture allowing independent scaling of backend workers, database, and LLM instances.
- **NFR4 — Reliability & ACID Compliance:** Relational integrity enforced via PostgreSQL foreign keys and transactional session rollbacks.
- **NFR5 — Maintainability:** Modular codebase adhering to clean architecture principles with 94 passing automated unit and integration tests.
- **NFR6 — Usability:** Glassmorphic, responsive user interface with real-time status pills, active loading skeletons, and interactive citation modals.
