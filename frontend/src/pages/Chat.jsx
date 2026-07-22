import React, { useRef } from 'react';

export default function Chat({ chatHistory, input, setInput, isLoading, tools, onSendMessage, onAddAttachment }) {
  const chatWindowRef = useRef(null);

  return (
    <section className="chat-section">
      <div className="chat-section-inner">
        <div className="chat-window" ref={chatWindowRef}>
          {chatHistory.map(message => (
            <div key={message.id} className={`chat-bubble ${message.role === 'user' ? 'user' : 'assistant'}`}>
              {message.role === 'assistant' && (
                <div className="chat-message-header">
                  <img src="/agent-profile.png" alt="Dead Vision AI" className="message-avatar" />
                  <span className="message-model-name">Dead Vision AI</span>
                </div>
              )}
              <p>{message.content}</p>
              {message.tool_calls && message.tool_calls.length > 0 && (
                <div className="chat-tool-calls">
                  Tools: {message.tool_calls.map(tc => tc.name).join(', ')}
                </div>
              )}
            </div>
          ))}
          {isLoading && (
            <div className="chat-bubble assistant">
              <div className="typing-indicator">
                <div className="typing-dot"></div>
                <div className="typing-dot"></div>
                <div className="typing-dot"></div>
              </div>
            </div>
          )}
        </div>
        <form onSubmit={onSendMessage} className="chat-form">
          <input
            type="text"
            value={input}
            onChange={e => setInput(e.target.value)}
            placeholder="Ask Dead Vision AI&#8230;"
            className="chat-input"
            disabled={isLoading}
          />
          <button
            type="button"
            className="chat-attachment-btn"
            onClick={onAddAttachment}
            disabled={isLoading}
            aria-label="Add attachment"
          >
            +
          </button>
          <button
            type="submit"
            disabled={isLoading || !input.trim()}
            className="chat-submit"
          >
            Send
          </button>
        </form>
      </div>
    </section>
  );
}
