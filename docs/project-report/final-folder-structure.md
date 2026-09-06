# Final Project Folder Structure Report

**Project Title:** Local Enterprise Policy Assistant Using Retrieval-Augmented Generation  
**Phase:** Phase 11 — Final Project Verification & Report Evidence  
**Status:** Verified & Production-Ready  

---

## 1. Directory Tree Overview

```text
e:/GEN AI/
├── .gitignore                          # Repository exclusion rules
├── docker-compose.yml                  # Container orchestration specification
├── README.md                           # Comprehensive documentation & setup guide
│
├── backend/                            # FastAPI backend application
│   ├── .env                            # Active environment configuration
│   ├── .env.example                    # Environment template with zero credentials
│   ├── alembic.ini                     # Alembic database migration configuration
│   ├── requirements.txt                # Python backend dependencies
│   ├── alembic/                        # Database migration scripts
│   │   ├── env.py
│   │   ├── script.py.mako
│   │   └── versions/
│   ├── app/                            # Application source code
│   │   ├── __init__.py
│   │   ├── config.py                   # Centralized configuration & environment loader
│   │   ├── main.py                     # FastAPI application entrypoint & middleware
│   │   ├── api/                        # API route controllers
│   │   │   ├── __init__.py
│   │   │   ├── auth.py                 # Authentication (JWT login, register, me)
│   │   │   ├── chat.py                 # RAG chat & message history
│   │   │   ├── documents.py            # Document upload, extraction, chunking
│   │   │   ├── evaluation.py           # Evaluation metrics & regression API
│   │   │   ├── knowledge_base.py       # Knowledge base status, build, validation
│   │   │   ├── rag.py                  # Direct vector retrieval endpoints
│   │   │   └── system.py               # Health checks & system diagnostic status
│   │   ├── database/                   # Database connection and session management
│   │   │   ├── __init__.py
│   │   │   ├── base.py                 # SQLAlchemy declarative base
│   │   │   ├── connection.py           # Engine & connection pool configuration
│   │   │   └── session.py              # Session factory & dependency generator
│   │   ├── models/                     # SQLAlchemy relational schema models
│   │   │   ├── __init__.py
│   │   │   ├── chat.py                 # ChatSession, ChatMessage
│   │   │   ├── document.py             # Document
│   │   │   ├── document_chunk.py       # DocumentChunk
│   │   │   ├── document_metadata.py    # DocumentMetadata
│   │   │   ├── feedback.py             # ChatFeedback
│   │   │   └── user.py                 # User (auth & roles)
│   │   ├── schemas/                    # Pydantic validation schemas
│   │   │   ├── __init__.py
│   │   │   ├── auth.py
│   │   │   ├── chat.py
│   │   │   ├── document.py
│   │   │   ├── evaluation.py
│   │   │   ├── knowledge_base.py
│   │   │   ├── rag.py
│   │   │   └── system.py
│   │   ├── services/                   # Business logic services
│   │   │   ├── __init__.py
│   │   │   ├── auth_service.py         # Password hashing & JWT issuance
│   │   │   ├── document_service.py     # Document validation & storage
│   │   │   ├── parser_service.py       # PDF, DOCX, TXT loaders & cleaners
│   │   │   └── chunking_service.py     # Recursive token/character chunking
│   │   ├── rag/                        # RAG core engine
│   │   │   ├── __init__.py
│   │   │   ├── embeddings.py           # SentenceTransformers (all-MiniLM-L6-v2)
│   │   │   ├── vector_store.py         # FAISS IndexFlatIP / cosine similarity
│   │   │   ├── retriever.py            # Top-K retrieval & relevance filtering
│   │   │   ├── context_builder.py      # Context assembly & prompt grounding
│   │   │   ├── schemas.py              # Retrieval & citation schemas
│   │   │   └── service.py              # Orchestrated RAG service
│   │   ├── llm/                        # Local LLM integration (Ollama)
│   │   │   ├── __init__.py
│   │   │   ├── ollama_client.py        # HTTP client communicating with Ollama daemon
│   │   │   ├── prompt_builder.py       # Anti-hallucination & injection-resistant prompts
│   │   │   ├── response_parser.py      # Citation validator & grounding extractor
│   │   │   ├── schemas.py              # LLM request/response contracts
│   │   │   └── service.py              # Orchestrated LLM execution service
│   │   ├── evaluation/                 # Scientific evaluation & benchmarking
│   │   │   ├── __init__.py
│   │   │   ├── dataset.py              # 35 standard QA benchmark test cases
│   │   │   ├── retrieval_evaluator.py  # Precision@K, Recall@K, HitRate@K
│   │   │   ├── answer_evaluator.py     # Accuracy, Numerical, Date, Refusal checks
│   │   │   ├── hallucination_evaluator.py # Faithfulness & ungrounded fact detector
│   │   │   ├── performance.py          # Latency profiler (Avg, P50, P95)
│   │   │   ├── metrics.py              # Metric aggregation & JSON exporter
│   │   │   └── runner.py               # Automated evaluation test runner
│   │   └── utils/                      # Helper utilities
│   │       ├── __init__.py
│   │       ├── security.py             # Path traversal & sanitize helpers
│   │       └── logger.py               # Structured logging configuration
│   ├── documents/                      # Persistent storage for uploaded enterprise policies
│   ├── vectorstore/                    # Serialized FAISS indices (`index.faiss`, `metadata.json`)
│   ├── evaluation_results/             # Evaluation export artifacts & JSON reports
│   └── tests/                          # Automated Pytest suite (94 tests)
│       ├── __init__.py
│       ├── test_api.py                 # REST API endpoints
│       ├── test_database.py            # PostgreSQL / SQLAlchemy models
│       ├── test_document_processing.py # PDF/DOCX parsing & chunking
│       ├── test_evaluation.py          # Evaluation metrics & runner
│       ├── test_health.py              # Health check & CORS
│       ├── test_llm.py                 # Ollama client & prompt defenses
│       ├── test_rag.py                 # SentenceTransformers & FAISS index
│       ├── test_rag_e2e.py             # End-to-end question answering
│       ├── test_retrieval.py           # Top-K retrieval & relevance threshold
│       └── data/                       # Test fixture files
│
├── frontend/                           # React 18 + Vite modern single-page application
│   ├── .env                            # Frontend environment configuration
│   ├── .env.example                    # Frontend environment template
│   ├── package.json                    # Frontend dependencies & scripts
│   ├── vite.config.js                  # Vite bundler configuration
│   ├── index.html                      # HTML5 entrypoint
│   ├── dist/                           # Compiled production bundle
│   └── src/                            # React application source code
│       ├── main.jsx                    # React DOM root mounting
│       ├── App.jsx                     # Main shell & tab routing
│       ├── index.css                   # Modern CSS design system (Glassmorphism & animations)
│       ├── components/                 # Reusable UI components
│       │   ├── Layout.jsx              # Navigation header, status pill, sidebar
│       │   ├── Navbar.jsx              # Application navigation
│       │   ├── StatusBadge.jsx         # Connection & health status indicator
│       │   ├── ChatMessage.jsx         # User & assistant chat bubbles with source badges
│       │   ├── SourceViewerModal.jsx   # Interactive modal displaying supporting chunks
│       │   └── MetricCard.jsx          # Statistics & analytics visualization cards
│       ├── pages/                      # Application view pages
│       │   ├── Dashboard.jsx           # System summary, quick metrics, quick actions
│       │   ├── Documents.jsx           # Document upload dropzone & repository table
│       │   ├── Assistant.jsx           # Real-time enterprise QA chat interface
│       │   ├── ChatHistory.jsx         # Past conversation logs & feedback
│       │   ├── KnowledgeBase.jsx       # FAISS index inspector & vector rebuild triggers
│       │   ├── Evaluation.jsx          # Live scientific metrics, latency charts, test results
│       │   └── Settings.jsx            # RAG parameters, model selector, threshold controls
│       └── services/                   # Frontend API client layer
│           └── api.js                  # Centralized Axios/Fetch integration
│
├── data/                               # Sample enterprise policy documents
│   ├── Leave_Policy.pdf                # Benchmark policy document
│   ├── Code_of_Conduct.docx            # Enterprise conduct policy
│   ├── Remote_Work_Policy.txt          # Telecommuting guidelines
│   └── IT_Security_Policy.pdf          # Data protection & security policy
│
└── docs/                               # Project documentation & report evidence
    └── project-report/
        ├── final-folder-structure.md   # This document
        ├── final-metrics.md            # Verified scientific benchmark metrics
        ├── test-summary.md             # Complete test matrix (94 unit + E2E tests)
        ├── demo-script.md              # 5-10 minute presentation demonstration flow
        ├── viva-questions.md           # 30 technical defense questions & detailed answers
        ├── report-content.md           # Full 35-section formal academic/industry report
        └── screenshots/                # Screenshot checklist and capture guide
```

---

## 2. Structural Verification Findings

1. **Clean Separation of Concerns:** Frontend, backend, database models, vector retrieval, local LLM orchestration, evaluation, and documentation are strictly segregated.
2. **Zero Cloud Dependencies:** All indexing, embedding generation (`all-MiniLM-L6-v2`), vector similarity computations (FAISS), and LLM inference (Ollama) run entirely locally on premise.
3. **Reproducibility:** Environment variables are properly abstracted in `.env.example` templates without hardcoded secrets or credentials.
