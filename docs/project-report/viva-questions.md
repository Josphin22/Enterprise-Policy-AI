# Viva Voce & Technical Defense Preparation (30 Questions & Answers)

**Project Title:** Local Enterprise Policy Assistant Using Retrieval-Augmented Generation  
**Domain:** Distributed Computing, Generative AI, Information Retrieval  

---

### 1. What is Retrieval-Augmented Generation (RAG)?
**Answer:** RAG is an architectural framework that enhances Large Language Models (LLMs) by retrieving relevant, authoritative information from an external private knowledge base before generating a response. Instead of relying solely on parametric weights, the LLM receives real-time context from authoritative enterprise documents.

### 2. Why did you use RAG instead of fine-tuning an LLM?
**Answer:**
1. **Dynamic Updates:** RAG allows instant addition, deletion, or modification of enterprise policy documents without costly and time-consuming model retraining.
2. **Zero Hallucination & Verifiability:** Every generated answer is paired with exact document chunk citations.
3. **Data Privacy & Cost:** Avoids expensive GPU fine-tuning cycles and maintains access control over proprietary enterprise documents.

### 3. Why did you choose FAISS for vector storage?
**Answer:** Facebook AI Similarity Search (FAISS) is an industry-standard, high-performance C++ library with Python bindings optimized for dense vector clustering and similarity search. It provides sub-millisecond similarity search (`IndexFlatIP` for cosine similarity) on standard CPU hardware without external vector database licensing fees.

### 4. Why SentenceTransformers?
**Answer:** SentenceTransformers provides pretrained transformer models optimized via Siamese networks for generating semantically meaningful dense sentence embeddings where cosine distance accurately reflects semantic similarity.

### 5. Why the `all-MiniLM-L6-v2` embedding model?
**Answer:** It provides an optimal balance between retrieval accuracy and latency. It outputs 384-dimensional dense vectors, has a lightweight footprint (~80 MB), and achieves fast CPU inference (7.23 ms retrieval latency) while matching the performance of much larger models on retrieval benchmarks.

### 6. Why did you choose Ollama?
**Answer:** Ollama is an open-source, lightweight runtime designed to run quantized GGUF Large Language Models locally on consumer hardware with native CPU/GPU acceleration, providing a clean REST API without transmitting enterprise data to third-party clouds.

### 7. Why is a local LLM critical for enterprise environments?
**Answer:** Strict compliance, privacy (GDPR, HIPAA), and proprietary trade secret protection forbid sending confidential internal policies to commercial cloud APIs. A local LLM guarantees zero external telemetry and zero data leakage.

### 8. What is a text embedding?
**Answer:** An embedding is a continuous mathematical representation of textual data as a high-dimensional vector in real space ($\mathbb{R}^d$, where $d=384$). Semantically similar phrases are located close to each other in vector space.

### 9. What is vector similarity?
**Answer:** Vector similarity measures how close two dense embedding vectors are in vector space. For normalized vectors, the cosine similarity equals the inner product: $\text{sim}(u, v) = \frac{u \cdot v}{\|u\|_2 \|v\|_2} = u \cdot v$, yielding a score between -1 and +1 (or 0 and 1 for positive embeddings).

### 10. What is chunking?
**Answer:** Chunking is the process of breaking long documents into discrete, semantically cohesive segments (e.g., 500 characters with 100 characters of overlap) before vector indexing.

### 11. Why is chunking necessary?
**Answer:**
1. **Embedding Context Limits:** Embedding models and LLMs have finite context window limits (e.g., 256–512 tokens for embeddings).
2. **Precision in Retrieval:** Smaller chunks allow pinpoint retrieval of specific clauses without diluting the semantic vector with irrelevant paragraphs.

### 12. What is hallucination in LLMs?
**Answer:** Hallucination occurs when an LLM produces syntactically fluent and confident statements that are factually false, ungrounded, or fabricated from outside the provided reference text.

### 13. How does your system reduce and eliminate hallucination?
**Answer:**
1. **Relevance Threshold Filtering:** If cosine similarity falls below $0.35$/$0.40$, the query is deemed unanswerable and refused immediately.
2. **Strict System Prompt Constraints:** The model is instructed: *"Answer ONLY based on the provided context. If the context does not contain the answer, state that information is insufficient."*
3. **Response Citation Validation:** The response parser cross-references generated claims with retrieved chunks. In our benchmark, the hallucination rate was 0.0%.

### 14. What happens if no relevant document is found?
**Answer:** The retriever flags insufficient context and returns a graceful refusal: *"I cannot find sufficient policy documentation to answer this question accurately."* No hallucinated policy is produced.

