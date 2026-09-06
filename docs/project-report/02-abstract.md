# Abstract

Enterprise organizations maintain extensive collections of human resource guidelines, standard operating procedures (SOPs), legal compliance mandates, and departmental policy manuals. Rapidly locating precise, actionable answers within these voluminous and heterogeneous document repositories (PDF, DOCX, TXT) remains a critical productivity challenge. Traditional keyword-based search systems rely strictly on exact lexical matches, frequently returning irrelevant fragments without contextual synthesis or natural-language explanations. Conversely, general-purpose commercial cloud-based Large Language Models (LLMs) introduce critical data privacy and regulatory compliance risks (e.g., GDPR, HIPAA, proprietary trade secret exposure) and are notoriously prone to factual hallucinations—generating plausible yet ungrounded and unverifiable assertions.

To address these limitations, this project presents the engineering and empirical evaluation of the **Local Enterprise Policy Assistant**, an end-to-end, privacy-preserving Retrieval-Augmented Generation (RAG) system running entirely on local infrastructure with zero cloud dependencies. The system architecture incorporates:
1. A multi-format document ingestion and recursive text-chunking pipeline (500-character windows with 100-character overlap) preserving structural metadata;
2. Dense semantic text embeddings generated via `sentence-transformers/all-MiniLM-L6-v2` producing 384-dimensional $L_2$-normalized vectors;
3. Sub-millisecond vector similarity search using a local Facebook AI Similarity Search (FAISS `IndexFlatIP`) index executing normalized cosine similarity;
4. Dynamic context construction with relevance threshold filtering ($s \ge 0.35$) and prompt injection defense barriers;
5. Local on-premise language model generation powered by quantized Ollama (`llama3.2:3b`);
6. Relational metadata persistence, session history tracking, and user feedback logging via PostgreSQL and SQLAlchemy 2.0;
7. An asynchronous FastAPI REST API backend and a modern React 18 single-page frontend.

The system was evaluated against a 35-query empirical benchmark dataset containing answerable policy questions, paraphrased variants, multi-document queries, numerical/date-sensitive queries, and adversarial prompt injection attempts. Empirical evaluation results demonstrate a **100.0% Top-1 Retrieval Hit Rate**, **100.0% Faithfulness**, **0.0% Hallucination Rate**, **81.82% Answer Accuracy**, and an average end-to-end pipeline latency of **16.14 ms** (P95 latency of 20.00 ms). Every generated answer is accompanied by verifiable, interactive chunk-level source citations, ensuring complete organizational transparency, factual grounding, and absolute data privacy.
