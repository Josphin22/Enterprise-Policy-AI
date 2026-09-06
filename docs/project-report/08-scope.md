# 6. Scope of the Project

## 6.1 Current Operational Scope
- **Document Formats:** PDF (`.pdf`), Microsoft Word (`.docx`), and Plain Text (`.txt`).
- **Domain Coverage:** Human Resource manuals, employee handbooks, IT security standards, standard operating procedures, travel expense policies, and corporate codes of conduct.
- **Query Types Handled:** Direct policy inquiries, synonymous/paraphrased queries, multi-document combination queries, numerical fact inquiries, and adversarial/injection attempts.
- **Deployment Modality:** On-premise local server running FastAPI, PostgreSQL/SQLite, FAISS, and Ollama with local CPU/GPU execution.
- **Language Scope:** Primary focus on English enterprise documentation.

## 6.2 Future Enhancements Scope
- **Optical Character Recognition (OCR):** Integration of Tesseract or PaddleOCR to ingest scanned physical documents and image-based PDFs.
- **Multilingual Support:** Cross-lingual embeddings (e.g., `paraphrase-multilingual-MiniLM-L12-v2`) for global multi-language enterprise policy retrieval.
- **Hybrid Retrieval & Reranking:** Combining BM25 sparse lexical retrieval with FAISS dense vector retrieval via Reciprocal Rank Fusion (RRF) and Cross-Encoder re-ranking.
- **Distributed Enterprise Clustering:** Scaling vector indexing and LLM workers across distributed multi-node Kubernetes clusters with load balancing.
- **Enterprise SSO & Active Directory:** Integration with SAML 2.0, OAuth2, and LDAP / Azure Active Directory for single sign-on.