### 15. What is Top-K retrieval?
**Answer:** Top-K retrieval searches the vector index for the $K$ nearest neighbors (highest cosine similarity scores) to the query vector. We use $K=5$.

### 16. What is cosine similarity?
**Answer:** The cosine of the angle between two vectors:
$$\cos(\theta) = \frac{\mathbf{A} \cdot \mathbf{B}}{\|\mathbf{A}\|_2 \|\mathbf{B}\|_2}$$
If both vectors are unit-normalized ($L_2$ norm = 1.0), cosine similarity simplifies to the dot product $\mathbf{A} \cdot \mathbf{B}$, which FAISS computes using `IndexFlatIP`.

### 17. Why did you choose FastAPI for the backend?
**Answer:** FastAPI is an asynchronous, high-performance Python web framework based on Starlette and Pydantic. It provides automatic OpenAPI/Swagger documentation, strict type validation, asynchronous I/O concurrency, and fast response serialization.

### 18. Why PostgreSQL?
**Answer:** PostgreSQL is an enterprise-grade ACID-compliant relational database. It reliably manages structured metadata, document status, user credentials, conversation session histories, and audit logs with strong foreign key integrity.

### 19. What is the role of React in the frontend?
**Answer:** React 18 provides a component-driven, declarative user interface that re-renders state changes efficiently using the Virtual DOM, enabling real-time chat streaming, document upload progress, and dynamic evaluation visualizations.

### 20. How does the frontend communicate with the backend?
**Answer:** Over asynchronous HTTP/REST protocols using Axios/Fetch with JSON payloads. The frontend connects to `http://localhost:8000/api` with CORS headers configured.

### 21. How are documents processed in the pipeline?
**Answer:**
1. Upload & MIME validation $\to$ 2. Text extraction via PyPDF / python-docx $\to$ 3. Text cleaning & whitespace normalization $\to$ 4. Recursive overlapping chunking $\to$ 5. Storage of chunk metadata in PostgreSQL $\to$ 6. Dense vector embedding $\to$ 7. FAISS index serialization.

### 22. How are source citations verified and displayed?
**Answer:** Each retrieved chunk carries metadata (document name, chunk index, page number, and text snippet). The frontend renders interactive citation pills beneath each answer; clicking a pill opens a modal highlighting the exact supporting text from the document.

### 23. How is authentication implemented?
**Answer:** Using industry-standard JWT (JSON Web Tokens) with PBKDF2/bcrypt password hashing. Protected endpoints require a Bearer token in the `Authorization` header.

### 24. What is the role of FAISS in the RAG pipeline?
**Answer:** FAISS indexes the 384-dimensional document vectors into memory and performs nearest-neighbor vector searches in $O(N \cdot D)$ time (or sub-linear time with IVF indexing), delivering candidate chunks in ~7 ms.

### 25. What is the role of Ollama in the RAG pipeline?
**Answer:** Ollama loads and executes the quantized LLM weights (`llama3.2:3b`) on the local CPU/GPU, reading the assembled prompt and generating natural-language text based strictly on the retrieved context.

### 26. What are the limitations of the current implementation?
**Answer:**
1. Complex graphical tables and embedded scanned images require OCR extensions.
2. Cross-encoder re-ranking could further improve Precision@5 on massive datasets exceeding 100,000 pages.
3. Multi-turn chat memory is currently bounded to session context windows.

### 27. How did you evaluate the system scientifically?
**Answer:** We built an automated evaluation engine (`app.evaluation.runner`) running a curated 35-question dataset covering direct queries, paraphrased queries, multi-document queries, numerical questions, out-of-domain queries, and prompt injection attacks.

### 28. What is Retrieval Accuracy (Hit Rate and Precision@K)?
**Answer:**
- **Hit Rate@K:** The proportion of queries where at least one ground-truth relevant chunk is present in the top $K$ results (Achieved: 100.0% at $K=1, 3, 5$).
- **Precision@K:** The fraction of retrieved chunks in top $K$ that are truly relevant (Achieved: 67.27% at $K=5$).

### 29. What is Faithfulness in RAG?
**Answer:** Faithfulness measures whether every assertion in the generated answer can be directly inferred from the retrieved context. Our system achieved a 100.0% Faithfulness Rate.

### 30. How can the system be extended in future work?
**Answer:**
1. **Hybrid Search:** Combine BM25 keyword search with FAISS dense vector search (Reciprocal Rank Fusion).
2. **Multimodal RAG:** Integrate Vision-Language Models (e.g., LLaVA) for chart and table parsing.
3. **Distributed Clustering:** Deploy FAISS and LLM inference across a distributed Kubernetes cluster with load-balanced worker pools.
