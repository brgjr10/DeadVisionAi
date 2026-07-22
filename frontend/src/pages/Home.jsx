import React from 'react';
import { Link } from 'react-router-dom';

export default function Home({ statusCount, providerStatus, tools, onNavigate }) {
  return (
    <section className="hero" id="home">
      <div className="hero-glow"></div>
      <div className="hero-content">
        <p className="hero-subtitle">Dead Vision AI Platform</p>
        <h1 className="hero-title">Neural Intelligence Assistant</h1>
        <div className="hero-description">
          <p>Powered by HAIOS Backend with Local MCP Server Integration.
             Access real-time information and execute tools through AI assistance.</p>
        </div>
        <div className="hero-stats">
          <div className="hero-stat">
            <span className="hero-stat-number">{statusCount}/4</span>
            <span className="hero-stat-label">Services Online</span>
          </div>
          <div className="hero-stat">
            <span className="hero-stat-number">{providerStatus.length}</span>
            <span className="hero-stat-label">Providers Ready</span>
          </div>
          <div className="hero-stat">
            <span className="hero-stat-number">{tools.length}</span>
            <span className="hero-stat-label">Tools Available</span>
          </div>
        </div>
        <div className="cta-buttons">
          <Link to="/chat" className="btn-cta btn-cta-primary" onClick={onNavigate}>Start Chatting</Link>
          <Link to="/tools" className="btn-cta btn-cta-secondary" onClick={onNavigate}>View Tools</Link>
        </div>
      </div>
    </section>
  );
}
