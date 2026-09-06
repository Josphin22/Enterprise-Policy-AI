import React, { useState, useEffect, useCallback } from 'react';
import { Search, History, MessageSquare, Calendar, RefreshCw, Inbox } from 'lucide-react';
import { getChatHistory } from '../services/api';

export default function ChatHistory() {
  const [searchQuery, setSearchQuery] = useState('');
  const [historyItems, setHistoryItems] = useState([]);
  const [sessions, setSessions] = useState([]);
  const [isLoading, setIsLoading] = useState(false);

  const fetchHistory = useCallback(async () => {
    setIsLoading(true);
    const result = await getChatHistory();
    setIsLoading(false);
    if (result.success) {
      setHistoryItems(result.history || []);
      setSessions(result.sessions || []);
    }
  }, []);

  useEffect(() => {
    fetchHistory();
  }, [fetchHistory]);

  const filteredHistory = historyItems.filter((item) => {
    if (!searchQuery.trim()) return true;
    return (
      item.content?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      item.role?.toLowerCase().includes(searchQuery.toLowerCase())
    );
  });

  return (
    <div className="history-page-container">
      {/* Page Header */}
      <div className="page-header-intro">
        <div>
          <h1 className="page-main-heading">Conversation History</h1>
          <p className="page-sub-heading">
            Review past employee queries, retrieved policy citations, and generated assistant summaries.
          </p>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="history-toolbar-card">
        <div className="search-input-wrap">
          <Search size={18} className="search-icon" />
          <input
            type="text"
            className="history-search-input"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search past questions or policy topics..."
            aria-label="Search past conversations"
          />
        </div>

        <div className="filter-buttons-group">
          <button
            type="button"
            className={`btn-filter-pill ${isLoading ? 'spinning' : ''}`}
            onClick={fetchHistory}
            disabled={isLoading}
          >
            <RefreshCw size={14} /> Refresh History
          </button>
        </div>
      </div>

      {/* History Items Container */}
      <div className="history-content-container">
        {filteredHistory.length === 0 ? (
          <div className="empty-state-card">
            <div className="empty-state-icon">
              <Inbox size={36} />
            </div>
            <h4 className="empty-state-title">No conversations yet.</h4>
            <p className="empty-state-desc">
              When you ask questions in the AI Assistant, your query transcripts and persistent session records will be stored directly in PostgreSQL.
            </p>
            <span className="history-phase-badge">
              PostgreSQL persistence active &bull; {sessions.length} active sessions
            </span>
          </div>
        ) : (
          <div className="conversations-grid">
            {filteredHistory.map((item) => (
              <div key={item.id} className="conversation-card">
                <div className="conv-card-header">
                  <span className="conv-date">
                    <Calendar size={14} /> {item.created_at ? new Date(item.created_at).toLocaleString() : 'Just now'}
                  </span>
                  <span className="conv-msg-count">
                    <MessageSquare size={14} /> Role: {item.role}
                  </span>
                </div>
                <h4 className="conv-question">{item.content}</h4>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
