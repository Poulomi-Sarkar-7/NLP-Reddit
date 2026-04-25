import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { ArrowDownAZ, ArrowUpAZ } from 'lucide-react';

const METRIC_OPTIONS = [
  { value: 'most_comments', label: 'Most Comments' },
  { value: 'avg_comment_length', label: 'Average Length of Comments in Topics' },
  { value: 'mean_positive_sentiment', label: 'Mean Positive Sentiment' },
  { value: 'mean_negative_sentiment', label: 'Mean Negative Sentiment' },
  { value: 'mean_neutral_sentiment', label: 'Mean Neutral Sentiment' },
  { value: 'profanity', label: 'Profanity' },
  { value: 'non_english_words', label: 'Number of Non-English Words' }
];

export default function Sorting() {
  const [metric, setMetric] = useState('most_comments');
  const [order, setOrder] = useState('desc');
  const [data, setData] = useState({ topics: [], metric_label: '' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    setLoading(true);
    setError('');
    axios.get(`http://localhost:5000/api/sorting/topics?metric=${encodeURIComponent(metric)}&order=${order}`)
      .then(res => setData(res.data))
      .catch(e => setError(e?.response?.data?.error || 'Failed to fetch sorted topics.'))
      .finally(() => setLoading(false));
  }, [metric, order]);

  return (
    <div style={{ animation: 'fadeIn 0.5s ease' }}>
      <div className="section-title">Sorting</div>
      <p style={{ color: 'var(--text-dim)', marginBottom: '1.5rem' }}>
        Sort all topics by selected metric. You can switch ascending/descending at any time.
      </p>

      <div className="glass-card" style={{ marginBottom: '1.5rem' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: '0.75rem' }}>
          <select className="conversation-input" value={metric} onChange={(e) => setMetric(e.target.value)}>
            {METRIC_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
          <button className="btn-secondary" onClick={() => setOrder(prev => prev === 'asc' ? 'desc' : 'asc')}>
            {order === 'asc' ? <ArrowUpAZ size={16} style={{ marginRight: 4 }} /> : <ArrowDownAZ size={16} style={{ marginRight: 4 }} />}
            {order === 'asc' ? 'Ascending' : 'Descending'}
          </button>
        </div>
      </div>

      {error && (
        <div className="glass-card" style={{ borderColor: '#f87171', marginBottom: '1.5rem' }}>
          <h3 style={{ color: '#f87171', marginBottom: '0.35rem' }}>Error</h3>
          <p>{error}</p>
        </div>
      )}

      <div className="glass-card">
        <h3 style={{ marginBottom: '1rem' }}>
          Topics sorted by: {data.metric_label || METRIC_OPTIONS.find(m => m.value === metric)?.label}
        </h3>
        {loading ? (
          <p>Sorting topics...</p>
        ) : (
          <div style={{ display: 'grid', gap: '0.75rem' }}>
            {(data.topics || []).map((t) => (
              <div key={t.topic_id} className="topic-box" style={{ cursor: 'default' }}>
                <div>
                  <div style={{ fontWeight: 800, color: 'var(--accent)' }}>
                    #{t.rank} Topic {t.topic_id}: {t.label}
                  </div>
                  <div style={{ color: 'var(--text-dim)', fontSize: '0.9rem' }}>
                    Status: {t.status}
                  </div>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <div style={{ fontWeight: 700 }}>{t.metric_display}</div>
                  <div style={{ color: 'var(--text-dim)', fontSize: '0.8rem' }}>{t.metric_label}</div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
