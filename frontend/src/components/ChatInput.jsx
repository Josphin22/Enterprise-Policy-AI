import React, { useState, useRef, useEffect } from 'react';
import { Send, Trash2, Mic, MicOff, Globe, Sparkles, FileText, HelpCircle } from 'lucide-react';

export default function ChatInput({
  onClear,
  onSendQuery,
  disabled = false,
  loading = false,
  language = 'en',
  onLanguageChange,
  inputPlaceholder,
}) {
  const [query, setQuery] = useState('');
  const [isListening, setIsListening] = useState(false);
  const [speechSupported, setSpeechSupported] = useState(true);
  const textareaRef = useRef(null);
  const recognitionRef = useRef(null);

  // Initialize SpeechRecognition safely
  useEffect(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRecognition) {
      const recognition = new SpeechRecognition();
      recognition.continuous = false;
      recognition.interimResults = true;

      recognition.onresult = (event) => {
        let transcript = '';
        for (let i = event.resultIndex; i < event.results.length; i++) {
          transcript += event.results[i][0].transcript;
        }
        if (transcript) {
          setQuery((prev) => {
            const trimmed = prev.trim();
            return trimmed ? `${trimmed} ${transcript}` : transcript;
          });
        }
      };

      recognition.onerror = (event) => {
        console.warn('Speech recognition error:', event.error);
        setIsListening(false);
      };

      recognition.onend = () => {
        setIsListening(false);
      };

      recognitionRef.current = recognition;
    } else {
      setSpeechSupported(false);
    }

    return () => {
      if (recognitionRef.current) {
        try {
          recognitionRef.current.stop();
        } catch (e) {
          // ignore
        }
      }
    };
  }, []);

  // Update speech recognition language when language prop changes
  useEffect(() => {
    if (recognitionRef.current) {
      if (language === 'ta') {
        recognitionRef.current.lang = 'ta-IN';
      } else if (language === 'hi') {
        recognitionRef.current.lang = 'hi-IN';
      } else {
        recognitionRef.current.lang = 'en-US';
      }
    }
  }, [language]);

  // Auto-grow textarea up to max-height
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 180)}px`;
    }
  }, [query]);

  const toggleVoiceInput = () => {
    if (!speechSupported) {
      alert('Speech recognition is not supported in this browser. Please use Google Chrome, Edge, or a Web Speech API-compatible browser.');
      return;
    }

    if (!recognitionRef.current) return;

    if (isListening) {
      try {
        recognitionRef.current.stop();
      } catch (e) {
        console.warn('Error stopping speech recognition:', e);
      }
      setIsListening(false);
    } else {
      try {
        recognitionRef.current.start();
        setIsListening(true);
      } catch (e) {
        console.warn('Error starting speech recognition:', e);
        setIsListening(false);
      }
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const handleSubmit = (e) => {
    if (e && e.preventDefault) e.preventDefault();
    if (!query.trim() || disabled || loading) return;

    if (isListening && recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch (err) {}
      setIsListening(false);
    }

    if (onSendQuery) {
      onSendQuery(query.trim());
      setQuery('');
      if (textareaRef.current) {
        textareaRef.current.style.height = 'auto';
      }
    }
  };

  const handleQuickAction = (actionType) => {
    let actionPrompt = '';
    if (actionType === 'summarize') {
      actionPrompt = 'Summarize the core policy rules and key takeaways from the company documents.';
    } else if (actionType === 'explain') {
      actionPrompt = 'Explain the key company policies simply in plain language for a new employee.';
    } else if (actionType === 'find') {
      actionPrompt = 'What are the main company policies and guidelines documented here?';
    }

    if (actionPrompt && onSendQuery && !disabled && !loading) {
      onSendQuery(actionPrompt);
    }
  };

  return (
    <div className="chat-input-wrapper">
      {/* Quick Action Chips */}
      <div className="chat-quick-actions-bar" aria-label="Quick Actions">
        <span className="quick-actions-label">Quick Actions:</span>
        <button
          type="button"
          className="quick-action-pill"
          onClick={() => handleQuickAction('summarize')}
          disabled={disabled || loading}
          title="Summarize key policy documents"
        >
          <Sparkles size={12} className="text-emerald" />
          <span>Summarize</span>
        </button>

        <button
          type="button"
          className="quick-action-pill"
          onClick={() => handleQuickAction('explain')}
          disabled={disabled || loading}
          title="Explain simply in plain language"
        >
          <HelpCircle size={12} className="text-mint" />
          <span>Explain simply</span>
        </button>

        <button
          type="button"
          className="quick-action-pill"
          onClick={() => handleQuickAction('find')}
          disabled={disabled || loading}
          title="Find policy requirements"
        >
          <FileText size={12} className="text-cyan" />
          <span>Find policy</span>
        </button>
      </div>

      {/* Main Chat Input Box */}
      <form onSubmit={handleSubmit} className="chatgpt-input-box">
        <div className="chatgpt-textarea-row">
          <textarea
            ref={textareaRef}
            rows={1}
            className="chatgpt-textarea"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              isListening
                ? 'Listening... Speak now...'
                : inputPlaceholder || 'Ask anything about company policies, leave rules, attendance, or benefits (Enter to send, Shift+Enter for new line)...'
            }
            disabled={disabled || loading}
          />

          {/* Voice Input Microphone Button */}
          <button
            type="button"
            className={`btn-chat-mic ${isListening ? 'listening' : ''}`}
            onClick={toggleVoiceInput}
            disabled={disabled || loading}
            title={isListening ? 'Stop voice recording' : 'Voice input (Speak your question)'}
            aria-label="Voice input"
          >
            {isListening ? <MicOff size={17} className="text-danger-pulse" /> : <Mic size={17} />}
            {isListening && <span className="mic-wave-pulse" />}
          </button>
        </div>

        {/* Action Controls Row (Clear, Language Selector, Send) */}
        <div className="chatgpt-actions-row">
          <div className="chat-actions-left">
            <button
              type="button"
              className="btn-chat-clear"
              onClick={onClear}
              title="Clear conversation"
              disabled={disabled || loading}
            >
              <Trash2 size={14} />
              <span>Clear</span>
            </button>

            {/* Language Selector */}
            <div className="chat-language-selector" title="Select response language">
              <Globe size={14} className="lang-icon" />
              <select
                className="lang-select-dropdown"
                value={language}
                onChange={(e) => onLanguageChange && onLanguageChange(e.target.value)}
                disabled={disabled || loading}
                aria-label="Response Language"
              >
                <option value="en">English</option>
                <option value="ta">Tamil (தமிழ்)</option>
                <option value="hi">Hindi (हिन्दी)</option>
              </select>
            </div>
          </div>

          <button
            type="submit"
            className="btn-chatgpt-send"
            disabled={disabled || loading || !query.trim()}
            title="Send question (Enter)"
          >
            <Send size={15} />
            <span>{loading ? 'Thinking...' : 'Ask AI'}</span>
          </button>
        </div>
      </form>
    </div>
  );
}
