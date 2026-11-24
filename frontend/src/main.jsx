
import React, { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import './style.css';

const API_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '');

const makeSessionId = () => `s-${crypto.randomUUID()}`;

function App() {
  const [sessionId] = useState(makeSessionId);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [systemPrompt, setSystemPrompt] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [health, setHealth] = useState('Checking backend…');

  const bottom = useRef(null);

  useEffect(() => {
    fetch(`${API_URL}/health`)
      .then(r => r.ok ? r.json() : Promise.reject())
      .then(d => setHealth(`Connected · ${d.keys_configured} keys · cache on`))
      .catch(() => setHealth('Backend unavailable · check API URL'));
  }, []);

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, busy]);

  async function send() {
    const message = input.trim();

    if (!message || busy) return;

    setInput('');
    setError('');
    setBusy(true);

    setMessages(prev => [
      ...prev,
      {
        role: 'user',
        content: message,
        id: crypto.randomUUID()
      }
    ]);

    try {
      const body = {
        session_id: sessionId,
        message
      };

      if (systemPrompt.trim()) {
        body.system_prompt = systemPrompt.trim();
      }

      const response = await fetch(`${API_URL}/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(body)
      });

      const data = await response.json().catch(() => ({
        detail: 'The server returned an unreadable response.'
      }));

      if (!response.ok) {
        throw new Error(data.detail || `Request failed (${response.status})`);
      }

      setMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          content: data.reply,
          metadata: data.metadata,
          id: crypto.randomUUID()
        }
      ]);

    } catch (e) {
      const messageText = e.message === 'Failed to fetch'
        ? 'Could not connect to the backend. Check that the backend is running and the API URL is correct.'
        : e.message;

      setError(messageText);

    } finally {
      setBusy(false);
    }
  }

  function onKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  }

  return (
    <main className="shell">

      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">✳</span>
          <div>
            <b>LYFTR</b>
            <small>AI WORKSPACE</small>
          </div>
        </div>

        <div className="side-card">
          <span className="live-dot" />
          <div>
            <b>Gateway status</b>
            <small>{health}</small>
          </div>
        </div>

        <div className="side-note">
          <span className="eyebrow">BUILT FOR RELIABILITY</span>
          <p>One conversation. Multiple keys. Smarter caching.</p>
        </div>

        <div className="side-bottom">
          LLM CHATBOT <span>·</span> TAKE-HOME BUILD
        </div>
      </aside>

      <section className="workspace">

        <header className="topbar">
          <div>
            <span className="eyebrow">PLAYGROUND / CHAT</span>
            <h1>Ask anything<span>.</span></h1>
          </div>

          <div className="session-pill">
            <span className="live-dot" /> SESSION ACTIVE
          </div>
        </header>

        <div className="prompt-row">
          <label htmlFor="system-prompt-input">
            SYSTEM PROMPT <span>OPTIONAL</span>
          </label>

          <input
            id="system-prompt-input"
            data-testid="system-prompt-input"
            value={systemPrompt}
            onChange={e => setSystemPrompt(e.target.value)}
            placeholder="Set a custom instruction for this session…"
          />
        </div>

        <div className="chat-area">

          {messages.length === 0 && (
            <div className="welcome">
              <div className="welcome-icon">✳</div>
              <span className="eyebrow">YOUR AI ASSISTANT</span>

              <h2>
                A clear answer<br />
                starts with a question.
              </h2>

              <p>
                Send a message to begin. Your conversation context is
                securely stored in SQLite.
              </p>

              <div className="suggestions">
                <button
                  onClick={() => setInput('Explain how response caching works in LLM applications.')}
                >
                  Explain response caching <span>↗</span>
                </button>

                <button
                  onClick={() => setInput('What happens when an LLM API key is rate limited?')}
                >
                  Explore key failover <span>↗</span>
                </button>
              </div>
            </div>
          )}

          {messages.map(m =>
            m.role === 'user' ? (
              <div className="user-row" key={m.id}>
                <div className="user-bubble">{m.content}</div>
              </div>
            ) : (
              <article
                className="assistant-message"
                data-testid="assistant-message"
                key={m.id}
              >
                <div className="assistant-avatar">✳</div>

                <div className="assistant-content">
                  <div className="assistant-label">
                    LYFTR AI <span>·</span> RESPONSE
                  </div>

                  <div className="reply">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {m.content}
                    </ReactMarkdown>
                  </div>

                  <div className="metadata">
                    <span
                      className={`source ${
                        m.metadata?.resolution_source === 'LLM_CACHE'
                          ? 'cached'
                          : ''
                      }`}
                      data-testid="meta-source"
                    >
                      {m.metadata?.resolution_source}
                    </span>

                    <span data-testid="meta-model">
                      {m.metadata?.model}
                    </span>

                    <span data-testid="meta-latency">
                      {m.metadata?.latency_ms} ms
                    </span>

                    <span>
                      IN <b data-testid="meta-input-tokens">
                        {m.metadata?.input_tokens}
                      </b>
                    </span>

                    <span>
                      OUT <b data-testid="meta-output-tokens">
                        {m.metadata?.output_tokens}
                      </b>
                    </span>

                    <span className="key-label">
                      {m.metadata?.key_id || 'CACHE'}
                    </span>
                  </div>
                </div>
              </article>
            )
          )}

          {busy && (
            <div className="thinking">
              <span />
              <span />
              <span />
              <small>Thinking…</small>
            </div>
          )}

          {error && (
            <div className="error-message" role="alert">
              <b>Request not completed</b>
              <span>{error}</span>
            </div>
          )}

          <div ref={bottom} />
        </div>

        <footer className="composer-wrap">
          <div className="composer">
            <textarea
              id="chat-input"
              data-testid="chat-input"
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={onKeyDown}
              placeholder="Message LYFTR AI…"
              rows="1"
              maxLength="4000"
            />

            <button
              id="send-button"
              data-testid="send-button"
              onClick={send}
              disabled={busy || !input.trim()}
              aria-label="Send message"
            >
              {busy ? '…' : '↑'}
            </button>
          </div>

          <div className="composer-foot">
            <span>
              ENTER TO SEND <span>·</span> SHIFT + ENTER FOR NEW LINE
            </span>
            <span>PER-REQUEST USAGE TRACKING</span>
          </div>
        </footer>

      </section>
    </main>
  );
}

createRoot(document.getElementById('root')).render(<App />);
