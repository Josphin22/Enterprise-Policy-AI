import React, { useState, useRef, useEffect } from 'react';
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
  RotateCw,
  FileText,
  HelpCircle,
  ExternalLink,
} from 'lucide-react';
import ChatInput from './ChatInput';
import { sendFeedback } from '../services/api';

const DEFAULT_SUGGESTIONS = [
  "How many annual leave days are allowed?",
  "What is the work-from-home policy?",
  "What are the core working hours?",
  "What is the sick leave policy?",
];

const EMPTY_STATE_TAGS = [
  { label: "Annual Leave", query: "How many annual leave days are allowed and how to apply?" },
  { label: "WFH Policy", query: "What is the work-from-home policy and eligibility rules?" },
  { label: "Attendance Rules", query: "What are the core working hours and attendance rules?" },
  { label: "Working Hours", query: "What are the standard office hours and shift timings?" },
];

/**
 * Lightweight, safe Markdown renderer for enterprise policy responses.
 * Formats:
 * - Bold: **text** or __text__
 * - Italic: *text* or _text_
 * - Inline code: `code`
 * - Code blocks: ```language ... ```
 * - Unordered lists: - item or * item
 * - Ordered lists: 1. item
 * - Tables: | Header | Header | ...
 * - Paragraphs
 */
