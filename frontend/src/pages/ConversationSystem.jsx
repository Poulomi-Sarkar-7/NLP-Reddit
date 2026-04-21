import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { MessageSquare, Database, Bot } from 'lucide-react';

export default function ConversationSystem() {
  const [query, setQuery] = useState('');
  const [provider, setProvider] = useState('groq');
  const [model, setModel] = useState('');
  const [topK, setTopK] = useState(8);
  const [loading, setLoading] = useState(false);
  const [rebuilding, setRebuilding] = useState(false);
  const [answer, setAnswer] = useState('');
  const [contexts, setContexts] = useState([]);
  const [error, setError] = useState('');
  const [providerStatus, setProviderStatus] = useState({ groq: false, google: false });

  useEffect(() => {
    axios.get('http://localhost:5000/api/conversation/providers')
      .then(res => setProviderStatus(res.data.providers || { groq: false, google: false }))
      .catch(() => setProviderStatus({ groq: false, google: false }));
  }, []);

  const runAsk = async () => {
    const trimmed = query.trim();
    if (!trimmed) return;
    setLoading(true);
    setError('');
    setAnswer('');
    setContexts([]);

    try {
      const res = await axios.post('http://localhost:5000/api/conversation/ask', {
        query: trimmed,
        provider,
        model: model.trim() || null,
        top_k: topK
      });

      setAnswer(res.data.answer || '');
      setContexts(res.data.contexts || []);
    } catch (e) {
      setError(e?.response?.data?.error || 'Failed to get response from conversation system.');
    } finally {
      setLoading(false);
    }
  };

  const rebuildIndex = async () => {
    setRebuilding(true);
    setError('');
    try {
      await axios.post('http://localhost:5000/api/conversation/rebuild');
    } catch (e) {
      setError(e?.response?.data?.error || 'Failed to rebuild RAG index.');
    } finally {
      setRebuilding(false);
    }
  };

  return (
    <div style={{ animation: 'fadeIn 0.5s ease' }}>
      <div className="section-title">Conversation System</div>
      <p style={{ color: 'var(--text-dim)', marginBottom: '1.5rem', lineHeight: '1.6' }}>
        Ask questions over your Reddit repository using Retrieval-Augmented Generation (RAG).
        The system retrieves relevant posts/comments, then sends that context to your selected LLM endpoint.
      </p>

      <div className="glass-card" style={{ marginBottom: '1.5rem' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 0.8fr', gap: '1rem', marginBottom: '1rem' }}>
          <div>
            <label style={{ fontWeight: 600, display: 'block', marginBottom: '0.5rem' }}>Question</label>
            <textarea
              className="conversation-input"
              rows={5}
              placeholder="Example: What are people saying about AI replacing junior developers?"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>

          <div style={{ display: 'grid', gap: '0.75rem', alignContent: 'start' }}>
            <div>
              <label style={{ fontWeight: 600, display: 'block', marginBottom: '0.4rem' }}>Provider</label>
              <select className="conversation-input" value={provider} onChange={(e) => setProvider(e.target.value)}>
                <option value="groq">Groq</option>
                <option value="google">Google AI Studio (Gemini)</option>
              </select>
            </div>

            <div>
              <label style={{ fontWeight: 600, display: 'block', marginBottom: '0.4rem' }}>Model (optional)</label>
              <input
                className="conversation-input"
                placeholder="Leave blank for default"
                value={model}
                onChange={(e) => setModel(e.target.value)}
              />
            </div>

            <div>
              <label style={{ fontWeight: 600, display: 'block', marginBottom: '0.4rem' }}>Retrieved Chunks (Top-K)</label>
              <input
                type="number"
                className="conversation-input"
                min={3}
                max={20}
                value={topK}
                onChange={(e) => setTopK(Number(e.target.value))}
              />
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
          <button className="btn-primary" onClick={runAsk} disabled={loading}>
            <Bot size={16} /> {loading ? 'Generating...' : 'Ask'}
          </button>
          <button className="btn-secondary" onClick={rebuildIndex} disabled={rebuilding}>
            <Database size={16} style={{ marginRight: 4 }} />
            {rebuilding ? 'Rebuilding...' : 'Rebuild Retrieval Index'}
          </button>
        </div>
      </div>

      <div className="glass-card" style={{ marginBottom: '1.5rem' }}>
        <h3 style={{ marginBottom: '0.75rem' }}>Provider Key Status</h3>
        <p style={{ color: 'var(--text-dim)' }}>
          Groq key: <strong>{providerStatus.groq ? 'Configured' : 'Missing'}</strong> | Google key:{' '}
          <strong>{providerStatus.google ? 'Configured' : 'Missing'}</strong>
        </p>
        <p style={{ color: 'var(--text-dim)', marginTop: '0.5rem', fontSize: '0.92rem' }}>
          Set environment variables on backend: <code>GROQ_API_KEY</code> and <code>GOOGLE_API_KEY</code> (or <code>GEMINI_API_KEY</code>).
        </p>
      </div>

      {error && (
        <div className="glass-card" style={{ borderColor: '#f87171', marginBottom: '1.5rem' }}>
          <h3 style={{ color: '#f87171', marginBottom: '0.5rem' }}>Error</h3>
          <p>{error}</p>
        </div>
      )}

      {answer && (
        <div className="glass-card" style={{ marginBottom: '1.5rem' }}>
          <h3 style={{ marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <MessageSquare size={18} /> Generated Answer
          </h3>
          <div style={{ whiteSpace: 'pre-wrap', lineHeight: '1.7' }}>{answer}</div>
        </div>
      )}

      {contexts.length > 0 && (
        <div className="glass-card">
          <h3 style={{ marginBottom: '1rem' }}>Retrieved Context</h3>
          <div style={{ display: 'grid', gap: '0.9rem' }}>
            {contexts.map((c, i) => (
              <div key={c.id || i} className="comment-card">
                <div style={{ fontWeight: 700, marginBottom: '0.35rem' }}>
                  [{i + 1}] {c.source_type.toUpperCase()} - {c.source_id}
                </div>
                <div style={{ color: 'var(--text-dim)', marginBottom: '0.35rem' }}>{c.title}</div>
                <div>{c.body}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
