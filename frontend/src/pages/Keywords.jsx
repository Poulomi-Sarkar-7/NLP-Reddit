import React, { useState } from 'react';
import axios from 'axios';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import { Search, Hash } from 'lucide-react';

function colorForValue(v) {
  const value = Math.max(0, Math.min(1, Number(v) || 0));
  const alpha = 0.12 + value * 0.78;
  return `rgba(133, 57, 83, ${alpha})`;
}

export default function Keywords() {
  const [keyword, setKeyword] = useState('');
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [postSnippets, setPostSnippets] = useState([]);
  const [commentSnippets, setCommentSnippets] = useState([]);
  const [postState, setPostState] = useState({ offset: 0, hasMore: false, total: 0, loading: false });
  const [commentState, setCommentState] = useState({ offset: 0, hasMore: false, total: 0, loading: false });

  const fetchSnippets = async (kind, offset, reset = false) => {
    const q = keyword.trim();
    if (!q) return;

    if (kind === 'posts') setPostState(prev => ({ ...prev, loading: true }));
    if (kind === 'comments') setCommentState(prev => ({ ...prev, loading: true }));

    try {
      const res = await axios.get(
        `http://localhost:5000/api/keywords/snippets?keyword=${encodeURIComponent(q)}&kind=${kind}&offset=${offset}&limit=5`
      );
      const payload = res.data || {};
      if (kind === 'posts') {
        setPostSnippets(prev => (reset ? (payload.items || []) : [...prev, ...(payload.items || [])]));
        setPostState({
          offset: payload.next_offset || 0,
          hasMore: !!payload.has_more,
          total: payload.total || 0,
          loading: false
        });
      } else {
        setCommentSnippets(prev => (reset ? (payload.items || []) : [...prev, ...(payload.items || [])]));
        setCommentState({
          offset: payload.next_offset || 0,
          hasMore: !!payload.has_more,
          total: payload.total || 0,
          loading: false
        });
      }
    } catch (e) {
      setError(e?.response?.data?.error || 'Failed to fetch keyword snippets.');
      if (kind === 'posts') setPostState(prev => ({ ...prev, loading: false }));
      if (kind === 'comments') setCommentState(prev => ({ ...prev, loading: false }));
    }
  };

  const runAnalyze = async () => {
    const q = keyword.trim();
    if (!q) return;
    setLoading(true);
    setError('');
    setData(null);
    setPostSnippets([]);
    setCommentSnippets([]);
    setPostState({ offset: 0, hasMore: false, total: 0, loading: false });
    setCommentState({ offset: 0, hasMore: false, total: 0, loading: false });
    try {
      const res = await axios.get(`http://localhost:5000/api/keywords/analyze?keyword=${encodeURIComponent(q)}`);
      setData(res.data);
      await Promise.all([
        fetchSnippets('posts', 0, true),
        fetchSnippets('comments', 0, true)
      ]);
    } catch (e) {
      setError(e?.response?.data?.error || 'Failed to analyze keyword.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ animation: 'fadeIn 0.5s ease' }}>
      <div className="section-title">Keywords</div>
      <p style={{ color: 'var(--text-dim)', marginBottom: '1.5rem' }}>
        Query a keyword to inspect frequency, top co-occurring terms, and their correlation heatmap.
      </p>

      <div className="glass-card" style={{ marginBottom: '1.5rem' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: '0.75rem' }}>
          <input
            className="conversation-input"
            placeholder="Enter keyword (e.g., career, interview, salary)"
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && runAnalyze()}
          />
          <button className="btn-primary" onClick={runAnalyze} disabled={loading}>
            <Search size={16} /> {loading ? 'Analyzing...' : 'Analyze'}
          </button>
        </div>
      </div>

      {error && (
        <div className="glass-card" style={{ borderColor: '#f87171', marginBottom: '1.5rem' }}>
          <h3 style={{ color: '#f87171', marginBottom: '0.35rem' }}>Error</h3>
          <p>{error}</p>
        </div>
      )}

      {data && (
        <>
          <div className="grid-cols-2" style={{ marginBottom: '1.5rem' }}>
            <div className="glass-card" style={{ textAlign: 'center' }}>
              <Hash size={28} color="var(--accent)" style={{ marginBottom: '0.5rem' }} />
              <div className="stat-value">{Number(data.keyword_frequency || 0).toLocaleString()}</div>
              <div className="stat-label">Frequency of "{data.keyword}" in Database</div>
            </div>
            <div className="glass-card" style={{ textAlign: 'center' }}>
              <div className="stat-value">{Number(data.matched_documents || 0).toLocaleString()}</div>
              <div className="stat-label">Documents Containing "{data.keyword}"</div>
            </div>
          </div>

          <div className="glass-card" style={{ marginBottom: '1.5rem' }}>
            <h3 style={{ marginBottom: '1rem' }}>Top 10 Co-occurring Keywords</h3>
            <div style={{ height: 360 }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={data.cooccurring || []}>
                  <XAxis dataKey="term" stroke="var(--text-dim)" angle={-25} textAnchor="end" height={76} />
                  <YAxis stroke="var(--text-dim)" />
                  <Tooltip />
                  <Bar dataKey="count" fill="var(--accent)" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="glass-card">
            <h3 style={{ marginBottom: '1rem' }}>Keyword Correlation Heatmap</h3>
            <Heatmap labels={data.heatmap?.labels || []} matrix={data.heatmap?.matrix || []} />
          </div>

          <div className="grid-cols-2" style={{ marginTop: '1.5rem' }}>
            <div className="glass-card">
              <h3 style={{ marginBottom: '0.75rem' }}>Posts Containing "{data.keyword}"</h3>
              <p style={{ color: 'var(--text-dim)', marginBottom: '0.8rem' }}>Showing {postSnippets.length} of {postState.total}</p>
              <div style={{ display: 'grid', gap: '0.7rem', maxHeight: 420, overflow: 'auto', paddingRight: '0.3rem' }}>
                {postSnippets.map((p) => (
                  <div key={p.id} className="comment-card">
                    <div style={{ fontWeight: 700, marginBottom: '0.35rem' }}>{p.title || '(No title)'}</div>
                    <div style={{ color: 'var(--text-dim)', fontSize: '0.88rem', marginBottom: '0.35rem' }}>
                      Author: {p.author} | Post ID: {p.id}
                    </div>
                    <div>{String(p.selftext || '').slice(0, 260)}</div>
                  </div>
                ))}
              </div>
              <div style={{ marginTop: '0.9rem' }}>
                {postState.hasMore ? (
                  <button className="btn-secondary" onClick={() => fetchSnippets('posts', postState.offset)} disabled={postState.loading}>
                    {postState.loading ? 'Loading...' : 'Load 5 More Posts'}
                  </button>
                ) : (
                  <p style={{ color: 'var(--text-dim)' }}>No more posts to load.</p>
                )}
              </div>
            </div>

            <div className="glass-card">
              <h3 style={{ marginBottom: '0.75rem' }}>Comments Containing "{data.keyword}"</h3>
              <p style={{ color: 'var(--text-dim)', marginBottom: '0.8rem' }}>Showing {commentSnippets.length} of {commentState.total}</p>
              <div style={{ display: 'grid', gap: '0.7rem', maxHeight: 420, overflow: 'auto', paddingRight: '0.3rem' }}>
                {commentSnippets.map((c) => (
                  <div key={c.id} className="comment-card">
                    <div style={{ color: 'var(--text-dim)', fontSize: '0.88rem', marginBottom: '0.35rem' }}>
                      Author: {c.author} | Comment ID: {c.id} | Post ID: {c.post_id}
                    </div>
                    <div>{String(c.body || '').slice(0, 320)}</div>
                  </div>
                ))}
              </div>
              <div style={{ marginTop: '0.9rem' }}>
                {commentState.hasMore ? (
                  <button className="btn-secondary" onClick={() => fetchSnippets('comments', commentState.offset)} disabled={commentState.loading}>
                    {commentState.loading ? 'Loading...' : 'Load 5 More Comments'}
                  </button>
                ) : (
                  <p style={{ color: 'var(--text-dim)' }}>No more comments to load.</p>
                )}
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function Heatmap({ labels, matrix }) {
  if (!labels.length || !matrix.length) return <p>No heatmap data available.</p>;

  return (
    <div style={{ overflowX: 'auto' }}>
      <table className="heatmap-table">
        <thead>
          <tr>
            <th>Term</th>
            {labels.map((label) => (
              <th key={`h-${label}`}>{label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {matrix.map((row, i) => (
            <tr key={`r-${labels[i] || i}`}>
              <th>{labels[i]}</th>
              {row.map((val, j) => (
                <td
                  key={`c-${i}-${j}`}
                  title={`${labels[i]} x ${labels[j]} = ${val}`}
                  style={{ background: colorForValue(val), color: val >= 0.5 ? '#fff' : 'var(--text-main)' }}
                >
                  {Number(val).toFixed(2)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
