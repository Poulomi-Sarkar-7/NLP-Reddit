import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { UserSearch, MessageSquareText, FileText } from 'lucide-react';

function TopUsersTooltip({ active, payload }) {
  if (!active || !payload || !payload.length) return null;
  const row = payload[0].payload;
  return (
    <div style={{ background: 'var(--card-bg)', border: '1px solid var(--accent)', padding: '0.6rem 0.8rem', borderRadius: 8 }}>
      <div style={{ fontWeight: 700 }}>{row.author}</div>
      <div style={{ fontSize: '0.9rem', color: 'var(--text-dim)' }}>Posts: {row.posts_count}</div>
      <div style={{ fontSize: '0.9rem', color: 'var(--text-dim)' }}>Comments: {row.comments_count}</div>
    </div>
  );
}

export default function Users() {
  const [username, setUsername] = useState('');
  const [queryData, setQueryData] = useState(null);
  const [topUsers, setTopUsers] = useState([]);
  const [loadingTop, setLoadingTop] = useState(false);
  const [loadingUser, setLoadingUser] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    setLoadingTop(true);
    axios.get('http://localhost:5000/api/users/top?limit=20')
      .then(res => setTopUsers(res.data.users || []))
      .catch(err => {
        console.error(err);
        setError('Could not load top users.');
      })
      .finally(() => setLoadingTop(false));
  }, []);

  const runUserQuery = async () => {
    const q = username.trim();
    if (!q) return;
    setLoadingUser(true);
    setError('');
    setQueryData(null);
    try {
      const res = await axios.get(`http://localhost:5000/api/users/query?username=${encodeURIComponent(q)}`);
      setQueryData(res.data);
    } catch (e) {
      setError(e?.response?.data?.error || 'Failed to fetch user data.');
    } finally {
      setLoadingUser(false);
    }
  };

  return (
    <div style={{ animation: 'fadeIn 0.5s ease' }}>
      <div className="section-title">Users</div>
      <p style={{ color: 'var(--text-dim)', marginBottom: '1.5rem' }}>
        Search a Reddit username to view their posts/comments, and explore top active users from the dataset.
      </p>

      <div className="glass-card" style={{ marginBottom: '1.5rem' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: '0.75rem' }}>
          <input
            className="conversation-input"
            placeholder="Enter Reddit username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && runUserQuery()}
          />
          <button className="btn-primary" onClick={runUserQuery} disabled={loadingUser}>
            <UserSearch size={16} /> {loadingUser ? 'Searching...' : 'Fetch User'}
          </button>
        </div>
      </div>

      {error && (
        <div className="glass-card" style={{ borderColor: '#f87171', marginBottom: '1.5rem' }}>
          <h3 style={{ color: '#f87171', marginBottom: '0.35rem' }}>Error</h3>
          <p>{error}</p>
        </div>
      )}

      {queryData && (
        <div className="glass-card" style={{ marginBottom: '1.5rem' }}>
          {!queryData.found ? (
            <p>No matching user found for <strong>{queryData.username}</strong>.</p>
          ) : (
            <>
              <h3 style={{ marginBottom: '0.75rem' }}>User: {queryData.username}</h3>
              <p style={{ color: 'var(--text-dim)', marginBottom: '1rem' }}>
                Posts fetched: {queryData.posts_count} | Comments fetched: {queryData.comments_count}
              </p>

              <div className="grid-cols-2">
                <div>
                  <h4 style={{ marginBottom: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <FileText size={16} /> Posts
                  </h4>
                  <div style={{ display: 'grid', gap: '0.75rem', maxHeight: 420, overflow: 'auto', paddingRight: '0.35rem' }}>
                    {(queryData.posts || []).map((p) => (
                      <div key={p.id} className="comment-card">
                        <div style={{ fontWeight: 700, marginBottom: '0.35rem' }}>{p.title || '(No title)'}</div>
                        <div style={{ color: 'var(--text-dim)', fontSize: '0.9rem' }}>
                          Post ID: {p.id} | Comments: {p.num_comments || 0}
                        </div>
                        {p.selftext && <div style={{ marginTop: '0.45rem' }}>{String(p.selftext).slice(0, 280)}</div>}
                      </div>
                    ))}
                  </div>
                </div>
                <div>
                  <h4 style={{ marginBottom: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <MessageSquareText size={16} /> Comments
                  </h4>
                  <div style={{ display: 'grid', gap: '0.75rem', maxHeight: 420, overflow: 'auto', paddingRight: '0.35rem' }}>
                    {(queryData.comments || []).map((c) => (
                      <div key={c.id} className="comment-card">
                        <div style={{ color: 'var(--text-dim)', fontSize: '0.9rem', marginBottom: '0.35rem' }}>
                          Comment ID: {c.id} | Post ID: {c.post_id}
                        </div>
                        <div>{String(c.body || '').slice(0, 320)}</div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </>
          )}
        </div>
      )}

      <div className="glass-card">
        <h3 style={{ marginBottom: '1rem' }}>Top Users by Activity (Posts + Comments)</h3>
        {loadingTop ? (
          <p>Loading top users...</p>
        ) : (
          <div style={{ height: 420 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={topUsers}>
                <XAxis dataKey="bar_label" stroke="var(--text-dim)" />
                <YAxis stroke="var(--text-dim)" />
                <Tooltip content={<TopUsersTooltip />} />
                <Legend />
                <Bar dataKey="posts_count" name="Posts" fill="var(--accent)" />
                <Bar dataKey="comments_count" name="Comments" fill="var(--accent-light)" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </div>
  );
}
