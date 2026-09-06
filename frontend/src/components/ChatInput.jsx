import React, { useState } from 'react';
import { Send, Trash2, Sparkles } from 'lucide-react';

export default function ChatInput({ onClear, onSendQuery, disabled = false, loading = false }) {
  const [query, setQuery] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!query.trim() || disabled || loading) return;
    if (onSendQuery) {
      onSendQuery(query.trim());
      setQuery('');
    }
  };

  return (
    <div className="chat-input-wrapper">
      <div className="chat-phase-notice" role="note">
        <Sparkles size={14} className="text-cyan" />
        <span>
          <strong>Phase 7 Active:</strong> RAG Retrieval Engine & Context Construction enabled. Ask questions to test local semantic retrieval and grounded context assembly.
        </span>
      </div>

      <form onSubmit={handleSubmit} className="chat-form">
        <button
          type="button"
          className="btn-chat-clear"
          onClick={onClear}
          title="Clear conversation"
          aria-label="Clear conversation history"
        >
          <Trash2 size={16} />
          <span>Clear</span>
        </button>

        <div className="input-group-main">
          <input
            type="text"
            className="chat-text-input"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Ask an enterprise policy question (e.g. 'How many annual leave days are allowed?')..."
            aria-label="Enterprise policy question"
            disabled={disabled || loading}
          />
          <button
            type="submit"
            className="btn-chat-send"
            disabled={disabled || loading || !query.trim()}
            title="Retrieve grounded context"
            aria-label="Send question"
          >
            <Send size={16} />
            <span>{loading ? 'Retrieving...' : 'Retrieve Context'}</span>
          </button>
        </div>
      </form>
    </div>
  );
}
