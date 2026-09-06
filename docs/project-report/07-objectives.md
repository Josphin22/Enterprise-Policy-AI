# 5. Project Objectives

## 5.1 Primary Objective
"To develop a privacy-preserving local Generative AI assistant capable of answering enterprise document queries accurately by combining semantic vector retrieval with a lightweight local Large Language Model."

## 5.2 Specific Objectives
1. **Document Upload & Storage:** Support secure drag-and-drop uploading of multi-format enterprise policies (PDF, DOCX, TXT) with automatic format validation and storage isolation.
2. **Text Extraction & Cleaning:** Extract clean text from unstructured documents, stripping non-printable artifacts while preserving section headers, numbers, and bullet points.
3. **Semantic Chunking:** Partition long documents into semantically coherent overlapping chunks ($500$ chars with $100$ char overlap) and persist them in PostgreSQL with relational metadata.
4. **Dense Vector Embeddings:** Compute 384-dimensional dense semantic vectors using `sentence-transformers/all-MiniLM-L6-v2` with $L_2$ unit normalization.
5. **High-Performance Vector Indexing:** Store and index chunk vectors in FAISS (`IndexFlatIP`) supporting sub-10ms similarity queries.
6. **Top-K Semantic Retrieval:** Retrieve top candidate chunks based on cosine similarity and filter out irrelevant passages using a relevance score threshold ($s \ge 0.35$).
7. **Local Generative Synthesis:** Synthesize natural-language answers using a local, quantized LLM via Ollama (`llama3.2:3b`), eliminating all external network calls.
8. **Auditable Source Citations:** Attach interactive, chunk-level citations (document name, page number, chunk ID, text excerpt) to every answer.
9. **Anti-Hallucination & Refusal Guardrails:** Ensure out-of-domain, irrelevant, or malicious prompt injection queries are safely refused rather than hallucinating facts.
10. **Scientific Benchmarking:** Build an automated evaluation suite (`app.evaluation.runner`) to scientifically measure retrieval accuracy, answer accuracy, faithfulness, and latency.
11. **Modern Single-Page Interface:** Develop an intuitive, responsive React 18 frontend with interactive chat, real-time health badges, and an evaluation dashboard.
12. **Enterprise API Architecture:** Expose a secure, documented asynchronous FastAPI backend with strict Pydantic schema validation.
13. **Role-Based Access Control:** Implement JWT-based authentication and role-based permissions (`USER` vs `ADMIN`).
