import React from 'react';
import { Loader2 } from 'lucide-react';

export default function LoadingIndicator({ message = 'Loading...', size = 20, inline = false }) {
  if (inline) {
    return (
      <span className="loading-inline" role="status" aria-live="polite">
        <Loader2 size={size} className="spin-animation" />
        <span className="loading-text">{message}</span>
      </span>
    );
  }

  return (
    <div className="loading-container" role="status" aria-live="polite">
      <Loader2 size={size} className="spin-animation" />
      <p className="loading-text">{message}</p>
    </div>
  );
}
