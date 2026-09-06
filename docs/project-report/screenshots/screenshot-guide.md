# Screenshot Checklist & Manual Capture Guide

This document lists all 20 required screenshots for the project report, along with their standardized file names, descriptions, and exact UI locations for capture.

---

## Required Screenshots Table

| # | Filename | Description | UI Location / Command |
| :-: | :--- | :--- | :--- |
| 1 | `01-login.png` | User Login & Authentication Screen | Frontend `/login` or Login Modal |
| 2 | `02-dashboard.png` | System Dashboard & Quick Health Metrics | Frontend `/dashboard` |
| 3 | `03-document-upload.png` | Document Upload Drag-and-Drop Dropzone | Frontend `/documents` |
| 4 | `04-document-list.png` | Repository Table of Ingested Documents | Frontend `/documents` (table view) |
| 5 | `05-document-processing.png` | Document Parsing & Chunking Status | Frontend `/documents` (processing indicator) |
| 6 | `06-knowledge-base.png` | Knowledge Base Overview & Vector Stats | Frontend `/knowledge-base` |
| 7 | `07-faiss-status.png` | FAISS Index Health & Dimension Diagnostics | Frontend `/knowledge-base` (FAISS details) |
| 8 | `08-chat.png` | Empty Chat Assistant Interface | Frontend `/assistant` |
| 9 | `09-question.png` | User Submitting a Policy Question | Frontend `/assistant` (active query) |
| 10 | `10-answer.png` | Grounded Natural Language Answer Output | Frontend `/assistant` (response bubble) |
| 11 | `11-sources.png` | Source Citation Badge & Chunk Modal | Frontend `/assistant` (Source modal open) |
| 12 | `12-chat-history.png` | Chat History & Conversation Log List | Frontend `/history` |
| 13 | `13-admin.png` | System Settings & Re-indexing Controls | Frontend `/settings` |
| 14 | `14-evaluation.png` | Evaluation Dashboard Overview | Frontend `/evaluation` |
| 15 | `15-retrieval-metrics.png` | Retrieval Accuracy (Top-K & Hit Rates) | Frontend `/evaluation` (Retrieval chart) |
| 16 | `16-hallucination.png` | Hallucination Benchmark (0.0% Rate) | Frontend `/evaluation` (Grounding chart) |
| 17 | `17-system-health.png` | Real-Time Service Health Diagnostic Pill | Header status badge or `/dashboard` |
| 18 | `18-swagger.png` | FastAPI Interactive Swagger UI Documentation| Browser `http://localhost:8000/docs` |
| 19 | `19-database.png` | PostgreSQL Relational Schema & Tables | pgAdmin / DBeaver / Terminal SQL query |
| 20 | `20-terminal.png` | Terminal Showing App Running & Pytest Passing | Terminal console window |

---

## Instructions for Saving Screenshots

Save each captured image in this folder: `docs/project-report/screenshots/` with the exact corresponding filename listed above (PNG format).
