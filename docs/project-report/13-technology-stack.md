# 11. Detailed Technology Stack

The following table itemizes the exact software packages, frameworks, and model weights implemented and verified in the project:

| Technology Layer | Component / Package | Exact Version | Architectural Purpose & Role in System |
| :--- | :--- | :--- | :--- |
| **Backend Runtime** | Python | 3.14.6 | Core execution environment for API, data processing, and AI workflows |
| **Frontend Runtime** | Node.js / npm | v22.20 / 10.9 | Runtime and package management for modern web client |
| **Frontend Framework** | React | 18.x | Declarative component-based user interface and reactive state management |
| **Frontend Bundler** | Vite | 8.2.2 | High-speed frontend development server and optimized ES module bundler |
| **Web API Gateway** | FastAPI | 0.141.1 | High-performance asynchronous REST API framework with OpenAPI generation |
| **ASGI Web Server** | Uvicorn | 0.52.4 | Production ASGI web server running asynchronous request event loops |
| **Relational ORM** | SQLAlchemy | 2.0.52 | Type-safe SQL Object-Relational Mapping, query compilation, and pooling |
| **Relational Database** | PostgreSQL / SQLite | 16.x / 3.x | Relational store for users, documents, chunks, chat logs, and feedback |
| **DB Migrations** | Alembic | 1.13.x | Schema migration tracking and automated database version management |
| **Embedding Engine** | SentenceTransformers | 6.0.1 | Framework for computing dense semantic vector embeddings on CPU/GPU |
| **Embedding Model** | all-MiniLM-L6-v2 | Hub Pretrained | 384-dimensional dense transformer model mapping text to unit hypersphere |
| **Vector Index** | FAISS (`faiss-cpu`) | 1.15.0 | Sub-millisecond exact inner-product nearest-neighbor search (`IndexFlatIP`) |
| **Local LLM Daemon** | Ollama | Latest Native | On-premise runtime hosting quantized GGUF foundation models |
| **Local LLM Model** | llama3.2:3b | 3B 4-bit | Lightweight instruction-tuned local LLM for context-grounded answer generation |
| **Document Loaders** | PyPDF & python-docx | 6.16 & 1.2.0 | Multi-format binary file parsers extracting text from PDF and Word files |
| **Auth & Security** | PyJWT & Bcrypt | 2.13 & 5.0.0 | Cryptographic JSON Web Token signing and salted password hashing |
| **Automated Testing** | Pytest | 9.1.1 | Comprehensive unit, integration, and RAG benchmark regression suite |
| **Containerization** | Docker / Compose | v2.x spec | Container orchestration defining isolated services and network bridges |
