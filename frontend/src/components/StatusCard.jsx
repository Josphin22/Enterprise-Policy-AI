import React from 'react';

export default function StatusCard({
  title,
  value,
  subtitle,
  icon: Icon,
  badgeText,
  badgeType = 'neutral', // 'success' | 'warning' | 'error' | 'neutral' | 'info'
  className = '',
}) {
  return (
    <div className={`status-card ${className}`}>
      <div className="status-card-header">
        <span className="status-card-title">{title}</span>
        {Icon && (
          <div className="status-card-icon-wrap">
            <Icon size={18} />
          </div>
        )}
      </div>

      <div className="status-card-body">
        <div className="status-card-value">{value}</div>
        {subtitle && <div className="status-card-subtitle">{subtitle}</div>}
      </div>

      {badgeText && (
        <div className="status-card-footer">
          <span className={`status-badge badge-${badgeType}`}>{badgeText}</span>
        </div>
      )}
    </div>
  );
}
