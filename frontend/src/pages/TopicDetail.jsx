import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';
import { ArrowLeft, MessageSquareQuote } from 'lucide-react';

export default function TopicDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState(null);

  useEffect(() => {
    axios.get(`http://localhost:5000/api/topic/${id}`)
      .then(res => setData(res.data))
      .catch(err => console.error(err));
  }, [id]);

  if (!data) return <div style={{ textAlign: 'center', marginTop: '10%' }}>Loading insights...</div>;

  const { info, timeline, stance_counts, top_comments } = data;
  
  // Format for Recharts Pie
  const stanceData = [
    { name: 'Support', value: stance_counts['Support'] || 0 },
    { name: 'Oppose', value: stance_counts['Oppose'] || 0 },
    { name: 'Neutral', value: stance_counts['Neutral'] || 0 }
  ];
  const STANCE_COLORS = ['#4ade80', '#f87171', '#94a3b8'];

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
            {info.keywords.split(', ').map(kw => (
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
                <XAxis dataKey="year" stroke="var(--text-dim)" />
                <YAxis stroke="var(--text-dim)" />
                <Tooltip contentStyle={{ backgroundColor: 'var(--card-bg)', border: '1px solid var(--accent)' }} />
                <Line type="monotone" dataKey="count" stroke="var(--accent)" strokeWidth={4} dot={{ r: 4 }} activeDot={{ r: 8 }} />
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

      <div className="grid-cols-2">
        <div className="glass-card">
          <h3 style={{ marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#4ade80' }}>
            <MessageSquareQuote /> Supporting Arguments
          </h3>
          <p style={{ color: 'var(--text-dim)', marginBottom: '1rem', fontStyle: 'italic', fontSize: '0.95rem' }}>
            <strong>AI Snapshot:</strong> {info.support_summary}
          </p>
          <div style={{ marginTop: '2rem' }}>
            {top_comments.support.map((c, i) => <div key={i} className="comment-card comment-support">"{c}"</div>)}
          </div>
        </div>

        <div className="glass-card">
          <h3 style={{ marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#f87171' }}>
            <MessageSquareQuote /> Opposing Arguments
          </h3>
          <p style={{ color: 'var(--text-dim)', marginBottom: '1rem', fontStyle: 'italic', fontSize: '0.95rem' }}>
            <strong>AI Snapshot:</strong> {info.oppose_summary}
          </p>
          <div style={{ marginTop: '2rem' }}>
            {top_comments.oppose.map((c, i) => <div key={i} className="comment-card comment-oppose">"{c}"</div>)}
          </div>
        </div>
      </div>
    </div>
  );
}
