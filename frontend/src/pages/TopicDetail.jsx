import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';
import { ArrowLeft, MessageSquareQuote } from 'lucide-react';

export default function TopicDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [stanceComments, setStanceComments] = useState({ support: [], oppose: [], neutral: [] });
  const [stanceState, setStanceState] = useState({
    support: { offset: 5, hasMore: false, loading: false, total: 0 },
    oppose: { offset: 5, hasMore: false, loading: false, total: 0 },
    neutral: { offset: 5, hasMore: false, loading: false, total: 0 }
  });
  const [profanity, setProfanity] = useState({ top_words: [], comments: [], has_more: false, total_comments_with_profanity: 0 });
  const [profanityState, setProfanityState] = useState({ offset: 5, hasMore: false, loading: false, total: 0 });

  useEffect(() => {
    setError('');
    axios.get(`http://localhost:5000/api/topic/${id}`)
      .then(res => {
        setData(res.data);
        const tc = res.data.top_comments || {};
        setStanceComments({
          support: tc.support || [],
          oppose: tc.oppose || [],
          neutral: tc.neutral || []
        });
        const sc = res.data.stance_counts || {};
        setStanceState({
          support: { offset: (tc.support || []).length, hasMore: (tc.support || []).length < (sc.Support || 0), loading: false, total: sc.Support || 0 },
          oppose: { offset: (tc.oppose || []).length, hasMore: (tc.oppose || []).length < (sc.Oppose || 0), loading: false, total: sc.Oppose || 0 },
          neutral: { offset: (tc.neutral || []).length, hasMore: (tc.neutral || []).length < (sc.Neutral || 0), loading: false, total: sc.Neutral || 0 }
        });
        const p = res.data.profanity || {};
        setProfanity({
          top_words: p.top_words || [],
          comments: p.comments || [],
          has_more: !!p.has_more,
          total_comments_with_profanity: p.total_comments_with_profanity || 0
        });
        setProfanityState({
          offset: (p.comments || []).length,
          hasMore: !!p.has_more,
          loading: false,
          total: p.total_comments_with_profanity || 0
        });
      })
      .catch(err => {
        console.error(err);
        setError('Could not load topic insights. Please try again.');
      });
  }, [id]);

  if (error) return <div style={{ textAlign: 'center', marginTop: '10%' }}>{error}</div>;
  if (!data) return <div style={{ textAlign: 'center', marginTop: '10%' }}>Loading insights...</div>;

  const { info, timeline, stance_counts } = data;
  const cleanedKeywords = (info.keywords || '')
    .split(', ')
    .map(k => k.trim())
    .filter(Boolean);
  
  // Format for Recharts Pie
  const stanceData = [
    { name: 'Support', value: stance_counts['Support'] || 0 },
    { name: 'Oppose', value: stance_counts['Oppose'] || 0 },
    { name: 'Neutral', value: stance_counts['Neutral'] || 0 }
  ];
  const STANCE_COLORS = ['#4ade80', '#f87171', '#94a3b8'];

  const loadMoreStance = async (key, apiStance) => {
    setStanceState(prev => ({ ...prev, [key]: { ...prev[key], loading: true } }));
    try {
      const res = await axios.get(
        `http://localhost:5000/api/topic/${id}/comments?stance=${encodeURIComponent(apiStance)}&offset=${stanceState[key].offset}&limit=5`
      );
      const payload = res.data || {};
      setStanceComments(prev => ({ ...prev, [key]: [...(prev[key] || []), ...(payload.items || [])] }));
      setStanceState(prev => ({
        ...prev,
        [key]: {
          ...prev[key],
          loading: false,
          offset: payload.next_offset || prev[key].offset,
          hasMore: !!payload.has_more,
          total: payload.total || prev[key].total
        }
      }));
    } catch (e) {
      setStanceState(prev => ({ ...prev, [key]: { ...prev[key], loading: false } }));
    }
  };

  const loadMoreProfanity = async () => {
    setProfanityState(prev => ({ ...prev, loading: true }));
    try {
      const res = await axios.get(
        `http://localhost:5000/api/topic/${id}/profanity?offset=${profanityState.offset}&limit=5`
      );
      const payload = res.data || {};
      setProfanity(prev => ({
        ...prev,
        top_words: payload.top_words || prev.top_words,
        comments: [...(prev.comments || []), ...(payload.items || [])]
      }));
      setProfanityState(prev => ({
        ...prev,
        loading: false,
        offset: payload.next_offset || prev.offset,
        hasMore: !!payload.has_more,
        total: payload.total || prev.total
      }));
    } catch (e) {
      setProfanityState(prev => ({ ...prev, loading: false }));
    }
  };

  // Determine Popular Stance
  let popularStance = "Neutral";
  let maxVal = 0;
  stanceData.forEach(s => {
    if (s.value > maxVal) {
      maxVal = s.value;
      popularStance = s.name;
    }
  });

  return (
    <div style={{ animation: 'fadeIn 0.5s ease' }}>
      <button className="btn-secondary" onClick={() => navigate('/topics')} style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem', marginBottom: '2rem' }}>
        <ArrowLeft size={16}/> Back to Topics
      </button>

      <div className="glass-card" style={{ marginBottom: '2rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <h1 style={{ color: 'var(--accent)', marginBottom: '0.5rem', fontWeight: 800 }}>Topic {info.topic_id}: {info.label}</h1>
            <p style={{ color: 'var(--text-dim)', fontStyle: 'italic', marginBottom: '1.5rem' }}>
              Classification: <span style={{ color: 'white' }}>{info.status}</span>
            </p>
          </div>
        </div>
        <p style={{ lineHeight: '1.6', fontSize: '1.05rem', marginBottom: '1.5rem' }}>{info.description}</p>
        <div>
          <h4 style={{ marginBottom: '0.5rem', color: 'var(--text-dim)' }}>Top Keywords</h4>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
            {cleanedKeywords.map(kw => (
              <span key={kw} style={{ background: 'rgba(34, 112, 106, 0.3)', padding: '0.3rem 0.8rem', borderRadius: '4px', fontSize: '0.9rem' }}>
                {kw}
              </span>
            ))}
          </div>
        </div>
      </div>

      <div className="grid-cols-2" style={{ marginBottom: '3rem' }}>
        <div className="glass-card">
          <h3 style={{ marginBottom: '1.5rem', textAlign: 'center' }}>Time Series Analysis (Frequency)</h3>
          <div style={{ height: 300 }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={timeline}>
                <XAxis dataKey="period" stroke="var(--text-dim)" />
                <YAxis stroke="var(--text-dim)" />
                <Tooltip contentStyle={{ backgroundColor: 'var(--card-bg)', border: '1px solid var(--accent)' }} />
                <Line type="linear" dataKey="count" stroke="var(--accent)" strokeWidth={4} dot={{ r: 3 }} activeDot={{ r: 7 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="glass-card">
          <h3 style={{ marginBottom: '0.5rem', textAlign: 'center' }}>Stance Detection</h3>
          <p style={{ textAlign: 'center', color: 'var(--text-dim)', marginBottom: '1rem', fontSize: '0.9rem' }}>
            Popular Stance: <strong style={{ color: popularStance === 'Support' ? '#4ade80' : popularStance === 'Oppose' ? '#f87171' : '#94a3b8' }}>{popularStance}</strong>
          </p>
          <div style={{ height: 250 }}>
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={stanceData}
                  cx="50%" cy="50%"
                  outerRadius={90}
                  dataKey="value"
                  label={({name, percent}) => `${name} ${(percent * 100).toFixed(0)}%`}
                >
                  {stanceData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={STANCE_COLORS[index % STANCE_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip contentStyle={{ backgroundColor: 'var(--card-bg)', border: 'none', color: 'white' }} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="glass-card">
        <div className="comment-split-grid-3">
          <div>
            <h3 style={{ marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#4ade80' }}>
              <MessageSquareQuote /> Supporting Arguments
            </h3>
            <p style={{ color: 'var(--text-dim)', marginBottom: '1rem', fontStyle: 'italic', fontSize: '0.95rem' }}>
              <strong>AI Snapshot:</strong> {info.support_summary}
            </p>
            <ol className="comment-list">
              {stanceComments.support.map((c, i) => <li key={i} className="comment-card comment-support">"{c}"</li>)}
            </ol>
            {stanceState.support.hasMore ? (
              <button className="btn-secondary" onClick={() => loadMoreStance('support', 'Support')} disabled={stanceState.support.loading}>
                {stanceState.support.loading ? 'Loading...' : 'Load 5 More'}
              </button>
            ) : (
              <p style={{ color: 'var(--text-dim)', fontSize: '0.9rem' }}>No more comments.</p>
            )}
          </div>

          <div>
            <h3 style={{ marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#f87171' }}>
              <MessageSquareQuote /> Opposing Arguments
            </h3>
            <p style={{ color: 'var(--text-dim)', marginBottom: '1rem', fontStyle: 'italic', fontSize: '0.95rem' }}>
              <strong>AI Snapshot:</strong> {info.oppose_summary}
            </p>
            <ol className="comment-list">
              {stanceComments.oppose.map((c, i) => <li key={i} className="comment-card comment-oppose">"{c}"</li>)}
            </ol>
            {stanceState.oppose.hasMore ? (
              <button className="btn-secondary" onClick={() => loadMoreStance('oppose', 'Oppose')} disabled={stanceState.oppose.loading}>
                {stanceState.oppose.loading ? 'Loading...' : 'Load 5 More'}
              </button>
            ) : (
              <p style={{ color: 'var(--text-dim)', fontSize: '0.9rem' }}>No more comments.</p>
            )}
          </div>

          <div>
            <h3 style={{ marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#94a3b8' }}>
              <MessageSquareQuote /> Neutral Statements
            </h3>
            <p style={{ color: 'var(--text-dim)', marginBottom: '1rem', fontStyle: 'italic', fontSize: '0.95rem' }}>
              <strong>AI Snapshot:</strong> {info.neutral_summary}
            </p>
            <ol className="comment-list">
              {stanceComments.neutral.map((c, i) => <li key={i} className="comment-card">"{c}"</li>)}
            </ol>
            {stanceState.neutral.hasMore ? (
              <button className="btn-secondary" onClick={() => loadMoreStance('neutral', 'Neutral')} disabled={stanceState.neutral.loading}>
                {stanceState.neutral.loading ? 'Loading...' : 'Load 5 More'}
              </button>
            ) : (
              <p style={{ color: 'var(--text-dim)', fontSize: '0.9rem' }}>No more comments.</p>
            )}
          </div>
        </div>
      </div>

      <div className="glass-card" style={{ marginTop: '1.5rem' }}>
        <h3 style={{ marginBottom: '1rem' }}>Profanity Check</h3>
        <p style={{ color: 'var(--text-dim)', marginBottom: '0.8rem' }}>
          Comments with profanity in this topic: {profanityState.total}
        </p>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', marginBottom: '1rem' }}>
          {(profanity.top_words || []).map((w) => (
            <span key={w.word} style={{ background: 'rgba(248, 113, 113, 0.15)', border: '1px solid rgba(248, 113, 113, 0.35)', padding: '0.3rem 0.65rem', borderRadius: '999px', fontSize: '0.85rem' }}>
              {w.word} ({w.count})
            </span>
          ))}
        </div>

        <div style={{ display: 'grid', gap: '0.75rem' }}>
          {(profanity.comments || []).map((c, i) => (
            <div key={i} className="comment-card comment-oppose">"{c}"</div>
          ))}
        </div>
        <div style={{ marginTop: '0.9rem' }}>
          {profanityState.hasMore ? (
            <button className="btn-secondary" onClick={loadMoreProfanity} disabled={profanityState.loading}>
              {profanityState.loading ? 'Loading...' : 'Load 5 More'}
            </button>
          ) : (
            <p style={{ color: 'var(--text-dim)', fontSize: '0.9rem' }}>No more profanity comments.</p>
          )}
        </div>
      </div>
    </div>
  );
}
