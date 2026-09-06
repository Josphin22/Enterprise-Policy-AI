# 3. Existing System Analysis

## 3.1 Existing Approaches in Enterprise Document Management

1. **Manual Document Search:** Employees manually navigate hierarchical folder structures on corporate intranets, open individual PDF or Word files, and manually skim or use `Ctrl+F` to search for policy terms.
2. **Lexical / Keyword-Based Search (BM25 / Inverted Index):** Search engines index individual words and calculate Term Frequency-Inverse Document Frequency (TF-IDF) or BM25 scores.
3. **Public Cloud AI Assistants (e.g., ChatGPT, Copilot):** Employees copy-paste policy questions or entire documents into commercial cloud-hosted AI chats.
4. **General-Purpose Un-grounded Foundation Models:** Utilizing pre-trained LLMs without external retrieval mechanisms.

## 3.2 Critical Disadvantages and Vulnerabilities

| Dimension | Existing System | Limitation / Vulnerability |
| :--- | :--- | :--- |
| **Search Precision** | Keyword Search | Fails to comprehend semantic equivalence (e.g., "yearly leave" vs "annual vacation"). Misses multi-clause context. |
| **User Productivity** | Manual Skimming | High labor cost; average knowledge worker spends 1.8 to 2.5 hours per day searching for corporate information. |
| **Data Privacy** | Cloud AI Services | High security risk; sensitive enterprise policies, salaries, and proprietary protocols are exposed to third-party cloud infrastructure. |
| **Factual Veracity** | Generic LLMs | High hallucination rate; models fabricate nonexistent organizational rules when uncertain. |
| **Traceability** | Black-box LLMs | Lack of auditable source citations; impossible for compliance officers to verify the underlying policy document or page number. |
