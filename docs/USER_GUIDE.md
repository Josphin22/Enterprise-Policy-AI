# Enterprise Policy AI — End-User Guide

Welcome to the **Enterprise Policy AI Assistant**. This guide explains how to query internal corporate policies, inspect citations, review conversation history, and submit response feedback.

---

## 1. Asking Policy Questions

1. Open the **AI Assistant** tab in the sidebar navigation.
2. Type your question in plain English in the bottom input prompt, for example:
   - *"How many annual leave days are allowed?"*
   - *"What is the policy for carrying over unused vacation days?"*
   - *"What are the core working hours for remote employees?"*
3. Press `Enter` or click the Send button.
4. While formulating an answer, the assistant displays dynamic progress indicators:
   - `Searching policies...` (vector similarity search in FAISS)
   - `Generating answer...` (local Ollama LLM synthesis)

---

## 2. Inspecting Source Citations

Every grounded response includes inline citation references (e.g. `[S1]`, `[S2]`).
- **Citation Badges**: Click any citation pill under the answer to automatically highlight the corresponding document excerpt in the right-hand panel.
- **Passage Excerpts**: Expand the excerpt cards in the citations panel to review the exact paragraph, page number, section header, and retrieval similarity score.
- **Strict Grounding Guarantee**: If a question cannot be answered from the company documents, the assistant will explicitly state:
  > *"I could not find sufficient information in the provided enterprise documents to answer this question."*

---

## 3. Managing Conversation Sessions

- **Thread History**: Past conversations are listed in the left sidebar of the AI Assistant module.
- **Searching Threads**: Use the search input box to filter conversations by keyword.
- **Renaming Conversations**: Click the Edit icon beside any conversation thread to rename it.
- **Deleting Threads**: Click the Trash icon to remove unwanted conversation history.
- **New Conversation**: Click the **+ New Chat** button in the header at any time.

---

## 4. Submitting Feedback

Help improve enterprise policy guidance by rating answers:
- Click the **Thumbs Up** icon if the answer was accurate and helpful.
- Click the **Thumbs Down** icon if the answer was ungrounded, incomplete, or unhelpful.
All ratings are logged to the administrative audit analytics database for continuous quality monitoring.