function MarkdownContent({ text }) {
  if (!text) return null;

  // Split into line-based blocks
  const lines = text.split('\n');
  const blocks = [];
  let currentList = null;
  let currentTable = null;
  let inCodeBlock = false;
  let codeBlockContent = [];
  let codeBlockLang = '';

  const renderInline = (str) => {
    if (!str) return '';
    // Format code
    let parts = str.split(/(`[^`]+`)/g);
    return parts.map((part, i) => {
      if (part.startsWith('`') && part.endsWith('`') && part.length > 1) {
        return (
          <code key={i} className="inline-code-badge">
            {part.slice(1, -1)}
          </code>
        );
      }

      // Format bold and italics
      const boldParts = part.split(/(\*\*[^*]+\*\*|__[^_]+__)/g);
      return boldParts.map((bPart, j) => {
        if ((bPart.startsWith('**') && bPart.endsWith('**')) || (bPart.startsWith('__') && bPart.endsWith('__'))) {
          return <strong key={`${i}-${j}`}>{bPart.slice(2, -2)}</strong>;
        }
        const italicParts = bPart.split(/(\*[^*]+\*|_[^_]+_)/g);
        return italicParts.map((iPart, k) => {
          if ((iPart.startsWith('*') && iPart.endsWith('*')) || (iPart.startsWith('_') && iPart.endsWith('_'))) {
            return <em key={`${i}-${j}-${k}`}>{iPart.slice(1, -1)}</em>;
          }
          return iPart;
        });
      });
    });
  };

  const flushList = () => {
    if (currentList) {
      if (currentList.type === 'ul') {
        blocks.push(
          <ul key={`ul-${blocks.length}`} className="markdown-ul">
            {currentList.items.map((item, idx) => (
              <li key={idx}>{renderInline(item)}</li>
            ))}
          </ul>
        );
      } else {
        blocks.push(
          <ol key={`ol-${blocks.length}`} className="markdown-ol">
            {currentList.items.map((item, idx) => (
              <li key={idx}>{renderInline(item)}</li>
            ))}
          </ol>
        );
      }
      currentList = null;
    }
  };

  const flushTable = () => {
    if (currentTable) {
      blocks.push(
        <div key={`table-wrapper-${blocks.length}`} className="markdown-table-wrapper">
          <table className="markdown-table">
            {currentTable.headers.length > 0 && (
              <thead>
                <tr>
                  {currentTable.headers.map((h, idx) => (
                    <th key={idx}>{renderInline(h.trim())}</th>
                  ))}
                </tr>
              </thead>
            )}
            <tbody>
              {currentTable.rows.map((row, rIdx) => (
                <tr key={rIdx}>
                  {row.map((cell, cIdx) => (
                    <td key={cIdx}>{renderInline(cell.trim())}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
      currentTable = null;
    }
  };

  lines.forEach((line, lineIdx) => {
    const trimmed = line.trim();

    // Code block toggle
    if (trimmed.startsWith('```')) {
      if (inCodeBlock) {
        blocks.push(
          <div key={`code-${blocks.length}`} className="markdown-code-block">
            {codeBlockLang && <div className="code-block-lang">{codeBlockLang}</div>}
            <pre>
              <code>{codeBlockContent.join('\n')}</code>
            </pre>
          </div>
        );
        inCodeBlock = false;
        codeBlockContent = [];
        codeBlockLang = '';
      } else {
        flushList();
        flushTable();
        inCodeBlock = true;
        codeBlockLang = trimmed.slice(3).trim();
      }
      return;
    }

    if (inCodeBlock) {
      codeBlockContent.push(line);
      return;
    }

    // Table line
    if (trimmed.startsWith('|') && trimmed.endsWith('|') && trimmed.length > 2) {
      flushList();
      const cells = trimmed
        .slice(1, -1)
        .split('|')
        .map((c) => c.trim());

      // Check if it's separator row (e.g. |---|---|)
      if (cells.every((c) => /^:?-+:?$/.test(c))) {
        return;
      }

      if (!currentTable) {
        currentTable = { headers: cells, rows: [] };
      } else {
        currentTable.rows.push(cells);
      }
      return;
    } else {
      flushTable();
    }

    // Unordered list item
    const ulMatch = line.match(/^(\s*)[-*+]\s+(.*)$/);
    if (ulMatch) {
      if (!currentList || currentList.type !== 'ul') {
        flushList();
        currentList = { type: 'ul', items: [ulMatch[2]] };
      } else {
        currentList.items.push(ulMatch[2]);
      }
      return;
    }

    // Ordered list item
    const olMatch = line.match(/^(\s*)\d+\.\s+(.*)$/);
    if (olMatch) {
      if (!currentList || currentList.type !== 'ol') {
        flushList();
        currentList = { type: 'ol', items: [olMatch[2]] };
      } else {
        currentList.items.push(olMatch[2]);
      }
      return;
    }

    // Not a list item
    flushList();

    if (!trimmed) {
      return; // Skip empty lines
    }

    // Heading tags (### or ## or #)
    if (trimmed.startsWith('### ')) {
      blocks.push(<h5 key={`h5-${lineIdx}`} className="markdown-h3">{renderInline(trimmed.slice(4))}</h5>);
      return;
    }
    if (trimmed.startsWith('## ')) {
      blocks.push(<h4 key={`h4-${lineIdx}`} className="markdown-h2">{renderInline(trimmed.slice(3))}</h4>);
      return;
    }
    if (trimmed.startsWith('# ')) {
      blocks.push(<h3 key={`h3-${lineIdx}`} className="markdown-h1">{renderInline(trimmed.slice(2))}</h3>);
      return;
    }

    // Standard paragraph
    blocks.push(
      <p key={`p-${lineIdx}`} className="markdown-p">
        {renderInline(line)}
      </p>
    );
  });

  flushList();
  flushTable();

  return <div className="markdown-container">{blocks}</div>;
}

