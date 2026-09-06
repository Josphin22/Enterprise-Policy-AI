import React, { useState, useEffect } from 'react';
import ChatWindow from '../components/ChatWindow';
import SourceCard from '../components/SourceCard';
import {
  sendChatMessage,
  getChatSessions,
  createChatSession,
  getChatHistory,
  getLLMStatus,
} from '../services/api';
import {
  Bot,
  Shield,
  BookOpen,
  Plus,
  MessageSquare,
  Cpu,
  Layers,
  CheckCircle2,
  AlertCircle,
  FileText,
} from 'lucide-react';

export default function Assistant() {
  const [messages, setMessages] = useState([]);
  const [sources, setSources] = useState([]);
  const [retrievalStatus, setRetrievalStatus] = useState('idle');
  const [loading, setLoading] = useState(false);
  const [sessions, setSessions] = useState([]);
  const [currentSessionId, setCurrentSessionId] = useState(null);
  const [llmStatus, setLlmStatus] = useState(null);

  // Load sessions and LLM status on mount
  useEffect(() => {
    loadSessions();
    checkLLM();
  }, []);

  const checkLLM = async () => {
    try {
      const res = await getLLMStatus();
      if (res.success) {
        setLlmStatus(res.data);
      }
    } catch (e) {
      console.warn("LLM check error:", e);
    }
  };

  const loadSessions = async () => {
    try {
      const res = await getChatSessions();
      if (res.success && res.sessions.length > 0) {
        setSessions(res.sessions);
      }
    } catch (e) {
      console.warn("Error loading sessions:", e);
    }
  };

  const handleCreateNewSession = async () => {
    try {
      const title = `Policy Session ${new Date().toLocaleDateString()} ${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
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
    setCurrentSessionId(sessionId);
    setLoading(true);
    try {
      const histRes = await getChatHistory(sessionId);
      if (histRes.success && histRes.history) {
        const loadedMessages = histRes.history.map((h, i) => ({
          id: h.id || `msg-${i}`,
          sender: h.role,
          text: h.content,
          answer: h.content,
          time: h.created_at ? new Date(h.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '',
        }));
        setMessages(loadedMessages);
      }
    } catch (e) {
      console.warn("Error loading session history:", e);
    } finally {
      setLoading(false);
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
      const chatRes = await sendChatMessage(queryText.trim(), currentSessionId, 5);

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
        const fallbackMessage = {
          id: `asst-${Date.now()}`,
          sender: 'assistant',
          status: chatRes.status || 'error',
          message: chatRes.message || chatRes.error || 'Unable to generate an answer at this time.',
          text: chatRes.message || chatRes.error || 'Generation error',
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
        message: err.message || 'Network error communicating with the assistant service.',
        text: 'Error connecting to local RAG service.',
        sources: [],
        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      setMessages((prev) => [...prev, errorMessage]);
      setSources([]);
      setRetrievalStatus('error');
    } finally {
      setLoading(false);
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
          <h1 className="page-main-heading">AI Policy Assistant</h1>
          <p className="page-sub-heading">
            Grounded enterprise question answering powered by local Ollama LLM and FAISS semantic retrieval.
          </p>
        </div>

        {/* Sessions & LLM Status Controls */}
        <div className="header-actions-group">
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
        {/* Left Sidebar: Active Sessions */}
        {sessions.length > 0 && (
          <div className="assistant-sessions-sidebar">
            <div className="sidebar-header">
              <MessageSquare size={16} className="text-cyan" />
              <h4>Conversations</h4>
            </div>
            <div className="sessions-list-scroll">
              {sessions.map((s) => (
                <button
                  key={s.id || s.session_id}
                  type="button"
                  className={`session-item-btn ${(s.id || s.session_id) === currentSessionId ? 'active' : ''}`}
                  onClick={() => handleSelectSession(s.id || s.session_id)}
                >
                  <FileText size={14} />
                  <span className="session-title-text">{s.title || 'Policy Discussion'}</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Center: Chat Window */}
        <div className="assistant-chat-column">
          <ChatWindow
            messages={messages}
            loading={loading}
            onClearMessages={handleClearMessages}
            onSendQuery={handleSendQuery}
            onSelectPrompt={handleSelectPrompt}
          />
        </div>

        {/* Right Sidebar: Source Citations & Security Guardrails */}
        <div className="assistant-sidebar-column">
          <div className="assistant-panel-card">
            <div className="panel-card-header">
              <BookOpen size={18} className="text-cyan" />
              <h4>Document Citations</h4>
            </div>
            <p className="panel-card-desc">
              Authoritative document chunks retrieved from FAISS used to ground the LLM answer.
            </p>

            <SourceCard sources={sources} status={retrievalStatus} />
          </div>

          <div className="assistant-panel-card">
            <div className="panel-card-header">
              <Cpu size={18} className="text-indigo" />
              <h4>Local LLM Architecture</h4>
            </div>
            <ul className="grounded-features-list">
              <li>
                <CheckCircle2 size={15} className="text-emerald inline-icon" />
                <strong>Local LLM:</strong> {llmStatus?.model || 'llama3.2:3b'} (Ollama)
              </li>
              <li>
                <CheckCircle2 size={15} className="text-emerald inline-icon" />
                <strong>Embedding:</strong> all-MiniLM-L6-v2 (384-dim)
              </li>
              <li>
                <CheckCircle2 size={15} className="text-emerald inline-icon" />
                <strong>Anti-Hallucination:</strong> Insufficient context safe refusal active.
              </li>
              <li>
                <CheckCircle2 size={15} className="text-emerald inline-icon" />
                <strong>Untrusted Context Defense:</strong> Document text framed strictly as reference DATA.
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
