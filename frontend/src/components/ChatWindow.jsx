import React, { useState } from 'react';
import {
  Bot,
  User,
  Sparkles,
  MessageSquare,
  ShieldCheck,
  BookOpen,
  AlertTriangle,
  Cpu,
  Clock,
  ThumbsUp,
  ThumbsDown,
  Copy,
  Check,
  Info,
} from 'lucide-react';
import ChatInput from './ChatInput';
import { sendFeedback } from '../services/api';

const EXAMPLE_PROMPTS = [
  "How many annual leave days are allowed?",
  "What is the paid sick leave entitlement?",
  "What are the core working hours for attendance?",
  "How many remote days are permitted per week under WFH policy?",
  "What is the population of Mars?", // Irrelevant test prompt for guardrail refusal
];

export default function ChatWindow({
  messages = [],
  loading = false,
  onClearMessages,
  onSendQuery,
  onSelectPrompt,
}) {
  const [copiedId, setCopiedId] = useState(null);
  const [feedbackState, setFeedbackState] = useState({});

  const handleCopy = (id, text) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleFeedback = async (messageId, rating) => {
    if (!messageId) return;
    try {
      await sendFeedback(messageId, rating);
      setFeedbackState((prev) => ({ ...prev, [messageId]: rating }));
    } catch (e) {
      console.error("Feedback error:", e);
    }
  };

  return (
    <div className="chat-window-card">
      {/* Chat Window Header */}
      <div className="chat-window-header">
        <div className="chat-header-title-group">
          <div className="chat-bot-avatar">
            <Bot size={22} />
          </div>
          <div>
            <h3>AI Policy Assistant</h3>
            <p>100% Local RAG Assistant powered by Ollama & FAISS</p>
          </div>
        </div>
        <div className="chat-mode-badge active-rag">
          <span className="dot-pulse"></span>
          <span>Phase 8 RAG Pipeline Live</span>
        </div>
      </div>

      {/* Messages / Discussion Viewport */}
      <div className="chat-messages-viewport">
        {messages.length === 0 ? (
          <div className="chat-empty-welcome">
            <div className="welcome-icon-box">
              <Sparkles size={32} />
            </div>
            <h4>Grounded Enterprise Policy Assistant</h4>
            <p className="welcome-desc">
              Ask any question about company policies, leave entitlements, attendance rules, or remote work guidelines. Answers are generated exclusively from your local enterprise documents with verifiable citations and strict anti-hallucination guardrails.
            </p>

            <div className="prompt-suggestions-container">
              <span className="suggestions-label">Try Example Questions:</span>
              <div className="prompt-chips-grid">
                {EXAMPLE_PROMPTS.map((prompt, idx) => (
                  <button
                    key={idx}
                    type="button"
                    className="prompt-chip"
                    onClick={() => onSelectPrompt && onSelectPrompt(prompt)}
                  >
                    <MessageSquare size={14} />
                    <span>{prompt}</span>
                  </button>
                ))}
              </div>
            </div>

            <div className="chat-status-callout">
              <ShieldCheck size={18} className="text-emerald" />
              <div>
                <strong>Local Privacy & Security:</strong> No external LLM cloud APIs (OpenAI, Gemini, Claude) are contacted. Documents remain strictly on your machine.
              </div>
            </div>
          </div>
        ) : (
          <div className="messages-list">
            {messages.map((msg, index) => (
              <div
                key={msg.id || index}
                className={`message-row ${msg.sender === 'user' ? 'message-user' : 'message-assistant'}`}
              >
                <div className="message-avatar">
                  {msg.sender === 'user' ? <User size={16} /> : <Bot size={16} />}
                </div>
                <div className="message-bubble">
                  <div className="message-sender-name">
                    {msg.sender === 'user' ? 'You' : 'Policy Assistant (Local Ollama)'}
                  </div>

                  {msg.sender === 'user' ? (
                    <div className="message-content">{msg.text}</div>
                  ) : msg.status === 'insufficient_context' ? (
                    <div className="insufficient-context-box">
                      <div className="insufficient-header">
                        <AlertTriangle size={16} className="text-amber" />
                        <strong>Safe Refusal / Insufficient Context</strong>
                      </div>
                      <p className="insufficient-desc">
                        {msg.text || msg.message || 'I could not find sufficient information in the provided enterprise documents to answer this question.'}
                      </p>
                      <div className="insufficient-footer">
                        <span>Threshold: 0.35</span>
                        <span>Hallucination Guardrail Triggered</span>
                        <span>LLM Inference Skipped</span>
                      </div>
                    </div>
                  ) : msg.status === 'llm_unavailable' || msg.status === 'model_not_found' ? (
                    <div className="llm-offline-box">
                      <div className="llm-offline-header">
                        <AlertTriangle size={16} className="text-amber" />
                        <strong>Ollama Service Notice</strong>
                      </div>
                      <p className="llm-offline-desc">
                        {msg.message || 'Local Ollama service is unreachable or the requested model is not downloaded.'}
                      </p>
                      {msg.context && (
                        <div className="retrieved-context-fallback">
                          <span className="fallback-label">Retrieved Grounded Context:</span>
                          <pre className="context-text-pre">{msg.context}</pre>
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="generated-answer-container">
                      {/* Natural Language Grounded Answer */}
                      <div className="ai-answer-body">
                        {msg.answer || msg.text}
                      </div>

                      {/* Source Citation Badges */}
                      {msg.sources && msg.sources.length > 0 && (
                        <div className="message-sources-summary">
                          <span className="summary-label">
                            <BookOpen size={13} className="text-cyan" /> Cited Sources:
                          </span>
                          <div className="source-pill-list">
                            {msg.sources.map((s, i) => (
                              <span key={i} className="source-citation-pill" title={`Score: ${s.score ? Math.round(s.score * 100) : 0}%`}>
                                <strong>[{s.source_id}]</strong> {s.document}
                                {s.page ? ` (p. ${s.page})` : ''}
                                {s.section ? ` · ${s.section}` : ''}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Latency & Hardware Metrics Footer */}
                      <div className="message-metrics-bar">
                        <div className="metrics-group">
                          <Clock size={12} />
                          <span>Total: {msg.total_duration_ms ? `${Math.round(msg.total_duration_ms)}ms` : 'fast'}</span>
                          {msg.retrieval_duration_ms ? (
                            <span className="sub-metric">(RAG: {Math.round(msg.retrieval_duration_ms)}ms | LLM: {Math.round(msg.llm_duration_ms || 0)}ms)</span>
                          ) : null}
                        </div>

                        {/* Action buttons (Copy, Feedback) */}
                        <div className="message-actions-group">
                          <button
                            type="button"
                            className="msg-action-btn"
                            title="Copy Answer"
                            onClick={() => handleCopy(msg.id, msg.answer || msg.text)}
                          >
                            {copiedId === msg.id ? <Check size={13} className="text-emerald" /> : <Copy size={13} />}
                          </button>
                          <button
                            type="button"
                            className={`msg-action-btn ${feedbackState[msg.assistant_message_id || msg.id] === 'positive' ? 'active-positive' : ''}`}
                            title="Helpful Answer"
                            onClick={() => handleFeedback(msg.assistant_message_id || msg.id, 'positive')}
                          >
                            <ThumbsUp size={13} />
                          </button>
                          <button
                            type="button"
                            className={`msg-action-btn ${feedbackState[msg.assistant_message_id || msg.id] === 'negative' ? 'active-negative' : ''}`}
                            title="Unhelpful Answer"
                            onClick={() => handleFeedback(msg.assistant_message_id || msg.id, 'negative')}
                          >
                            <ThumbsDown size={13} />
                          </button>
                        </div>
                      </div>
                    </div>
                  )}

                  <div className="message-timestamp">{msg.time}</div>
                </div>
              </div>
            ))}

            {loading && (
              <div className="message-row message-assistant">
                <div className="message-avatar">
                  <Bot size={16} />
                </div>
                <div className="message-bubble loading-bubble">
                  <div className="retrieval-spinner-group">
                    <span className="dot-spinner"></span>
                    <span>Retrieving context & generating answer with local Ollama LLM...</span>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Chat Input Bar */}
      <ChatInput
        onClear={onClearMessages}
        onSendQuery={onSendQuery}
        disabled={loading}
        loading={loading}
      />
    </div>
  );
}
