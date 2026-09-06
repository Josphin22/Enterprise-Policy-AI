# Comprehensive Viva Voce Preparation & Technical Q&A

**Project Title:** LOCAL ENTERPRISE POLICY ASSISTANT USING RETRIEVAL-AUGMENTED GENERATION  
**Subject / Domain:** Distributed Computing, Generative AI, Natural Language Processing  

---

## Part 1: The 2-Minute Elevator Pitch / Project Explanation

> **"What is your project in 2 minutes?"**

*"Our project is the **Local Enterprise Policy Assistant**, a privacy-preserving Generative AI platform built using **Retrieval-Augmented Generation (RAG)** to answer enterprise policy and compliance questions.
<br><br>
**The Problem:** Organizations possess large volumes of complex policies in PDF, Word, and text formats. Employees spend hours searching them manually, while generic cloud AI chatbots like ChatGPT risk leaking confidential corporate trade secrets and frequently hallucinate non-existent rules.
<br><br>
**The Solution:** We built a 100% on-premise system with zero cloud dependencies. When enterprise documents are uploaded, our system cleans and splits them into 500-character overlapping chunks, converts them into 384-dimensional dense vectors using **SentenceTransformers (`all-MiniLM-L6-v2`)**, and indexes them in a **FAISS** vector database. 
<br><br>
**The Query Flow:** When an employee asks a natural-language question, the system retrieves the Top-5 most relevant chunks using cosine similarity in under 8 milliseconds. It filters out irrelevant chunks using a relevance score cutoff of 0.35. If context is insufficient, it safely refuses to answer; otherwise, it feeds the context into a local **Ollama LLM (`llama3.2:3b`)** running on the host machine.
<br><br>
**The Result:** The system generates a concise, grounded answer paired with interactive, clickable source citations displaying the exact document and page number. In our 35-question empirical benchmark, the system achieved a **100.0% Top-1 Retrieval Hit Rate**, **100.0% Faithfulness**, **0.0% Hallucination Rate**, and an average end-to-end retrieval latency of **7.23 ms**, fully verified across **94 automated Pytest tests**."*

---

## Part 2: The 30 Most Important Viva Questions & Answers

### 1. What is your project?
**Answer:** A local, privacy-preserving enterprise document question-answering assistant that uses Retrieval-Augmented Generation (RAG) to provide verified natural-language answers based strictly on internal corporate documentation.

### 2. What exact problem does it solve?
**Answer:** It eliminates the time employees waste manually searching large policy manuals, solves the lexical matching limitations of keyword search, eliminates cloud data privacy risks, and prevents AI hallucinations.

### 3. Why did you choose RAG over fine-tuning?
**Answer:** RAG allows immediate knowledge base updates (by simply adding/removing documents), provides direct chunk-level source citations for verification, prevents hallucinations via strict context bounds, and avoids costly GPU retraining cycles.

### 4. What is hallucination in LLMs?
**Answer:** Hallucination is when a generative language model produces syntactically fluent, confident statements that are factually false, ungrounded, or fabricated outside the provided reference text.

### 5. How does your project reduce and eliminate hallucination?
**Answer:**
1. Cosine relevance thresholding ($s \ge 0.35$) prunes irrelevant context;
2. Strict system prompt boundaries command the model to answer *only* from context and refuse otherwise;
3. Output citation parsing validates that all generated claims map to actual retrieved chunks (0.0% hallucination in our benchmark).

### 6. What is FAISS?
**Answer:** Facebook AI Similarity Search (FAISS) is an open-source, highly optimized C++ library with Python bindings for dense vector indexing and nearest-neighbor similarity search in metric space.

### 7. Why did you choose FAISS?
**Answer:** FAISS delivers sub-10ms nearest-neighbor search (`IndexFlatIP`) on standard CPU hardware, requires zero external database licensing, and serializes easily to local disk (`index.faiss` and `metadata.json`).

### 8. What are text embeddings?
**Answer:** Continuous numerical vector representations of text in high-dimensional space ($\mathbb{R}^{384}$). Semantically similar sentences map close to each other in vector space.

### 9. Why SentenceTransformers?
**Answer:** SentenceTransformers models use Siamese BERT architectures specifically tuned to produce semantically rich sentence-level embeddings where cosine similarity directly corresponds to semantic closeness.

### 10. Why `all-MiniLM-L6-v2`?
**Answer:** It outputs 384-dimensional dense vectors with a lightweight memory footprint (~80 MB), provides fast CPU embedding (~7.23 ms retrieval), and matches the retrieval accuracy of much larger 768d/1536d models.

### 11. What is Ollama?
**Answer:** An open-source, lightweight local LLM execution runtime that serves quantized GGUF foundation models over a local HTTP socket with zero external cloud dependencies.

### 12. Why use a local LLM instead of commercial cloud APIs (OpenAI/Anthropic)?
**Answer:** Enterprise regulatory compliance (GDPR, HIPAA, SOC 2) and corporate confidentiality forbid sending proprietary internal policies, salaries, and security guidelines to third-party cloud servers.

### 13. What is chunking and why is it necessary?
**Answer:** Chunking divides long documents into discrete, semantically cohesive passages (500 chars with 100 char overlap). It is necessary because embedding models have token length limits and smaller chunks enable pinpoint retrieval without diluting vector representations.

### 14. What is Top-K retrieval?
**Answer:** Searching the vector database to retrieve the top $K$ nearest neighbor chunks ranked by highest cosine similarity score. We use $K=5$.

