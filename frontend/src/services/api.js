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

// Attach Authorization header if JWT token is stored
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('auth_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

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
 * 2c. Ollama Health API (Phase 6)
 * GET /api/health/ollama
 */
export async function getOllamaHealth() {
  try {
    const response = await apiClient.get('/api/health/ollama');
    return { success: true, data: response.data, error: null };
  } catch (err) {
    return {
      success: false,
      data: null,
      error: err.response?.data?.error || err.message || 'Failed to fetch Ollama health',
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
    let detailMsg = err.response?.data?.error?.message || err.response?.data?.detail?.message || err.response?.data?.detail || err.response?.data?.error || err.message || 'Upload failed';
    if (typeof detailMsg === 'object') {
      detailMsg = detailMsg.message || JSON.stringify(detailMsg);
    }
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

// GET /api/documents/:id/preview
export async function getDocumentPreview(documentId) {
  try {
    const response = await apiClient.get(`/api/documents/${documentId}/preview`);
    return {
      success: true,
      data: response.data,
      error: null,
    };
  } catch (err) {
    return {
      success: false,
      data: null,
      error: err.response?.data?.detail || err.response?.data?.error || err.message || 'Failed to fetch document preview',
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

// POST /api/knowledge-base/rebuild
export async function buildKnowledgeBase() {
  try {
    const response = await apiClient.post('/api/knowledge-base/rebuild');
    return { success: true, data: response.data, error: null };
  } catch (err) {
    const errorMsg =
      err.response?.data?.error?.message ||
      err.response?.data?.error ||
      err.response?.data?.detail ||
      err.message ||
      'Failed to trigger knowledge base build';
    return {
      success: false,
      data: null,
      error: typeof errorMsg === 'object' ? JSON.stringify(errorMsg) : errorMsg,
    };
  }
}

export const rebuildKnowledgeBase = buildKnowledgeBase;

// POST /api/knowledge-base/search
export async function searchKnowledgeBase(query, topK = 5, minScore = 0.35) {
  try {
    const response = await apiClient.post('/api/knowledge-base/search', {
      query,
      top_k: topK,
      min_score: minScore,
    });
    return {
      success: true,
      data: response.data,
      results: response.data?.results || [],
      total_matches: response.data?.total_matches || 0,
      error: null,
    };
  } catch (err) {
    const errorMsg =
      err.response?.data?.error ||
      err.response?.data?.detail ||
      err.message ||
      'Semantic search failed';
    return {
      success: false,
      data: null,
      results: [],
      total_matches: 0,
      error: typeof errorMsg === 'object' ? JSON.stringify(errorMsg) : errorMsg,
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
export async function sendChatMessage(question, sessionId = null, topK = 5, documentId = null, language = 'en') {
  try {
    const payload = {
      message: question,
      question: question,
      conversation_id: sessionId,
      session_id: sessionId,
      top_k: topK,
      document_id: documentId,
      language: language || 'en',
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
      retrieval: response.data?.retrieval,
      message_id: response.data?.message_id,
      assistant_message_id: response.data?.assistant_message_id,
      conversation_id: response.data?.conversation_id || response.data?.session_id,
      session_id: response.data?.session_id || response.data?.conversation_id,
      message: response.data?.message,
      guardrail_status: response.data?.guardrail_status,
      grounding_warning: response.data?.grounding_warning,
      grounding_classification: response.data?.grounding_classification,
      confidence: response.data?.confidence,
      language: response.data?.language,
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
      conversation_id: sessionId,
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

// GET /api/chat/sessions or /api/conversations
export async function getChatSessions(search = '') {
  try {
    const url = search ? `/api/conversations?search=${encodeURIComponent(search)}` : '/api/conversations';
    const response = await apiClient.get(url);
    return { success: true, sessions: response.data || [], error: null };
  } catch (err) {
    return {
      success: false,
      sessions: [],
      error: err.response?.data?.error || err.message || 'Failed to fetch chat sessions',
    };
  }
}

export const getConversations = getChatSessions;

// GET /api/conversations/:id
export async function getConversation(conversationId) {
  try {
    const response = await apiClient.get(`/api/conversations/${conversationId}`);
    return { success: true, data: response.data, conversation: response.data, error: null };
  } catch (err) {
    return {
      success: false,
      data: null,
      conversation: null,
      error: err.response?.data?.error || err.message || 'Failed to fetch conversation details',
    };
  }
}

// PATCH /api/conversations/:id
export async function renameConversation(conversationId, title) {
  try {
    const response = await apiClient.patch(`/api/conversations/${conversationId}`, { title });
    return { success: true, data: response.data, error: null };
  } catch (err) {
    return {
      success: false,
      data: null,
      error: err.response?.data?.error || err.message || 'Failed to rename conversation',
    };
  }
}

// DELETE /api/conversations/:id
export async function deleteConversation(conversationId) {
  try {
    const response = await apiClient.delete(`/api/conversations/${conversationId}`);
    return { success: true, data: response.data, error: null };
  } catch (err) {
    return {
      success: false,
      data: null,
      error: err.response?.data?.error || err.message || 'Failed to delete conversation',
    };
  }
}

// POST /api/chat/messages/:messageId/feedback or POST /api/chat/feedback
export async function submitMessageFeedback(messageId, rating, comment = null) {
  try {
    const response = await apiClient.post(`/api/chat/messages/${messageId}/feedback`, {
      rating,
      comment,
    });
    return { success: true, data: response.data, error: null };
  } catch (err) {
    // Fallback to /api/chat/feedback
    try {
      const fallback = await apiClient.post('/api/chat/feedback', {
        message_id: messageId,
        rating,
        comment,
      });
      return { success: true, data: fallback.data, error: null };
    } catch (fbErr) {
      return {
        success: false,
        data: null,
        error: fbErr.response?.data?.error || fbErr.message || 'Feedback submission failed',
      };
    }
  }
}

// POST /api/chat/feedback
export async function sendFeedback(messageId, rating, comment = null) {
  return submitMessageFeedback(messageId, rating, comment);
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

/**
 * 7. Authentication & User Profile APIs (Phase 8)
 */
export async function loginUser(email, password) {
  try {
    const response = await apiClient.post('/api/auth/login', { email, password });
    if (response.data?.access_token) {
      localStorage.setItem('auth_token', response.data.access_token);
      localStorage.setItem('auth_user', JSON.stringify(response.data.user));
    }
    return { success: true, data: response.data, error: null };
  } catch (err) {
    return {
      success: false,
      data: null,
      error: err.response?.data?.detail || err.response?.data?.error || err.message || 'Login failed',
    };
  }
}

export async function registerUser(email, username, password) {
  try {
    const response = await apiClient.post('/api/auth/register', { email, username, password });
    if (response.data?.access_token) {
      localStorage.setItem('auth_token', response.data.access_token);
      localStorage.setItem('auth_user', JSON.stringify(response.data.user));
    }
    return { success: true, data: response.data, error: null };
  } catch (err) {
    return {
      success: false,
      data: null,
      error: err.response?.data?.detail || err.response?.data?.error || err.message || 'Registration failed',
    };
  }
}

export async function getCurrentUser() {
  try {
    const response = await apiClient.get('/api/auth/me');
    if (response.data) {
      localStorage.setItem('auth_user', JSON.stringify(response.data));
    }
    return { success: true, user: response.data, error: null };
  } catch (err) {
    return {
      success: false,
      user: null,
      error: err.response?.data?.detail || err.message || 'Failed to fetch user',
    };
  }
}

export function logoutUser() {
  localStorage.removeItem('auth_token');
  localStorage.removeItem('auth_user');
}

export function getStoredUser() {
  try {
    const raw = localStorage.getItem('auth_user');
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

/**
 * 8. Enterprise Admin Dashboard & Management APIs (Phase 8)
 */
export async function getAdminDashboard() {
  try {
    const response = await apiClient.get('/api/admin/dashboard');
    return { success: true, data: response.data, error: null };
  } catch (err) {
    return {
      success: false,
      data: null,
      error: err.response?.data?.detail || err.response?.data?.error || err.message || 'Failed to fetch admin dashboard',
    };
  }
}

export async function getAdminUsers(params = {}) {
  try {
    const response = await apiClient.get('/api/admin/users', { params });
    return { success: true, data: response.data, error: null };
  } catch (err) {
    return {
      success: false,
      data: null,
      error: err.response?.data?.detail || err.response?.data?.error || err.message || 'Failed to list users',
    };
  }
}

export async function updateUserRole(userId, role) {
  try {
    const response = await apiClient.patch(`/api/admin/users/${userId}/role`, { role });
    return { success: true, data: response.data, error: null };
  } catch (err) {
    return {
      success: false,
      data: null,
      error: err.response?.data?.detail || err.response?.data?.error || err.message || 'Failed to update role',
    };
  }
}

export async function updateUserStatus(userId, isActive) {
  try {
    const response = await apiClient.patch(`/api/admin/users/${userId}/status`, { is_active: isActive });
    return { success: true, data: response.data, error: null };
  } catch (err) {
    return {
      success: false,
      data: null,
      error: err.response?.data?.detail || err.response?.data?.error || err.message || 'Failed to update user status',
    };
  }
}

export async function getAdminSystemHealth() {
  try {
    const response = await apiClient.get('/api/admin/system-health');
    return { success: true, data: response.data, error: null };
  } catch (err) {
    return {
      success: false,
      data: null,
      error: err.response?.data?.detail || err.response?.data?.error || err.message || 'Failed to fetch health report',
    };
  }
}

export async function getAdminAnalytics(params = {}) {
  try {
    const response = await apiClient.get('/api/admin/analytics', { params });
    return { success: true, data: response.data, error: null };
  } catch (err) {
    return {
      success: false,
      data: null,
      error: err.response?.data?.detail || err.response?.data?.error || err.message || 'Failed to fetch analytics',
    };
  }
}

export async function getAdminAuditLogs(params = {}) {
  try {
    const response = await apiClient.get('/api/admin/audit-logs', { params });
    return { success: true, data: response.data, error: null };
  } catch (err) {
    return {
      success: false,
      data: null,
      error: err.response?.data?.detail || err.response?.data?.error || err.message || 'Failed to fetch audit logs',
    };
  }
}

export async function reprocessDocument(documentId) {
  try {
    const response = await apiClient.post(`/api/admin/documents/${documentId}/reprocess`);
    return { success: true, data: response.data, error: null };
  } catch (err) {
    return {
      success: false,
      data: null,
      error: err.response?.data?.detail || err.response?.data?.error || err.message || 'Failed to reprocess document',
    };
  }
}

export async function rebuildKnowledgeBaseAdmin() {
  try {
    const response = await apiClient.post('/api/admin/knowledge-base/rebuild');
    return { success: true, data: response.data, error: null };
  } catch (err) {
    return {
      success: false,
      data: null,
      isConflict: err.response?.status === 409,
      error: err.response?.data?.detail || err.response?.data?.message || err.message || 'Failed to rebuild knowledge base',
    };
  }
}

export async function getAdminEvaluation() {
  try {
    const response = await apiClient.get('/api/admin/evaluation');
    return { success: true, data: response.data, error: null };
  } catch (err) {
    return {
      success: false,
      data: null,
      error: err.response?.data?.detail || err.response?.data?.error || err.message || 'Failed to fetch evaluation metrics',
    };
  }
}

export default apiClient;
