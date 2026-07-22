import React, { useState, useEffect } from 'react';

const MCPSettings = () => {
  const [settings, setSettings] = useState({
    mcpServers: [],
    activeServer: null,
    autoConnect: true,
    timeout: 30000,
  });
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // Simulate loading MCP settings (remove actual API call since endpoint doesn't exist)
  useEffect(() => {
    // Simulate loading state
    setIsLoading(true);
    
    // Mock data for demonstration
    const mockData = {
      mcpServers: [
        { 
          id: 'server-1', 
          name: 'Local Filesystem MCP', 
          url: 'http://localhost:3001/mcp', 
          status: 'connected',
          description: 'Provides access to local filesystem tools'
        },
        { 
          id: 'server-2', 
          name: 'GitHub MCP', 
          url: 'http://localhost:3002/mcp', 
          status: 'connecting',
          description: 'GitHub integration for repository management'
        }
      ],
      activeServer: 'server-1',
      autoConnect: true,
      timeout: 30000
    };
    
    // Simulate network delay
    const timer = setTimeout(() => {
      setSettings(mockData);
      setIsLoading(false);
    }, 1000);
    
    return () => clearTimeout(timer);
  }, []);

  const handleAddServer = async () => {
    // Placeholder for adding a new MCP server
    setSuccess('MCP server configuration feature coming soon!');
    setTimeout(() => setSuccess(''), 3000);
  };

  const handleRemoveServer = async (serverId) => {
    // Placeholder for removing an MCP server
    setSuccess(`Removed MCP server: ${serverId}`);
    setTimeout(() => setSuccess(''), 3000);
  };

  const handleTestConnection = async (serverId) => {
    // Placeholder for testing MCP connection
    setSuccess(`Testing connection to ${serverId}...`);
    setTimeout(() => {
      setSuccess(`Connection test completed for ${serverId}`);
    }, 2000);
    setTimeout(() => setSuccess(''), 5000);
  };

  return (
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

      <header className="">
        <nav>
          <a href="#/" className="logo">
            <img src="/main-logo.png" alt="Dead Vision AI" className="logo-icon" />
            AI
          </a>
          <ul className="nav-links">
            <li><a href="#/" className="nav-link">Home</a></li>
            <li><a href="#/chat" className="nav-link">Chat</a></li>
            <li><a href="#/tools" className="nav-link">Tools</a></li>
            <li><a href="#/mcp-settings" className="nav-link active">MCP Settings</a></li>
          </ul>
        </nav>
      </header>

      <main className="flex-1 overflow-auto p-8">
        <div className="max-w-6xl mx-auto">
          <h1 className="text-3xl font-bold mb-6 text-center">
            MCP Server Settings
          </h1>

          {error && (
            <div className="bg-error/10 text-error border-l-4 border-error p-4 mb-6">
              {error}
            </div>
          )}

          {success && (
            <div className="bg-success/10 text-success border-l-4 border-success p-4 mb-6">
              {success}
            </div>
          )}

          <div className="bg-surface rounded-lg border border-card-border shadow-sm overflow-hidden">
            <div className="p-6">
              <h2 className="text-xl font-semibold mb-4">MCP Server Configuration</h2>
              
              <div className="space-y-4">
                <div className="flex justify-between items-center">
                  <button 
                    onClick={handleAddServer}
                    className="btn-cta-primary px-6 py-3"
                    disabled={isLoading}
                  >
                    {isLoading ? 'Loading...' : 'Add MCP Server'}
                  </button>
                  
                  <div className="text-txtsecondary">
                    Configure connections to Model Context Protocol servers
                  </div>
                </div>
                
                <div className="space-y-3">
                  <label className="block text-sm font-medium mb-1">
                    Auto-connect to MCP servers
                  </label>
                  <div className="flex items-center">
                    <label className="relative inline-flex items-center cursor-select-none rounded-md border border-border">
                      <input
                        type="checkbox"
                        className="sr-only peer"
                        checked={settings.autoConnect}
                        onChange={(e) => {
                          setSettings(prev => ({ ...prev, autoConnect: e.target.checked }));
                        }}
                      />
                      <span className="pointer-events-none inset-0 flex items-center px-3">
                        <span className="inline-flex h-5 w-5 shrink-0">
                          <span className="flex items-center justify-center h-4 w-4 rounded">
                            {settings.autoConnect ? (
                              <span className="flex items-center justify-center text-current">
                                {/* Checkmark icon */}
                                <svg className="h-3 w-3" fill="none" viewBox="0 0 6 6">
                                  <path strokeWidth="1.5" d="m2 3 1.5 1.5L4 1" stroke="currentCapRound" strokeLinejoin="round" />
                                </svg>
                              </span>
                            ) : (
                              <span className="flex items-center justify-center">
                                {/* Empty box */}
                              </span>
                            )}
                          </span>
                          <span className="ml-2 text-txtsecondary">{settings.autoConnect ? 'Enabled' : 'Disabled'}</span>
                        </span>
                      </span>
                    </label>
                  </div>
                </div>

                <div className="space-y-3">
                  <label className="block text-sm font-medium mb-1">
                    Connection Timeout (ms)
                  </label>
                  <div className="relative">
                    <input
                      type="number"
                      value={settings.timeout}
                      onChange={(e) => {
                        const value = parseInt(e.target.value) || 30000;
                        setSettings(prev => ({ ...prev, timeout: Math.max(5000, Math.min(300000, value)) }));
                      }}
                      className="block w-full px-4 py-3 text-sm font-medium text-txtmain bg-background border border-border rounded-lg focus:border-primary focus:ring-primary focus:ring-openness-20 disabled:opacity-50"
                      min="5000"
                      max="300000"
                      step="1000"
                      placeholder="30000"
                      disabled={isLoading}
                    />
                  </div>
                  <p className="text-xs text-txtsecondary mt-1">
                    Timeout for MCP server connections (5000-300000 ms)
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* MCP Servers List */}
          {settings.mcpServers.length > 0 && (
            <div className="mt-8">
              <div className="bg-surface rounded-lg border border-card-border shadow-sm overflow-hidden">
                <div className="p-6">
                  <h2 className="text-xl font-semibold mb-4">Configured MCP Servers</h2>
                  
                  <div className="space-y-3">
                    {settings.mcpServers.map((server) => (
                      <div key={server.id || server.name} className="border border-border/50 rounded-lg p-4">
                        <div className="flex justify-between items-start mb-2">
                          <h3 className="font-semibold text-txtmain">{server.name || 'Unnamed Server'}</h3>
                          <div className="flex space-x-2">
                            <button
                              onClick={() => handleTestConnection(server.id || server.name)}
                              className="btn-cta-secondary px-3 py-1 text-xs"
                              disabled={isLoading}
                            >
                              Test
                            </button>
                            <button
                              onClick={() => handleRemoveServer(server.id || server.name)}
                              className="btn-cta-secondary px-3 py-1 text-xs text-error hover:bg-error/10"
                              disabled={isLoading}
                            >
                              Remove
                            </button>
                          </div>
                        </div>
                        
                        <div className="space-y-2 text-txtsecondary">
                          <p><strong>URL:</strong> {server.url || 'Not configured'}</p>
                          <p><strong>Status:</strong> 
                            <span className={`${server.status === 'connected' ? 'text-success' : server.status === 'connecting' ? 'text-warning' : 'text-error'}`}>
                              {server.status || 'Unknown'}
                            </span>
                          </p>
                          {server.description && (
                            <p><strong>Description:</strong> {server.description}</p>
                          )}
                        </div>
                      </div>
                    ))}
                    
                    {settings.mcpServers.length === 0 && (
                      <p className="text-txtsecondary text-center py-6">
                        No MCP servers configured. Add your first server above.
                      </p>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Placeholder content */}
          {settings.mcpServers.length === 0 && (
            <div className="mt-8 text-center py-12">
              <div className="bg-surface rounded-lg border border-card-border shadow-sm p-8">
                <h3 className="text-xl font-semibold mb-4">MCP Server Configuration</h3>
                <p className="text-txtsecondary mb-6">
                  Configure Model Context Protocol servers to extend the capabilities of your AI assistant.
                  MCP servers provide access to tools, resources, and prompts that can be used by LLMs.
                </p>
                
                <div className="space-y-4">
                  <button 
                    onClick={handleAddServer}
                    className="btn-cta-primary px-6 py-3"
                    disabled={isLoading}
                  >
                    {isLoading ? 'Loading...' : 'Add First MCP Server'}
                  </button>
                  
                  <div className="flex flex-col items-center">
                    <a href="#" className="text-primary hover:text-primary-hover">
                      Learn more about MCP
                    </a>
                    <span className="mx-2">|</span>
                    <a href="#" className="text-txtsecondary hover:text-txtmain">
                      Documentation
                    </a>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
};

export default MCPSettings;