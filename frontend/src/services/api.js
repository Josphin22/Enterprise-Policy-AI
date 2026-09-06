import axios from 'axios';

// Get API base URL from environment variable or fallback to localhost:8000
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 120000, // 120s timeout for local LLM inference
  headers: {
    'Accept': 'application/json',
  },
});

/**
 * 1. Health Status API
 * GET /api/health
 */
export async function getHealthStatus() {
  const startTime = performance.now();
  try {
    const response = await apiClient.get('/api/health');
    const endTime = performance.now();
    const latencyMs = Math.round(endTime - startTime);

    if (response.status === 200 && response.data?.status === 'healthy') {
      return {
        isConnected: true,
        data: response.data,
        latencyMs,
        error: null,
      };
    }

    return {
      isConnected: false,
      data: response.data,
      latencyMs,
      error: `Unexpected response status: HTTP ${response.status}`,
    };
  } catch (err) {
    let errorMessage = 'Unable to connect to the backend.';
    if (err.response) {
      errorMessage = `Server error (HTTP ${err.response.status}): ${err.response.statusText}`;
    } else if (err.request) {
      errorMessage = `Cannot reach server at ${API_BASE_URL}. Ensure FastAPI is running on port 8000.`;
    } else {
      errorMessage = err.message || 'Unknown network error';
    }

    return {
      isConnected: false,
      data: null,
      latencyMs: null,
      error: errorMessage,
    };
  }
}

/**
 * 2. System Status API
 * GET /api/system/status
 */
export async function getSystemStatus() {
  try {
    const response = await apiClient.get('/api/system/status');
    return { success: true, data: response.data, error: null };
  } catch (err) {
    return {
      success: false,
      data: null,
      error: err.response?.data?.error || err.message || 'Failed to fetch system status',
    };
  }
}

/**
 * 2b. Local LLM Status APIs (Phase 8)
 * GET /api/llm/status
 * GET /api/llm/models
 */
export async function getLLMStatus() {
  try {
    const response = await apiClient.get('/api/llm/status');
    return { success: true, data: response.data, error: null };
  } catch (err) {
    return {
      success: false,
      data: null,
      error: err.response?.data?.error || err.message || 'Failed to fetch LLM status',
    };
  }
}

export async function getLLMModels() {
  try {
    const response = await apiClient.get('/api/llm/models');
    return { success: true, models: response.data || [], error: null };
  } catch (err) {
    return {
      success: false,
      models: [],
      error: err.response?.data?.error || err.message || 'Failed to fetch LLM models',
    };
  }
}

/**
 * 3. Document Ingestion & Management APIs
 */

// GET /api/documents
export async function getDocuments() {
  try {
    const response = await apiClient.get('/api/documents');
    return { success: true, documents: response.data?.documents || [], total: response.data?.total || 0, error: null };
  } catch (err) {
    return {
      success: false,
      documents: [],
      total: 0,
      error: err.response?.data?.error || err.message || 'Failed to fetch documents',
    };
  }
}

// GET /api/documents/:id
export async function getDocument(documentId) {
  try {
    const response = await apiClient.get(`/api/documents/${documentId}`);
    return { success: true, data: response.data, error: null };
  } catch (err) {
    return {
      success: false,
      data: null,
      error: err.response?.data?.error || err.message || 'Failed to fetch document',
    };
  }
}

// POST /api/documents/upload (multipart/form-data)
export async function uploadDocument(file, onProgress) {
  const formData = new FormData();
  formData.append('file', file);

  try {
    const response = await apiClient.post('/api/documents/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      onUploadProgress: (progressEvent) => {
        if (onProgress && progressEvent.total) {
          const percent = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          onProgress(percent);
        }
      },
    });

    return { success: true, data: response.data, error: null };
  } catch (err) {
    const detailMsg = err.response?.data?.error || err.response?.data?.detail || err.message || 'Upload failed';
    return {
      success: false,
      data: null,
      error: detailMsg,
    };
  }
}

// DELETE /api/documents/:id
export async function deleteDocument(documentId) {
  try {
    const response = await apiClient.delete(`/api/documents/${documentId}`);
    return { success: true, data: response.data, error: null };
  } catch (err) {
    return {
      success: false,
      data: null,
      error: err.response?.data?.error || err.message || 'Failed to delete document',
    };
  }
}

