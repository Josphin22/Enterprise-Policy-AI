import React, { useState, useEffect } from 'react';
import ChatWindow from '../components/ChatWindow';
import SourceCard from '../components/SourceCard';
import {
  sendChatMessage,
  getChatSessions,
  createChatSession,
  getChatHistory,
  renameConversation,
  deleteConversation,
  getLLMStatus,
  getDocuments,
  getOllamaHealth,
} from '../services/api';
import {
  BookOpen,
  Plus,
  MessageSquare,
  Cpu,
  CheckCircle2,
  FileText,
  Filter,
  Search,
  Edit2,
  Trash2,
  Check,
  X,
} from 'lucide-react';

export default function Assistant() {
  const [messages, setMessages] = useState([]);
  const [sources, setSources] = useState([]);
  const [retrievalStatus, setRetrievalStatus] = useState('idle');
  const [loading, setLoading] = useState(false);
  const [sessions, setSessions] = useState([]);
  const [currentSessionId, setCurrentSessionId] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [editingSessionId, setEditingSessionId] = useState(null);
  const [editTitle, setEditTitle] = useState('');
  const [llmStatus, setLlmStatus] = useState(null);
  const [ollamaHealth, setOllamaHealth] = useState(null);
  const [documents, setDocuments] = useState([]);
  const [selectedDocumentId, setSelectedDocumentId] = useState('');
  const [language, setLanguage] = useState('en');

  // Load sessions, documents, and LLM status on mount
  useEffect(() => {
    loadSessions();
    checkLLM();
    loadDocuments();
  }, []);

  const checkLLM = async () => {
    try {
      const [res, healthRes] = await Promise.all([
        getLLMStatus(),
        getOllamaHealth(),
      ]);
      if (res.success) {
        setLlmStatus(res.data);
      }
      if (healthRes.success) {
        setOllamaHealth(healthRes.data);
      }
    } catch (e) {
      console.warn("LLM check error:", e);
    }
  };

  const loadDocuments = async () => {
    try {
      const res = await getDocuments();
      if (res.success && res.documents) {
        setDocuments(res.documents);
      }
    } catch (e) {
      console.warn("Error loading documents:", e);
    }
  };

  const loadSessions = async (search = searchQuery) => {
    try {
      const res = await getChatSessions(search);
      if (res.success) {
        setSessions(res.sessions || []);
      }
    } catch (e) {
      console.warn("Error loading sessions:", e);
    }
  };

  const handleSearchChange = (e) => {
    const val = e.target.value;
    setSearchQuery(val);
    loadSessions(val);
  };

  const handleCreateNewSession = async () => {
    try {
      const title = `Policy Discussion ${new Date().toLocaleDateString()} ${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
      const res = await createChatSession(title);
      if (res.success && res.session_id) {
        setCurrentSessionId(res.session_id);
        setMessages([]);
        setSources([]);
        setRetrievalStatus('idle');
        loadSessions();
      }
    } catch (e) {
      console.warn("Error creating new session:", e);
    }
  };

  const handleSelectSession = async (sessionId) => {
    if (editingSessionId) return; // Ignore selection while renaming
    setCurrentSessionId(sessionId);
    setLoading(true);
    try {
      const histRes = await getChatHistory(sessionId);
      if (histRes.success && histRes.history) {
        const loadedMessages = histRes.history.map((h, i) => ({
          id: h.id || `msg-${i}`,
          assistant_message_id: h.id,
          sender: h.role,
          text: h.content,
          answer: h.content,
          sources: h.sources || [],
          time: h.created_at ? new Date(h.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '',
        }));
        setMessages(loadedMessages);

        // Populate sources from the last assistant message if present
        const lastAssistant = [...loadedMessages].reverse().find(m => m.sender === 'assistant' && m.sources && m.sources.length > 0);
        if (lastAssistant) {
          setSources(lastAssistant.sources);
          setRetrievalStatus('success');
        } else {
          setSources([]);
          setRetrievalStatus('idle');
        }
      }
    } catch (e) {
      console.warn("Error loading session history:", e);
    } finally {
      setLoading(false);
    }
  };

  const startRenameSession = (e, session) => {
    e.stopPropagation();
    setEditingSessionId(session.id || session.session_id);
    setEditTitle(session.title || '');
  };

  const saveRenameSession = async (e, sessionId) => {
    e.stopPropagation();
    if (!editTitle.trim()) {
      setEditingSessionId(null);
      return;
    }
    try {
      const res = await renameConversation(sessionId, editTitle.trim());
      if (res.success) {
        setSessions(prev => prev.map(s => (s.id || s.session_id) === sessionId ? { ...s, title: editTitle.trim() } : s));
      }
    } catch (err) {
      console.error("Failed to rename conversation:", err);
    } finally {
      setEditingSessionId(null);
    }
  };

  const cancelRename = (e) => {
    e.stopPropagation();
    setEditingSessionId(null);
    setEditTitle('');
  };

  const handleDeleteSession = async (e, sessionId) => {
    e.stopPropagation();
    if (!window.confirm("Are you sure you want to delete this conversation? All messages will be permanently removed.")) {
      return;
    }
    try {
      const res = await deleteConversation(sessionId);
      if (res.success) {
        setSessions(prev => prev.filter(s => (s.id || s.session_id) !== sessionId));
        if (currentSessionId === sessionId) {
          setCurrentSessionId(null);
          setMessages([]);
          setSources([]);
          setRetrievalStatus('idle');
        }
      }
    } catch (err) {
      console.error("Failed to delete conversation:", err);
    }
  };

  const handleClearMessages = () => {
    setMessages([]);
    setSources([]);
    setRetrievalStatus('idle');
  };

  const handleSendQuery = async (queryText) => {
    if (!queryText || !queryText.trim()) return;

    const userMessage = {
      id: `user-${Date.now()}`,
      sender: 'user',
      text: queryText.trim(),
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((prev) => [...prev, userMessage]);
    setLoading(true);

    try {
      const chatRes = await sendChatMessage(queryText.trim(), currentSessionId, 8, selectedDocumentId || null, language);

      if (chatRes.session_id && !currentSessionId) {
        setCurrentSessionId(chatRes.session_id);
        loadSessions();
      }

      if (chatRes.success && (chatRes.status === 'success' || chatRes.answer)) {
        const assistantMessage = {
          id: `asst-${Date.now()}`,
          assistant_message_id: chatRes.assistant_message_id || chatRes.message_id,
          sender: 'assistant',
          status: chatRes.status,
          answer: chatRes.answer,
          text: chatRes.answer,
          context: chatRes.context,
          sources: chatRes.sources || [],
          confidence: chatRes.confidence || (chatRes.grounding_warning ? 'Low' : 'High'),
          grounding_classification: chatRes.grounding_classification || 'SUPPORTED',
          grounding_warning: chatRes.grounding_warning || false,
          language: chatRes.language || language,
          retrieval_duration_ms: chatRes.retrieval_duration_ms,
          llm_duration_ms: chatRes.llm_duration_ms,
          total_duration_ms: chatRes.total_duration_ms,
          time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        };

        setMessages((prev) => [...prev, assistantMessage]);
        setSources(chatRes.sources || []);
        setRetrievalStatus('success');
      } else if (chatRes.status === 'insufficient_context') {
        const assistantMessage = {
          id: `asst-${Date.now()}`,
          sender: 'assistant',
          status: 'insufficient_context',
          message: chatRes.answer || chatRes.message || 'I could not find sufficient information in the provided enterprise documents to answer this question.',
          text: chatRes.answer || chatRes.message,
          sources: [],
          time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        };

        setMessages((prev) => [...prev, assistantMessage]);
        setSources([]);
        setRetrievalStatus('insufficient_context');
      } else {
        const userFriendlyError = (chatRes.message || chatRes.error || '').toLowerCase();
        let displayError = 'The AI service is temporarily unavailable. Please try again.';
        if (userFriendlyError.includes('ollama') || userFriendlyError.includes('connection refused') || userFriendlyError.includes('timeout')) {
          displayError = 'The local AI reasoning service (Ollama) is temporarily unavailable. Please verify the background model runner is active and try again.';
        } else if (userFriendlyError.includes('vector') || userFriendlyError.includes('faiss')) {
          displayError = 'The vector knowledge base is not built or undergoing indexing. Please rebuild the knowledge base in the Knowledge Base tab.';
        } else if (chatRes.message || chatRes.error) {
          displayError = typeof chatRes.message === 'string' ? chatRes.message : 'The AI service encountered an unexpected issue while formulating the answer. Please try again.';
        }

        const fallbackMessage = {
          id: `asst-${Date.now()}`,
          sender: 'assistant',
          status: chatRes.status || 'error',
          message: displayError,
          text: displayError,
          context: chatRes.context || '',
          sources: chatRes.sources || [],
          time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        };

        setMessages((prev) => [...prev, fallbackMessage]);
        setSources(chatRes.sources || []);
        setRetrievalStatus(chatRes.status || 'error');
      }
    } catch (err) {
      const errorMessage = {
        id: `asst-${Date.now()}`,
        sender: 'assistant',
        status: 'error',
        message: 'The AI service is temporarily unavailable. Please verify the backend connection and try again.',
        text: 'The AI service is temporarily unavailable. Please verify the backend connection and try again.',
        sources: [],
        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      setMessages((prev) => [...prev, errorMessage]);
      setSources([]);
      setRetrievalStatus('error');
    } finally {
      setLoading(false);
      // Refresh session list to reflect auto-generated titles
      loadSessions();
    }
  };

  const handleSelectPrompt = (promptText) => {
    handleSendQuery(promptText);
  };

  return (
    <div className="assistant-page-container">
      {/* Page Header */}
      <div className="page-header-intro">
        <div className="header-text-block">
          <h1 className="page-main-heading">AI Assistant</h1>
          <p className="page-sub-heading">
            Ask questions directly regarding your company policies and guidelines.
          </p>
        </div>

        {/* Sessions & Document Filtering Controls */}
        <div className="header-actions-group">
          {documents.length > 0 && (
            <div className="document-filter-control" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', background: 'rgba(255, 255, 255, 0.05)', padding: '0.4rem 0.8rem', borderRadius: '8px', border: '1px solid rgba(255, 255, 255, 0.1)' }}>
              <Filter size={14} className="text-cyan" />
              <select
                value={selectedDocumentId}
                onChange={(e) => setSelectedDocumentId(e.target.value)}
                style={{ background: 'transparent', color: '#e2e8f0', border: 'none', outline: 'none', fontSize: '0.85rem', cursor: 'pointer' }}
                title="Filter retrieval to a specific document"
              >
                <option value="" style={{ background: '#1e293b', color: '#e2e8f0' }}>All Knowledge Base Documents</option>
                {documents.map((d) => (
                  <option key={d.id} value={d.id} style={{ background: '#1e293b', color: '#e2e8f0' }}>
                    {d.original_filename || d.filename}
                  </option>
                ))}
              </select>
            </div>
          )}

          <button
            type="button"
            className="btn-action-primary"
            onClick={handleCreateNewSession}
          >
            <Plus size={16} />
            <span>New Chat</span>
          </button>
        </div>
      </div>

      {/* Main Assistant Split Layout */}
      <div className="assistant-layout-grid">
        {/* Left Sidebar: Conversations History with Search & Actions */}
        <div className="assistant-sessions-sidebar">
          <div className="sidebar-header" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <MessageSquare size={16} className="text-cyan" />
              <h4 style={{ margin: 0, fontSize: '0.9rem', color: '#fff', fontWeight: 600 }}>Conversations</h4>
            </div>
            <span style={{ fontSize: '0.72rem', color: '#94a3b8', background: 'rgba(255,255,255,0.06)', padding: '1px 6px', borderRadius: '4px' }}>
              {sessions.length}
            </span>
          </div>

          {/* Search Input Filter */}
          <div className="sidebar-search-box">
            <Search size={13} className="sidebar-search-icon" />
            <input
              type="text"
              placeholder="Search conversations..."
              className="sidebar-search-input"
              value={searchQuery}
              onChange={handleSearchChange}
            />
          </div>

          {/* Scrollable Conversation List */}
          <div className="sessions-list-scroll">
            {sessions.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '1.5rem 0.5rem', color: '#64748b', fontSize: '0.8rem' }} role="status">
                {searchQuery ? 'No matching conversations' : 'Start a conversation with your policy assistant.'}
              </div>
            ) : (
              sessions.map((s) => {
                const sId = s.id || s.session_id;
                const isActive = sId === currentSessionId;
                const isEditing = editingSessionId === sId;

                return (
                  <div
                    key={sId}
                    className={`session-item-row ${isActive ? 'active' : ''}`}
                  >
                    {isEditing ? (
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', width: '100%' }}>
                        <input
                          type="text"
                          className="rename-input"
                          value={editTitle}
                          onChange={(e) => setEditTitle(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') saveRenameSession(e, sId);
                            if (e.key === 'Escape') cancelRename(e);
                          }}
                          autoFocus
                        />
                        <button
                          type="button"
                          className="btn-session-action"
                          title="Save Title"
                          onClick={(e) => saveRenameSession(e, sId)}
                        >
                          <Check size={13} className="text-emerald" />
                        </button>
                        <button
                          type="button"
                          className="btn-session-action"
                          title="Cancel"
                          onClick={cancelRename}
                        >
                          <X size={13} />
                        </button>
                      </div>
                    ) : (
                      <>
                        <button
                          type="button"
                          className="session-item-main-btn"
                          onClick={() => handleSelectSession(sId)}
                          title={s.title || 'Policy Discussion'}
                        >
                          <FileText size={13} style={{ flexShrink: 0 }} />
                          <span className="session-title-text">{s.title || 'Policy Discussion'}</span>
                        </button>

                        <div className="session-actions-group">
                          <button
                            type="button"
                            className="btn-session-action"
                            title="Rename Conversation"
                            onClick={(e) => startRenameSession(e, s)}
                          >
                            <Edit2 size={12} />
                          </button>
                          <button
                            type="button"
                            className="btn-session-action delete-action"
                            title="Delete Conversation"
                            onClick={(e) => handleDeleteSession(e, sId)}
                          >
                            <Trash2 size={12} />
                          </button>
                        </div>
                      </>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Center: ChatGPT-style Full Chat Window */}
        <div className="assistant-chat-column" style={{ width: '100%' }}>
          <ChatWindow
            messages={messages}
            loading={loading}
            onClearMessages={handleClearMessages}
            onSendQuery={handleSendQuery}
            onSelectPrompt={handleSelectPrompt}
            onRegenerate={handleSendQuery}
            language={language}
            onLanguageChange={setLanguage}
          />
        </div>
      </div>
    </div>
  );
}
