import React, { useState, useEffect } from 'react';
import { HashRouter, Routes, Route } from 'react-router-dom';
import './css/neural-glass.css';
import './App.css';
import Home from './pages/Home';
import Chat from './pages/Chat';
import Tools from './pages/Tools';
import MCPSettings from './pages/MCPSettings';

function App() {
   const [endpointStatuses, setEndpointStatuses] = useState({
     'Backend API': 'checking',
     'Tool Registry': 'checking',
     'Chat Service': 'checking',
     'Providers': 'checking',
     'LM Studio': 'checking'
   });
  const [providerStatus, setProviderStatus] = useState([]);
  const [tools, setTools] = useState([]);
  const [chatHistory, setChatHistory] = useState([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [headerScrolled, setHeaderScrolled] = useState(false);
  const [expandedTool, setExpandedTool] = useState(null);

  const scrollAndClearMobiles = () => {
    setMobileMenuOpen(false);
  };

  const handleAddAttachment = () => {
    const input = document.createElement('input');
    input.type = 'file';
    input.style.display = 'none';
    document.body.appendChild(input);
    input.addEventListener('change', () => {
      if (input.files.length > 0) {
        const fileNames = Array.from(input.files).map(f => f.name).join(', ');
        setInput(prev => prev + `\n[Attachment: ${fileNames}]`);
      }
      document.body.removeChild(input);
    });
    input.click();
  };

  useEffect(() => {
    checkEndpointStatuses();
    fetchAvailableTools();
    const intervalId = setInterval(checkEndpointStatuses, 30000);
    return () => clearInterval(intervalId);
  }, []);

  useEffect(() => {
    const onScroll = () => setHeaderScrolled(window.scrollY > 80);
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

    const checkEndpointStatuses = async () => {
      console.log('=== CHECKENDPOINTSTATUSES CALLED ===');
      // Define endpoints to check
      const endpoints = [
        { name: 'Backend API', url: '/api/v1/health' },
        { name: 'Tool Registry', url: '/tools' },
        { name: 'Chat Service', url: '/v1/models' },
        { name: 'LM Studio', url: '/v1/models' }
      ];

      // Initialize statuses
      const newStatuses = {};

      // Check each endpoint
      for (const endpoint of endpoints) {
        console.log(`[LM Studio] Processing endpoint: ${JSON.stringify(endpoint)}`);
        try {
          // For LM Studio, try without auth first to avoid CORS preflight issues
          if (endpoint.url.includes('1234')) {
            // Try without auth first
            console.log(`[LM Studio] Checking ${endpoint.name} at ${endpoint.url} (no auth)`);
            let response = await fetch(endpoint.url, { method: 'GET' });
            
            // If we get a 401, try with auth
            if (response.status === 401) {
              console.log(`[LM Studio] Getting 401, trying with auth for ${endpoint.name}`);
              const config = { 
                method: 'GET',
                headers: { 
                  Authorization: `Bearer sk-lm-oWIgaJqa:EzedWIId47dvcYlduV2H` 
                } 
              };
              response = await fetch(endpoint.url, config);
            }
            
            // Set status based on final response
            const isOnline = response.ok;
            console.log(`[LM Studio] ${endpoint.name} status: ${isOnline ? 'online' : 'offline'} (status: ${response.status}, ok: ${response.ok})`);
            newStatuses[endpoint.name] = isOnline ? 'online' : 'offline';
          } else {
            // For other endpoints, use original logic
            console.log(`[LM Studio] Checking ${endpoint.name} at ${endpoint.url}`);
            const response = await fetch(endpoint.url, { method: 'GET' });
            
            // Set status
            const isOnline = response.ok;
            console.log(`[LM Studio] ${endpoint.name} status: ${isOnline ? 'online' : 'offline'} (status: ${response.status}, ok: ${response.ok})`);
            newStatuses[endpoint.name] = isOnline ? 'online' : 'offline';
          }
        } catch (err) {
          console.error(`[LM Studio] Endpoint check failed for ${endpoint.name}:`, err);
          newStatuses[endpoint.name] = 'offline';
        }
      }

// Check providers endpoint
      try {
        console.log('[LM Studio] Checking providers endpoint');
        const providersResponse = await fetch('/api/v1/providers');
        if (providersResponse.ok) {
          const providersData = await providersResponse.json();
          newStatuses['Providers'] = 'online';
          setProviderStatus(providersData.providers || []);
          console.log('[LM Studio] Providers status: online');
        } else {
          newStatuses['Providers'] = 'offline';
          console.log('[LM Studio] Providers status: offline (not ok)');
        }
      } catch (err) {
        console.error('[LM Studio] Providers check failed:', err);
        newStatuses['Providers'] = 'offline';
      }

     // Update state
     console.log('[LM Studio] Setting endpoint statuses:', newStatuses);
     setEndpointStatuses(newStatuses);
   };

  const fetchAvailableTools = async () => {
    try {
      const response = await fetch('/tools');
      if (response.ok) {
        const data = await response.json();
        setTools(data.tools || []);
      }
    } catch (error) {
      console.error('Failed to fetch tools:', error);
    }
  };

  const sendMessage = async (e) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const message = input;
    setInput('');
    setIsLoading(true);

    setChatHistory(prev => [...prev, {
      id: Date.now(),
      role: 'user',
      content: message,
      timestamp: new Date()
    }]);

    try {
      const response = await fetch('/v1/chat/completions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model: "Llama-3-2-3B-Instruct-Q4_K_S",
          messages: [{ role: "user", content: message }],
          max_tokens: 1000,
          temperature: 0.7
        })
      });

      const data = await response.json();
      setChatHistory(prev => [...prev, {
        id: Date.now() + 1,
        role: 'assistant',
        content: response.ok ? data.choices[0]?.message?.content : 'Sorry, I encountered an error.',
        timestamp: new Date()
      }]);
    } catch {
      setChatHistory(prev => [...prev, {
        id: Date.now() + 1,
        role: 'assistant',
        content: 'Sorry, I encountered an error processing your request.',
        timestamp: new Date()
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  const statusCount = Object.values(endpointStatuses).filter(s => s === 'online').length;

  return (
    <HashRouter>
      <div className="content-wrapper">
        <div className="neural-background"></div>
        <div className="geometric-shapes">
          <div className="shape"></div>
          <div className="shape"></div>
          <div className="shape"></div>
          <div className="shape"></div>
        </div>
        <div className="neural-lines">
          <div className="neural-line"></div>
          <div className="neural-line"></div>
          <div className="neural-line"></div>
        </div>

        <header className={headerScrolled ? 'scrolled' : ''}>
          <nav>
            <a href="#/" className="logo">
              <img src="/main-logo.png" alt="Dead Vision AI" className="logo-icon" />
              AI
            </a>
            <ul className="nav-links">
               <li><a href="#/" className="nav-link" onClick={scrollAndClearMobiles}>Home</a></li>
               <li><a href="#/chat" className="nav-link" onClick={scrollAndClearMobiles}>Chat</a></li>
               <li><a href="#/tools" className="nav-link" onClick={scrollAndClearMobiles}>Tools</a></li>
               <li><a href="#/mcp-settings" className="nav-link" onClick={scrollAndClearMobiles}>MCP Settings</a></li>
            </ul>
          </nav>
        </header>

         <div className={`mobile-nav${mobileMenuOpen ? ' open' : ''}`}>
           <a href="#/" className="mobile-nav-link" onClick={scrollAndClearMobiles}>Home</a>
           <a href="#/chat" className="mobile-nav-link" onClick={scrollAndClearMobiles}>Chat</a>
           <a href="#/tools" className="mobile-nav-link" onClick={scrollAndClearMobiles}>Tools</a>
           <a href="#/mcp-settings" className="mobile-nav-link" onClick={scrollAndClearMobiles}>MCP Settings</a>
         </div>

        <Routes>
          <Route path="/" element={
            <Home
              statusCount={statusCount}
              providerStatus={providerStatus}
              tools={tools}
            />
          } />
          <Route path="/chat" element={
            <Chat
              chatHistory={chatHistory}
              input={input}
              setInput={setInput}
              isLoading={isLoading}
              tools={tools}
              onSendMessage={sendMessage}
              onAddAttachment={handleAddAttachment}
            />
          } />
           <Route path="/tools" element={
             <Tools
               endpointStatuses={endpointStatuses}
               tools={tools}
               expandedTool={expandedTool}
               setExpandedTool={setExpandedTool}
               onRefreshEndpoints={checkEndpointStatuses}
               onRefreshTools={fetchAvailableTools}
               providerStatus={providerStatus}
             />
           } />
           <Route path="/mcp-settings" element={
             <MCPSettings
               endpointStatuses={endpointStatuses}
               providerStatus={providerStatus}
             />
           } />
</Routes>
        </div>
    </HashRouter>
  );
}

export default App;

// Sample component for preview
export const SampleDefault = () => (
  <App
  />
);