// POST /api/documents/:id/process
export async function processDocument(documentId) {
  try {
    const response = await apiClient.post(`/api/documents/${documentId}/process`);
    return { success: true, data: response.data, error: null };
  } catch (err) {
    return {
      success: false,
      data: null,
      error: err.response?.data?.error || err.response?.data?.detail || err.message || 'Failed to process document',
    };
  }
}

// GET /api/documents/:id/chunks
export async function getDocumentChunks(documentId) {
  try {
    const response = await apiClient.get(`/api/documents/${documentId}/chunks`);
    return {
      success: true,
      data: response.data,
      chunks: response.data?.chunks || [],
      chunk_count: response.data?.chunk_count || 0,
      error: null,
    };
  } catch (err) {
    return {
      success: false,
      data: null,
      chunks: [],
      chunk_count: 0,
      error: err.response?.data?.error || err.response?.data?.detail || err.message || 'Failed to fetch document chunks',
    };
  }
}

/**
 * 4. Knowledge Base APIs
 */

// GET /api/knowledge-base/status
export async function getKnowledgeBaseStatus() {
  try {
    const response = await apiClient.get('/api/knowledge-base/status');
    return { success: true, data: response.data, error: null };
  } catch (err) {
    return {
      success: false,
      data: null,
      error: err.response?.data?.error || err.message || 'Failed to fetch knowledge base status',
    };
  }
}

// POST /api/knowledge-base/build
export async function buildKnowledgeBase() {
  try {
    const response = await apiClient.post('/api/knowledge-base/build');
    return { success: true, data: response.data, error: null };
  } catch (err) {
    return {
      success: false,
      data: null,
      error: err.response?.data?.error || err.response?.data?.detail || err.message || 'Failed to trigger knowledge base build',
    };
  }
}

// POST /api/knowledge-base/search
export async function searchKnowledgeBase(query, topK = 5) {
  try {
    const response = await apiClient.post('/api/knowledge-base/search', {
      query,
      top_k: topK,
    });
    return {
      success: true,
      data: response.data,
      results: response.data?.results || [],
      total_matches: response.data?.total_matches || 0,
      error: null,
    };
  } catch (err) {
    return {
      success: false,
      data: null,
      results: [],
      total_matches: 0,
      error: err.response?.data?.error || err.response?.data?.detail || err.message || 'Semantic search failed',
    };
  }
}

// POST /api/documents/:id/reindex
export async function reindexDocument(documentId) {
  try {
    const response = await apiClient.post(`/api/documents/${documentId}/reindex`);
    return { success: true, data: response.data, error: null };
  } catch (err) {
    return {
      success: false,
      data: null,
      error: err.response?.data?.error || err.response?.data?.detail || err.message || 'Failed to reindex document',
    };
  }
}

/**
 * 4b. RAG Retrieval Engine API (Phase 7)
 * POST /api/rag/retrieve
 */
export async function retrieveRAGContext(query, topK = 5, minScore = 0.35) {
  try {
    const response = await apiClient.post('/api/rag/retrieve', {
      query,
      top_k: topK,
      min_score: minScore,
    });
    return {
      success: true,
      data: response.data,
      status: response.data?.status,
      context: response.data?.context,
      sources: response.data?.sources || [],
      total_sources: response.data?.total_sources || 0,
      debug_info: response.data?.debug_info,
      message: response.data?.message,
      error: null,
    };
  } catch (err) {
    return {
      success: false,
      data: null,
      status: 'error',
      context: '',
      sources: [],
      total_sources: 0,
      debug_info: null,
      message: null,
      error: err.response?.data?.error || err.response?.data?.detail || err.message || 'RAG retrieval failed',
    };
  }
}

/**
 * 5. Chat & Feedback APIs (Phase 8 Local LLM)
 */