### 15. What is cosine similarity?
**Answer:** The cosine of the angle between two vectors:
$$\cos(\theta) = \frac{\mathbf{A} \cdot \mathbf{B}}{\|\mathbf{A}\|_2 \|\mathbf{B}\|_2}$$
Because our vectors are $L_2$-normalized to unit length ($\|\mathbf{A}\|_2=1.0$), cosine similarity equals the simple inner product $\mathbf{A} \cdot \mathbf{B}$.

### 16. What happens when no relevant document is found?
**Answer:** All candidate chunks fall below the relevance threshold ($s < 0.35$). The context builder detects insufficient context and the system returns a safe refusal message: *"I cannot find sufficient policy documentation to answer this question accurately."*

### 17. How are source citations generated and verified?
**Answer:** Each chunk retains metadata (`document_name`, `chunk_id`, `page_number`). The context builder attaches `[S1]`, `[S2]` markers. The response parser checks that citations in the generated answer match actual context chunks.

### 18. Why FastAPI for the backend?
**Answer:** FastAPI is an asynchronous, high-throughput Python framework with native OpenAPI documentation, strict Pydantic request validation, and asynchronous event loops.

### 19. Why PostgreSQL for the database?
**Answer:** PostgreSQL is an enterprise-grade ACID-compliant relational database providing robust relational integrity, foreign key cascading, and reliable storage for users, documents, chunks, and message logs.

### 20. Why React for the frontend?
**Answer:** React 18 provides a component-based reactive architecture with Virtual DOM updates, supporting real-time chat streaming, live health status pills, and interactive citation inspection modals.

### 21. How does the frontend communicate with the backend?
**Answer:** Via asynchronous HTTP REST API calls using JSON payloads, authenticated with Bearer JWT tokens in request headers.

### 22. How is authentication implemented?
**Answer:** Using JSON Web Tokens (JWT) signed with HMAC-SHA256 and salted password hashing via bcrypt.

### 23. What security defenses are implemented?
**Answer:**
1. Filename sanitization (`secure_filename`) preventing path traversal;
2. File size and MIME type validation;
3. Document injection isolation using `<CONTEXT_DOCUMENTATION>` XML delimiters;
4. Role-based access control (`USER` vs `ADMIN`).

### 24. What are the system's limitations?
**Answer:** Scanned bitmap PDFs require external OCR; graphical charts are not visually parsed; multi-turn conversation memory is bounded to recent message windows.

### 25. What were your empirical evaluation results?
**Answer:** On 35 benchmark questions: 100% Top-1 Retrieval Hit Rate, 67.27% Precision@5, 100% Recall@5, 81.82% Answer Accuracy, 100% Faithfulness, 0.0% Hallucination Rate, and 16.14 ms average latency.

### 26. How did you test for hallucination?
**Answer:** We evaluated answerable, out-of-domain (e.g., Mars travel), and adversarial prompt-injection queries using our evaluation engine (`app.evaluation.runner`), verifying that all assertions were strictly grounded in context chunks.

### 27. What happens if Ollama is offline or unavailable?
**Answer:** The LLM service catches the connection error and returns a structured degradation payload (`llm_unavailable`) with the retrieved context passages so the user can still read the authoritative chunks directly.

### 28. How is the system distributed/service-oriented?
**Answer:** The frontend, API gateway, PostgreSQL database, FAISS vector engine, and Ollama LLM are completely decoupled into autonomous services communicating over network-transparent REST interfaces.

### 29. How does the chunk overlap of 100 characters help?
**Answer:** It prevents sentences or policy clauses from being cut in half at chunk boundaries, ensuring semantic completeness across adjacent chunks.

### 30. How can this system be improved in future work?
**Answer:** By adding hybrid BM25 lexical search, Cross-Encoder re-ranking, OCR for scanned documents, Multimodal Vision-Language Models for chart interpretation, and Kubernetes cluster orchestration.

---

## Part 3: Categorized Technical Viva Q&A

### A. RAG & NLP Architecture
- **Q: What is the difference between naive RAG and your advanced RAG implementation?**  
  *A:* Naive RAG directly passes all retrieved chunks into an LLM. Our advanced RAG implementation includes text normalization, cosine relevance threshold filtering ($s \ge 0.35$), context deduplication, prompt-injection isolation delimiters, and post-generation citation validation.
- **Q: What is Precision@K vs Recall@K?**  
  *A:* Precision@K measures the proportion of the top $K$ retrieved chunks that are truly relevant. Recall@K measures the proportion of all relevant chunks in the database that were successfully retrieved in the top $K$.

### B. Machine Learning & Embeddings
- **Q: What is the embedding dimension of `all-MiniLM-L6-v2`?**  
  *A:* 384 dimensions.
- **Q: Why do we normalize embedding vectors to unit length?**  
  *A:* Normalizing vectors ($\|\mathbf{v}\|_2 = 1.0$) makes the Euclidean distance monotonic to cosine similarity and allows cosine similarity to be computed as a simple dot product ($\mathbf{A} \cdot \mathbf{B}$), which is computationally much faster.

### C. Backend & API Engineering
- **Q: What is ASGI vs WSGI?**  
  *A:* ASGI (Asynchronous Server Gateway Interface) supports asynchronous non-blocking concurrent request handling (used by FastAPI/Uvicorn), whereas WSGI is synchronous.
- **Q: How does Alembic handle schema migrations?**  
  *A:* Alembic inspects SQLAlchemy declarative models and generates versioned SQL migration scripts that can upgrade or downgrade database schemas without data loss.

### D. Security & Enterprise Compliance
- **Q: How does the system defend against prompt injection inside uploaded documents?**  
  *A:* Document text is strictly encapsulated inside `<CONTEXT_DOCUMENTATION>` XML tags, and the system prompt explicitly instructs the LLM that text inside context tags is passive reference data, not executable instructions.
