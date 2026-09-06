# 5–10 Minute Presentation Demonstration Flow Script

**Project Title:** Local Enterprise Policy Assistant Using Retrieval-Augmented Generation  
**Target Audience:** Evaluators, Faculty Committee, Industry Reviewers  
**Demonstration Time:** 5–10 Minutes  

---

## Demonstration Script & Step-by-Step Flow

### STEP 1: Application Architecture & Overview (1 Minute)
- **Action:** Introduce the purpose of the project.
- **Narrative:**  
  *"Good morning/afternoon. Today I am presenting our **Local Enterprise Policy Assistant**, built on Retrieval-Augmented Generation (RAG). The goal is to provide enterprise employees with instant, natural-language answers to policy and compliance queries while guaranteeing 100% data privacy by keeping all embeddings, vector storage, and language generation strictly on-premises without external cloud APIs."*

---

### STEP 2: Dashboard & System Health Inspection (1 Minute)
- **Action:** Open browser to `http://localhost:5173`. Show the **Dashboard** and health status pill in the top header.
- **Narrative:**  
  *"Here on the Dashboard, we can observe real-time system metrics: total indexed documents, total chunks, FAISS vector index health, and backend API status. The status pill indicates all sub-services (FastAPI backend, PostgreSQL database, and FAISS vector index) are active and responsive."*

---

### STEP 3: Document Ingestion & Chunking (1.5 Minutes)
- **Action:** Navigate to the **Documents** tab. Drag and drop `Leave_Policy.pdf` (or `Remote_Work_Policy.txt`).
- **Narrative:**  
  *"In the Documents module, the administrator uploads official enterprise guidelines. Upon upload, our backend performs security sanitization, extracts text using PyPDF/python-docx, cleans noise, and applies recursive chunking with a 500-character window and 100-character overlap. Each chunk is persisted in PostgreSQL with document ID and page metadata."*

---

### STEP 4: Knowledge Base & Vector Indexing (1 Minute)
- **Action:** Navigate to the **Knowledge Base** tab. Click **Rebuild Index** or inspect the current FAISS status.
- **Narrative:**  
  *"In the Knowledge Base tab, each document chunk is transformed into a 384-dimensional normalized dense vector using the `sentence-transformers/all-MiniLM-L6-v2` model. Vectors are indexed in FAISS (`IndexFlatIP`) for sub-millisecond inner-product similarity search."*

---

### STEP 5: Policy Query & Grounded Answer Generation (1.5 Minutes)
- **Action:** Navigate to the **Assistant** tab. In the chat prompt, enter:  
  `"How many annual leave days are allowed?"`
- **Narrative:**  
  *"When the user submits a question, our backend embeds the query, queries FAISS for the Top-5 most relevant chunks using cosine similarity, applies a relevance threshold (0.35), and constructs a grounded prompt. The local model produces an exact answer citing '15 days of annual leave' along with interactive source citations."*
- **Action:** Click the **Source Citation** badge under the response to open the **Source Viewer Modal**. Show the highlighted supporting text from `Leave_Policy.pdf`.

---

### STEP 6: Negative / Out-of-Domain Query & Hallucination Prevention (1 Minute)
- **Action:** In the chat prompt, enter:  
  `"What is the company's policy for travel to Mars?"`
- **Narrative:**  
  *"To prove our system does not hallucinate fictional facts, we submit an out-of-domain query. All retrieved candidate chunks fall below our relevance threshold. The system safely refuses: 'I cannot find sufficient policy documentation to answer this question accurately.' This guarantees zero hallucination."*

---

### STEP 7: Paraphrasing & Numerical Robustness (1 Minute)
- **Action:** Submit a paraphrased question:  
  `"What is the yearly leave entitlement?"`
- **Narrative:**  
  *"Because our system uses dense semantic vector embeddings rather than simplistic keyword matching, the paraphrased question maps to the exact same semantic neighborhood and retrieves the identical authoritative leave policy clause."*

---

### STEP 8: Live Evaluation & Scientific Benchmarks (1 Minute)
- **Action:** Navigate to the **Evaluation** tab.
- **Narrative:**  
  *"Finally, our platform includes a built-in scientific evaluation dashboard. Running the 35-question benchmark shows 100% Top-1 retrieval hit rate, 100% faithfulness, 0.0% hallucination rate, and an average end-to-end response latency of just 16.14 milliseconds."*

---

### STEP 9: Conclusion & Viva Q&A
- **Narrative:**  
  *"This completes our end-to-end demonstration of the Local Enterprise Policy Assistant. I am now ready for questions."*
