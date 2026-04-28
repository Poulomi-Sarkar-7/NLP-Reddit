import React, { useState } from 'react';
import axios from 'axios';
import { Languages } from 'lucide-react';

export default function Translation() {
  const [query, setQuery] = useState('');
  const [provider, setProvider] = useState('groq');
  const [model, setModel] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);

  const runTranslate = async () => {
    const q = query.trim();
    if (!q) return;
    setLoading(true);
    setError('');
    setResult(null);
    try {
      const res = await axios.post('http://localhost:5000/api/translation/translate', {
        query: q,
        provider,
        model: model.trim() || null
      });
      setResult(res.data);
    } catch (e) {
      setError(e?.response?.data?.error || 'Failed to translate post.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ animation: 'fadeIn 0.5s ease' }}>
      <div className="section-title">Translation</div>
      <p style={{ color: 'var(--text-dim)', marginBottom: '1.5rem' }}>
        Enter a post ID or post text query, and get Bengali-script translation.
      </p>

      <div className="glass-card" style={{ marginBottom: '1.5rem' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 220px 220px auto', gap: '0.75rem' }}>
          <input
            className="conversation-input"
            placeholder="Post ID or query text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && runTranslate()}
          />
          <select className="conversation-input" value={provider} onChange={(e) => setProvider(e.target.value)}>
            <option value="groq">Groq</option>
            <option value="google">Gemini</option>
            <option value="both">Both</option>
          </select>
          <input
            className="conversation-input"
            placeholder="Model (optional)"
            value={model}
            onChange={(e) => setModel(e.target.value)}
          />
          <button className="btn-primary" onClick={runTranslate} disabled={loading}>
            <Languages size={16} /> {loading ? 'Translating...' : 'Translate'}
          </button>
        </div>
      </div>

      {error && (
        <div className="glass-card" style={{ borderColor: '#f87171', marginBottom: '1.5rem' }}>
          <h3 style={{ color: '#f87171', marginBottom: '0.35rem' }}>Error</h3>
          <p>{error}</p>
        </div>
      )}

      {result && result.found === false && (
        <div className="glass-card">
          <p>No matching post found for this query.</p>
        </div>
      )}

      {result && result.found && provider !== 'both' && (
        <div className="grid-cols-2">
          <div className="glass-card">
            <h3 style={{ marginBottom: '0.8rem' }}>English Text (Post {result.post_id})</h3>
            <div style={{ whiteSpace: 'pre-wrap', lineHeight: '1.65' }}>{result.english_text}</div>
          </div>
          <div className="glass-card">
            <h3 style={{ marginBottom: '0.8rem' }}>Bengali Translation ({result.provider})</h3>
            <div style={{ whiteSpace: 'pre-wrap', lineHeight: '1.65' }}>{result.translation}</div>
          </div>
        </div>
      )}

      {result && result.found && provider === 'both' && (
        <>
          <div className="glass-card" style={{ marginBottom: '1.5rem' }}>
            <h3 style={{ marginBottom: '0.8rem' }}>English Text (Post {result.post_id})</h3>
            <div style={{ whiteSpace: 'pre-wrap', lineHeight: '1.65' }}>{result.english_text}</div>
          </div>
          <div className="grid-cols-2">
            <div className="glass-card">
              <h3 style={{ marginBottom: '0.8rem' }}>Bengali Translation (Groq)</h3>
              <div style={{ whiteSpace: 'pre-wrap', lineHeight: '1.65' }}>{result.translations?.groq || 'No output.'}</div>
            </div>
            <div className="glass-card">
              <h3 style={{ marginBottom: '0.8rem' }}>Bengali Translation (Gemini)</h3>
              <div style={{ whiteSpace: 'pre-wrap', lineHeight: '1.65' }}>{result.translations?.google || 'No output.'}</div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
