# 5-Minute Demonstration Script for Viva / Project Defense

**Project Title:** LOCAL ENTERPRISE POLICY ASSISTANT USING RETRIEVAL-AUGMENTED GENERATION  
**Target Duration:** 5 Minutes  
**Demonstration URL:** `http://localhost:5173`  

---

### Phase 1: Introduction & System Status (30 Seconds)
- **Action:** Open the web application at `http://localhost:5173`. Point to the **Dashboard** and top header **Health Pill**.
- **Dialogue:**  
  *"Good morning. Here is our live Local Enterprise Policy Assistant. Notice the health status pill in the header showing that our FastAPI backend, PostgreSQL database, and FAISS vector index are fully connected and healthy on local host."*

---

### Phase 2: Document Management & Chunking (1 Minute)
- **Action:** Click the **Documents** tab. Show the repository table. Drag and drop `Leave_Policy.pdf`.
- **Dialogue:**  
  *"In the Documents module, we upload enterprise policies in PDF, Word, or TXT format. Upon upload, our parser extracts the text, normalizes whitespace, and applies a recursive sliding chunker with a 500-character window and 100-character overlap, storing chunks and page metadata in PostgreSQL."*

---

### Phase 3: Knowledge Base & Vector Store (45 Seconds)
- **Action:** Click the **Knowledge Base** tab. Show the FAISS index health, vector count, and 384-dimension configuration.
- **Dialogue:**  
  *"In the Knowledge Base tab, all stored chunks are converted into 384-dimensional dense vectors using SentenceTransformers (`all-MiniLM-L6-v2`) and indexed in FAISS (`IndexFlatIP`). The vector count precisely matches our active chunk count."*

---

### Phase 4: Policy Assistant & Grounded Query Answering (1.5 Minutes)
- **Action:** Click the **Assistant** tab. In the chat prompt, enter:  
  `"How many annual leave days are allowed?"`
- **Dialogue:**  
  *"Now let's ask a policy question: 'How many annual leave days are allowed?'. When we submit, the system embeds the query, queries FAISS using cosine similarity in under 8 milliseconds, formats the context, and invokes our local Ollama LLM (`llama3.2:3b`)."*
- **Action:** Point to the generated answer and the source citation badge beneath it. Click the citation badge to open the **Source Viewer Modal**.
- **Dialogue:**  
  *"The model outputs the exact answer: 'Full-time employees are entitled to 15 working days of paid annual leave per calendar year.' Clicking the source citation opens our modal, showing the exact highlighted chunk from Leave_Policy.pdf, Section 3.1, Page 2."*

---

### Phase 5: Anti-Hallucination & Refusal Test (45 Seconds)
- **Action:** In the chat prompt, enter:  
  `"What is the company's official policy for commercial travel to Mars?"`
- **Dialogue:**  
  *"To demonstrate our anti-hallucination defense, let's ask an out-of-domain question about Mars travel. All candidate chunks fall below our 0.35 relevance threshold. The system safely refuses: 'I cannot find sufficient policy documentation to answer this question accurately.' It does not hallucinate."*

---

### Phase 6: Live Evaluation Dashboard & Conclusion (30 Seconds)
- **Action:** Click the **Evaluation** tab. Show the empirical benchmark cards (100% Top-1 Retrieval, 100% Faithfulness, 0% Hallucination, 16.14 ms average latency).
- **Dialogue:**  
  *"Finally, our live Evaluation Dashboard shows empirical results across our 35-query benchmark: 100% Top-1 retrieval hit rate, 100% faithfulness, and zero hallucinations. This concludes our live demonstration."*
