# 23. Future Enhancements & Roadmap

1. **Hybrid Retrieval (Dense Vector + BM25 Lexical):** Implement Reciprocal Rank Fusion (RRF) to merge FAISS dense semantic retrieval with BM25 sparse keyword search for improved exact acronym matching.
2. **Cross-Encoder Re-Ranking:** Integrate a lightweight Cross-Encoder (e.g., `ms-marco-MiniLM-L-6-v2`) to re-rank the Top-10 FAISS candidate chunks before LLM context assembly.
3. **Multimodal Document Understanding:** Incorporate Vision-Language Models (such as LLaVA or ColPali) to parse complex architectural diagrams, workflows, and organizational charts.
4. **Distributed Kubernetes Orchestration:** Scale FAISS vector workers and Ollama LLM nodes across a distributed cluster with automatic load balancing.
5. **Enterprise SSO & Active Directory Integration:** Integrate SAML 2.0 / OAuth2 with corporate Azure AD / Okta systems for Single Sign-On and document-level role access control.
6. **Automated Document Versioning:** Implement automated diff detection and re-indexing when corporate policies are updated.
