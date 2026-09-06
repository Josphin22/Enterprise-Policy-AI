# 10. Distributed Computing & Service Architecture

## 10.1 Modular Service-Oriented Architecture
While the current prototype is deployed and benchmarked on a unified local host for zero-cloud enterprise prototyping, the system was deliberately designed following **Distributed Service-Oriented Architecture (SOA)** principles. Each core capability is completely decoupled into independent, autonomous service modules communicating over standardized, network-transparent protocols.

```text
┌─────────────────────────┐
│     Client Machines     │
│   (Web Browsers / SPA)  │
└────────────┬────────────┘
             │ HTTP / JSON
             ▼
┌─────────────────────────┐
│    API Gateway Node     │  ◄── Horizontal Scaling (Nginx / Load Balancer)
│    (FastAPI / Uvicorn)  │
└──────┬──────┬─────┬─────┘
       │      │     │
       ▼      ▼     ▼
┌──────────┐ ┌──────────┐ ┌──────────────────────┐
│ Database │ │ Vector   │ │ LLM Inference Worker │
│ Node     │ │ Engine   │ │ (Ollama / GPU Node)  │
│ (Postgres│ │ (FAISS)  │ └──────────────────────┘
└──────────┘ └──────────┘
```

## 10.2 Service Separation & Communication Interfaces

1. **Frontend Presentation Service:** Static single-page application served via CDN or web server (Vite / Nginx). Communicates with the API gateway strictly via asynchronous JSON REST endpoints.
2. **API Application Gateway:** Stateless FastAPI server handling authentication, validation, session management, and orchestration.
3. **Database Service:** PostgreSQL database server managing ACID transactions, entity constraints, and query indexes. Can be deployed on a dedicated database server or managed relational instance.
4. **Vector Storage & Embedding Service:** Dedicated vector computation module encapsulating SentenceTransformers and FAISS. In distributed deployments, this service can scale independently or transition to distributed vector clusters (such as Milvus or Qdrant).
5. **Local LLM Inference Engine:** Ollama running as an isolated daemon. In enterprise production, multiple GPU worker nodes can run LLM daemon instances behind a round-robin load balancer.

## 10.3 Distributed Readiness Summary
- **Stateless Application Tier:** The FastAPI backend stores all persistent state in PostgreSQL and FAISS, enabling multi-instance load balancing.
- **Fault Isolation:** An outage in the LLM daemon does not crash the API gateway or database; the system returns structured degradation messages (`llm_unavailable`).
- **Data Locality:** By encapsulating all services within a private corporate Virtual Private Cloud (VPC) or local area network (LAN), the architecture guarantees zero data leakage across external network boundaries.