export default function ChatWindow({
  messages = [],
  loading = false,
  onClearMessages,
  onSendQuery,
  onSelectPrompt,
  onRegenerate,
  language = 'en',
  onLanguageChange,
}) {
  const [copiedId, setCopiedId] = useState(null);
  const [feedbackState, setFeedbackState] = useState({});
  const messagesEndRef = useRef(null);

  // Auto-scroll strictly to the bottom of message list on new messages or loading change
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, loading]);

  const handleCopy = (id, text) => {
    if (!text) return;
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

  // Find last user message for regeneration
  const getLastUserQuestion = (currentIndex) => {
    for (let i = currentIndex - 1; i >= 0; i--) {
      if (messages[i].sender === 'user') {
        return messages[i].text;
      }
    }
    return null;
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
            <h3>Enterprise AI Assistant</h3>
            <p>Instant answers verified against your company documents</p>
          </div>
        </div>

        <div className="chat-header-badge">
          <span className="grounded-badge-header">
            <ShieldCheck size={14} className="text-emerald" />
            <span>RAG Document-Grounded</span>
          </span>
        </div>
      </div>

      {/* Messages / Discussion Viewport */}
      <div className="chat-messages-viewport">
        {messages.length === 0 ? (
          <div className="chat-empty-welcome">
            <div className="welcome-icon-box">
              <Sparkles size={32} />
            </div>
            <h4>🤖 Enterprise AI Assistant</h4>
            <p className="welcome-desc">
              Ask questions about your company's policies and documents.
            </p>

            {/* Empty State Tag Pills */}
            <div className="empty-state-suggested-section">
              <span className="suggestions-label">Suggested questions:</span>
              <div className="empty-state-tags-grid">
                {EMPTY_STATE_TAGS.map((tag, idx) => (
                  <button
                    key={idx}
                    type="button"
                    className="empty-tag-btn"
                    onClick={() => onSendQuery && onSendQuery(tag.query)}
                  >
                    <span>[ {tag.label} ]</span>
                  </button>
                ))}
              </div>
            </div>

            <div className="chat-status-callout">
              <ShieldCheck size={18} className="text-emerald" />
              <div>
                <strong>Local Privacy & RAG Verification:</strong> Answers are grounded strictly in your uploaded policies without external API leaks.
              </div>
            </div>
          </div>
        ) : (
          <div className="messages-list">
            {messages.map((msg, index) => {
              const isUser = msg.sender === 'user';
              const messageKey = msg.id || `msg-${index}`;
              const previousUserQuestion = !isUser ? getLastUserQuestion(index) : null;
              const hasRefusal =
                msg.status === 'insufficient_context' ||
                (msg.answer && msg.answer.toLowerCase().includes('could not find sufficient information'));

              return (
                <div
                  key={messageKey}
                  className={`message-row ${isUser ? 'message-user' : 'message-assistant'}`}
                >
                  {/* Sender Avatar */}
                  <div className="message-avatar">
                    {isUser ? (
                      <div className="avatar-icon user-avatar-bg">
                        <User size={16} />
                      </div>
                    ) : (
                      <div className="avatar-icon bot-avatar-bg">
                        <Bot size={16} />
                      </div>
                    )}
                  </div>

                  <div className="message-bubble">
                    <div className="message-sender-name">
                      {isUser ? 'You' : 'Enterprise AI Assistant'}
                    </div>

                    {isUser ? (
                      <div className="message-content user-message-content">{msg.text}</div>
                    ) : msg.status === 'error' || msg.status === 'generation_error' ? (
                      <div className="chat-error-card">
                        <div className="error-card-header">
                          <AlertTriangle size={16} className="text-danger" />
                          <strong>Service Notice</strong>
                        </div>
                        <p className="error-card-desc">
                          ⚠ Unable to connect to the AI service. Please try again.
                        </p>
                      </div>
                    ) : (
                      <div className="generated-answer-container">
                        {/* 5. Grounding Indicator Badge */}
                        <div className="grounding-status-container">
                          {hasRefusal ? (
                            <div className="grounding-indicator warning-indicator">
                              <AlertTriangle size={14} className="text-amber" />
                              <span>⚠ Information not found in company documents</span>
                            </div>
                          ) : (
                            <div className="grounding-indicator success-indicator">
                              <Check size={14} className="text-emerald" />
                              <span>✓ Grounded in company documents</span>
                              <span className="grounding-divider">•</span>
                              <span className="grounding-confidence">
                                Confidence: {msg.confidence || (msg.grounding_warning ? 'Low' : 'High')}
                              </span>
                            </div>
                          )}
                        </div>

                        {/* 2. Formatted Markdown AI Answer */}
                        <div className="ai-answer-body">
                          <MarkdownContent text={msg.answer || msg.text || msg.message} />
                        </div>

                        {/* 4. Source Citations Section */}
                        {msg.sources && msg.sources.length > 0 && !hasRefusal && (
                          <div className="ai-sources-section">
                            <div className="sources-section-title">
                              <BookOpen size={13} className="text-emerald" />
                              <span>Sources</span>
                            </div>

                            <div className="source-cards-grid">
                              {msg.sources.map((src, sIdx) => {
                                const docName = src.document || src.filename || 'Policy Document';
                                const pageNum = src.page || src.page_number;
                                const sectionName = src.section;

                                return (
                                  <div key={sIdx} className="rag-source-card" title={src.preview || ''}>
                                    <div className="rag-source-icon">
                                      <FileText size={14} className="text-mint" />
                                    </div>
                                    <div className="rag-source-info">
                                      <span className="rag-source-filename">{docName}</span>
                                      <span className="rag-source-meta">
                                        {pageNum ? `Page ${pageNum}` : 'Document Excerpt'}
                                        {sectionName ? ` • ${sectionName}` : ''}
                                      </span>
                                    </div>
                                  </div>
                                );
                              })}
                            </div>
                          </div>
                        )}

                        {/* 3. AI Response Actions: Helpful, Not helpful, Copy, Regenerate */}
                        <div className="ai-response-action-bar">
                          <div className="action-buttons-left">
                            <button
                              type="button"
                              className={`response-action-btn ${feedbackState[msg.assistant_message_id || msg.id] === 'positive' ? 'action-active' : ''}`}
                              title="Helpful"
                              onClick={() => handleFeedback(msg.assistant_message_id || msg.id, 'positive')}
                              aria-label="Thumbs up helpful"
                            >
                              <ThumbsUp size={13} />
                              <span>Helpful</span>
                            </button>

                            <button
                              type="button"
                              className={`response-action-btn ${feedbackState[msg.assistant_message_id || msg.id] === 'negative' ? 'action-active-danger' : ''}`}
                              title="Not helpful"
                              onClick={() => handleFeedback(msg.assistant_message_id || msg.id, 'negative')}
                              aria-label="Thumbs down not helpful"
                            >
                              <ThumbsDown size={13} />
                              <span>Not helpful</span>
                            </button>

                            <button
                              type="button"
                              className="response-action-btn"
                              title="Copy Answer"
                              onClick={() => handleCopy(messageKey, msg.answer || msg.text)}
                              aria-label="Copy answer to clipboard"
                            >
                              {copiedId === messageKey ? (
                                <>
                                  <Check size={13} className="text-emerald" />
                                  <span className="text-emerald">Copied!</span>
                                </>
                              ) : (
                                <>
                                  <Copy size={13} />
                                  <span>Copy</span>
                                </>
                              )}
                            </button>

                            {previousUserQuestion && (
                              <button
                                type="button"
                                className="response-action-btn"
                                title="Regenerate answer with the same question"
                                onClick={() => onRegenerate && onRegenerate(previousUserQuestion)}
                                disabled={loading}
                                aria-label="Regenerate answer"
                              >
                                <RotateCw size={13} className={loading ? 'animate-spin' : ''} />
                                <span>Regenerate</span>
                              </button>
                            )}
                          </div>
                        </div>
                      </div>
                    )}

                    <div className="message-timestamp">{msg.time}</div>
                  </div>
                </div>
              );
            })}

            {/* 10. Typing / Loading State */}
            {loading && (
              <div className="message-row message-assistant" aria-live="polite">
                <div className="message-avatar">
                  <div className="avatar-icon bot-avatar-bg">
                    <Bot size={16} />
                  </div>
                </div>
                <div className="message-bubble loading-bubble">
                  <div className="typing-indicator-wrapper">
                    <span className="thinking-robot-label">🤖 AI Assistant is thinking...</span>
                    <div className="typing-dots-animation">
                      <span className="typing-dot" />
                      <span className="typing-dot" />
                      <span className="typing-dot" />
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Scroll Anchor */}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* 1. Suggested Questions Chips Bar (Displayed above Chat Input) */}
      <div className="chat-suggestions-bar" aria-label="Suggested Questions">
        <span className="suggestions-prefix-label">Suggested:</span>
        <div className="suggestions-chips-row">
          {DEFAULT_SUGGESTIONS.map((suggestion, idx) => (
            <button
              key={idx}
              type="button"
              className="suggestion-chip-btn"
              onClick={() => onSendQuery && onSendQuery(suggestion)}
              disabled={loading}
              title={`Ask: "${suggestion}"`}
            >
              <MessageSquare size={12} className="text-mint" />
              <span>{suggestion}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Chat Input Bar */}
      <ChatInput
        onClear={onClearMessages}
        onSendQuery={onSendQuery}
        disabled={loading}
        loading={loading}
        language={language}
        onLanguageChange={onLanguageChange}
      />
    </div>
  );
}
