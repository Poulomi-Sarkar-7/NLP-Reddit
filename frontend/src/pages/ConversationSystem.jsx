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
  const [knowledgeGraph, setKnowledgeGraph] = useState({ nodes: [], edges: [] });
  const [graphBusy, setGraphBusy] = useState(false);
  const [centerNodeId, setCenterNodeId] = useState('query');
  const [graphHistory, setGraphHistory] = useState([]);
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
    setKnowledgeGraph({ nodes: [], edges: [] });
    setCenterNodeId('query');
    setGraphHistory([]);

    try {
      const res = await axios.post('http://localhost:5000/api/conversation/ask', {
        query: trimmed,
        provider,
        model: model.trim() || null,
        top_k: topK
      });

      setAnswer(res.data.answer || '');
      setContexts(res.data.contexts || []);
      setKnowledgeGraph(res.data.knowledge_graph || { nodes: [], edges: [] });
      setCenterNodeId('query');
      setGraphHistory([]);
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

  const expandNode = async (node) => {
    if (!node || !node.id) return;
    const term = node.id === 'query' ? query : node.label;
    if (!term) return;

    setCenterNodeId(node.id);
    setGraphBusy(true);
    try {
      const res = await axios.post('http://localhost:5000/api/conversation/expand_node', {
        term,
        query,
        contexts,
        max_neighbors: 12
      });
      const next = res.data?.graph || { nodes: [], edges: [] };
      setGraphHistory(prev => [...prev, { graph: knowledgeGraph, center: centerNodeId }]);
      setKnowledgeGraph(next);
      if (next.center) {
        setCenterNodeId(next.center);
      }
    } catch (e) {
      setError(e?.response?.data?.error || 'Could not expand graph node.');
    } finally {
      setGraphBusy(false);
    }
  };

  const goBackGraphView = () => {
    if (!graphHistory.length) return;
    const prev = graphHistory[graphHistory.length - 1];
    setKnowledgeGraph(prev.graph || { nodes: [], edges: [] });
    setCenterNodeId(prev.center || 'query');
    setGraphHistory(graphHistory.slice(0, -1));
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

      {knowledgeGraph.nodes.length > 0 && (
        <div className="glass-card" style={{ marginTop: '1.5rem' }}>
          <h3 style={{ marginBottom: '1rem' }}>Knowledge Graph (Question-Focused)</h3>
          <p style={{ color: 'var(--text-dim)', marginBottom: '0.75rem' }}>
            Click a node to re-center and expand related concepts (local Reddit + external semantic neighbors).
            {graphBusy ? ' Expanding...' : ''}
          </p>
          <div style={{ marginBottom: '0.85rem' }}>
            <button className="btn-secondary" onClick={goBackGraphView} disabled={graphBusy || graphHistory.length === 0}>
              Back to Previous Graph View
            </button>
          </div>
          <KnowledgeGraphView graph={knowledgeGraph} centerNodeId={centerNodeId} onNodeClick={expandNode} />
        </div>
      )}
    </div>
  );
}

function KnowledgeGraphView({ graph, centerNodeId, onNodeClick }) {
  const width = 920;
  const height = 520;
  const cx = width / 2;
  const cy = height / 2;
  const center = centerNodeId || 'query';
  const orderedNodes = [...(graph.nodes || [])].sort((a, b) => {
    if (a.id === center) return -1;
    if (b.id === center) return 1;
    return (b.size || 12) - (a.size || 12);
  });
  const centerNode = orderedNodes.find(n => n.id === center) || orderedNodes[0];
  const otherNodes = orderedNodes.filter(n => n.id !== centerNode?.id).slice(0, 36);
  const radius = Math.min(width, height) * 0.34;

  const positions = {};
  if (centerNode) {
    positions[centerNode.id] = { x: cx, y: cy };
  }
  otherNodes.forEach((n, idx) => {
    const angle = (2 * Math.PI * idx) / Math.max(1, otherNodes.length);
    positions[n.id] = {
      x: cx + radius * Math.cos(angle),
      y: cy + radius * Math.sin(angle)
    };
  });

  const edgeColor = 'rgba(133, 57, 83, 0.35)';
  const labelColor = 'var(--text-main)';
  const getNodeStyle = (n) => {
    if (!n) return {};
    if (n.id === centerNode?.id) {
      return { fill: 'var(--accent)', stroke: 'var(--accent-dark)', text: '#ffffff' };
    }
    if (n.type === 'query') {
      return { fill: 'rgba(97, 45, 83, 0.85)', stroke: 'var(--accent-dark)', text: '#ffffff' };
    }
    if (n.type === 'external') {
      return { fill: 'rgba(74, 222, 128, 0.18)', stroke: '#4ade80', text: labelColor };
    }
    if (n.type === 'local_external') {
      return { fill: 'rgba(250, 204, 21, 0.22)', stroke: '#ca8a04', text: labelColor };
    }
    return { fill: 'rgba(133, 57, 83, 0.16)', stroke: 'var(--card-border)', text: labelColor };
  };

  return (
    <div style={{ width: '100%', overflowX: 'auto' }}>
      <svg viewBox={`0 0 ${width} ${height}`} style={{ width: '100%', minWidth: 700, height: 'auto' }}>
        {graph.edges.map((e, idx) => {
          const s = positions[e.source];
          const t = positions[e.target];
          if (!s || !t) return null;
          const strokeWidth = Math.max(1, Math.min(4, (e.weight || 1) * 0.8));
          return (
            <line
              key={`edge-${idx}`}
              x1={s.x}
              y1={s.y}
              x2={t.x}
              y2={t.y}
              stroke={edgeColor}
              strokeWidth={strokeWidth}
            />
          );
        })}

        {orderedNodes.map((n) => {
          const p = positions[n.id];
          if (!p) return null;
          const style = getNodeStyle(n);
          const isCenter = n.id === centerNode?.id;
          const r = isCenter ? 36 : Math.max(12, Math.min(26, n.size || 14));
          return (
            <g key={`node-${n.id}`} style={{ cursor: 'pointer' }} onClick={() => onNodeClick && onNodeClick(n)}>
              <circle cx={p.x} cy={p.y} r={r} fill={style.fill} stroke={style.stroke} strokeWidth={1.5} />
              <text
                x={p.x}
                y={p.y + 4}
                textAnchor="middle"
                style={{ fill: style.text, fontSize: isCenter ? 11 : 10, fontWeight: 600, pointerEvents: 'none' }}
              >
                {(n.label || '').slice(0, isCenter ? 18 : 14)}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
