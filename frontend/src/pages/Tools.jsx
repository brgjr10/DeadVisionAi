import React from 'react';

export default function Tools({ endpointStatuses, tools, expandedTool, setExpandedTool, onRefreshEndpoints, onRefreshTools, providerStatus }) {
  return (
    <section className="tools-section" style={{ maxWidth: '1200px', margin: '0 auto' }}>
      <div className="features-grid" style={{ marginTop: '80px' }}>
        {/* Spacer for Tools page only */}
        <div className="tools-spacer" />

        <div className="glass card status-card" style={{ marginBottom: '24px' }}>
          <div className="card-header">
            <h3 className="card-title">System Status</h3>
            <button onClick={onRefreshEndpoints} className="btn-refresh" type="button">Refresh Status</button>
          </div>
          {endpointStatuses && Object.entries(endpointStatuses).map(([name, status]) => (
            <div key={name} className="status-item">
              <div className={status === 'online' ? 'status-dot status-dot-online' : 'status-dot status-dot-offline'}></div>
              <span className="status-label">{name}</span>
              <span className={status === 'online' ? 'status-value status-value-online' : 'status-value status-value-offline'}>
                {status === 'online' ? '● Online' : '● Offline'}
              </span>
            </div>
          ))}
          {providerStatus && providerStatus.length > 0 && (
            <div className="provider-section">
              <p className="provider-label">Cloud Providers:</p>
              <div className="provider-tags">
                {providerStatus.map(provider => (
                  <span key={provider.provider_id} className="provider-tag">{provider.provider_id}</span>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="glass card tools-card">
          <div className="card-header">
            <h3 className="card-title">Available Tools ({tools.length})</h3>
            <button onClick={onRefreshTools} className="btn-refresh" type="button">Refresh Tools</button>
          </div>
          {tools.length > 0 ? (
            <div className="tools-list">
              {tools.map(tool => {
                const displayName = tool.tool_id.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
                const isOpen = expandedTool === tool.tool_id;
                return (
                  <div key={tool.tool_id} className="tool-row">
                    <button
                      className="tool-header"
                      onClick={() => setExpandedTool(isOpen ? null : tool.tool_id)}
                      aria-expanded={isOpen}
                      type="button"
                    >
                      <span className="tool-name">{displayName}</span>
                      <svg
                        className={isOpen ? 'chevron chevron-open' : 'chevron'}
                        width="14"
                        height="14"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2.5"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      >
                        <polyline points="6 9 12 15 18 9" />
                      </svg>
                    </button>
                    <div className={isOpen ? 'tool-details tool-details-open' : 'tool-details'}>
                      <p className="tool-details-text">{tool.description}</p>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <p className="tools-empty">No tools available. Start backend to load tools.</p>
          )}
        </div>
      </div>
    </section>
  );
}