// POST /api/chat
export async function sendChatMessage(question, sessionId = null, topK = 5) {
  try {
    const payload = {
      question,
      message: question,
      session_id: sessionId,
      top_k: topK,
    };
    const response = await apiClient.post('/api/chat', payload);
    return {
      success: response.data?.success !== false,
      data: response.data,
      status: response.data?.status,
      answer: response.data?.answer,
      context: response.data?.context,
      sources: response.data?.sources || [],
      total_sources: response.data?.total_sources || 0,
      message_id: response.data?.message_id,
      assistant_message_id: response.data?.assistant_message_id,
      session_id: response.data?.session_id,
      message: response.data?.message,
      retrieval_duration_ms: response.data?.retrieval_duration_ms,
      llm_duration_ms: response.data?.llm_duration_ms,
      total_duration_ms: response.data?.total_duration_ms,
      error: null,
    };
  } catch (err) {
    const errObj = err.response?.data;
    return {
      success: false,
      data: null,
      status: 'generation_error',
      answer: null,
      context: '',
      sources: [],
      total_sources: 0,
      message_id: null,
      assistant_message_id: null,
      session_id: sessionId,
      message: errObj?.message || errObj?.error || errObj?.detail || err.message || 'Chat request failed',
      error: errObj?.message || errObj?.error || errObj?.detail || err.message || 'Chat request failed',
    };
  }
}

// GET /api/chat/history
export async function getChatHistory(sessionId = null) {
  try {
    const url = sessionId ? `/api/chat/history?session_id=${sessionId}` : '/api/chat/history';
    const response = await apiClient.get(url);
    return {
      success: true,
      history: response.data?.history || [],
      sessions: response.data?.sessions || [],
      total: response.data?.total || 0,
      error: null,
    };
  } catch (err) {
    return {
      success: false,
      history: [],
      sessions: [],
      total: 0,
      error: err.response?.data?.error || err.message || 'Failed to fetch chat history',
    };
  }
}

// POST /api/chat/sessions
export async function createChatSession(title = 'Policy Query Session') {
  try {
    const response = await apiClient.post('/api/chat/sessions', { title });
    return { success: true, data: response.data, session_id: response.data?.session_id, error: null };
  } catch (err) {
    return {
      success: false,
      data: null,
      session_id: null,
      error: err.response?.data?.error || err.message || 'Failed to create chat session',
    };
  }
}

// GET /api/chat/sessions
export async function getChatSessions() {
  try {
    const response = await apiClient.get('/api/chat/sessions');
    return { success: true, sessions: response.data || [], error: null };
  } catch (err) {
    return {
      success: false,
      sessions: [],
      error: err.response?.data?.error || err.message || 'Failed to fetch chat sessions',
    };
  }
}

// POST /api/chat/feedback
export async function sendFeedback(messageId, rating, comment = null) {
  try {
    const response = await apiClient.post('/api/chat/feedback', {
      message_id: messageId,
      rating,
      comment,
    });
    return { success: true, data: response.data, error: null };
  } catch (err) {
    return {
      success: false,
      data: null,
      error: err.response?.data?.error || err.message || 'Feedback submission failed',
    };
  }
}

/**
 * 6. Scientific RAG Evaluation APIs (Phase 9)
 */

// GET /api/evaluation/summary
export async function getEvaluationSummary() {
  try {
    const response = await apiClient.get('/api/evaluation/summary');
    return { success: true, data: response.data, error: null };
  } catch (err) {
    return {
      success: false,
      data: null,
      error: err.response?.data?.error || err.message || 'Failed to fetch evaluation summary',
    };
  }
}

// GET /api/evaluation/results
export async function getEvaluationResults() {
  try {
    const response = await apiClient.get('/api/evaluation/results');
    return { success: true, results: response.data || [], error: null };
  } catch (err) {
    return {
      success: false,
      results: [],
      error: err.response?.data?.error || err.message || 'Failed to fetch evaluation results',
    };
  }
}

// POST /api/evaluation/run
export async function triggerEvaluationRun(topK = 5, minScore = 0.35) {
  try {
    const response = await apiClient.post('/api/evaluation/run', {
      top_k: topK,
      min_score: minScore,
    });
    return { success: true, data: response.data, error: null };
  } catch (err) {
    return {
      success: false,
      data: null,
      error: err.response?.data?.detail || err.message || 'Failed to trigger evaluation run',
    };
  }
}

export default apiClient;
