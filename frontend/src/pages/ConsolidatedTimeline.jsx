import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { 
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend, 
  LineChart, Line 
} from 'recharts';

// Distinct colors blending the aubergine/charcoal aesthetic
const TOPIC_COLORS = [
  '#853953', '#ab4b6d', '#bc6282', 
  '#612D53', '#793c68', '#914b7e', 
  '#401d36', '#2C2C2C', '#5a5a5a', '#8a8a8a'
];

export default function ConsolidatedTimeline() {
  const [data, setData] = useState({ timeline: [], topics: [] });

  useEffect(() => {
    axios.get('http://localhost:5000/api/timeline_consolidated')
      .then(res => setData(res.data))
      .catch(err => console.error(err));
  }, []);

  if (!data.timeline.length) return <div style={{ textAlign: 'center', marginTop: '10%' }}>Loading timeline...</div>;

  return (
    <div style={{ animation: 'fadeIn 0.5s ease' }}>
      <div className="section-title">Consolidated Time Series</div>
      
      <div className="glass-card" style={{ marginBottom: '2rem' }}>
        <p style={{ lineHeight: '1.6', fontSize: '1.05rem' }}>
          This visual aggregates all dynamically discovered conversational topics across the extracted Reddit span.
          By filtering out the structurally removed/deleted posts, our distributions are cleanly separated.
          <br /><br />
          <strong>Stacked Area Perspective:</strong> Excellent for visualizing total subreddit volume growth while understanding which topics structurally uphold that growth.
          <br />
          <strong>Multi-Line Perspective:</strong> Essential for analyzing independent velocity bursts (Trending vs Persistent) strictly on a localized basis.
        </p>
      </div>

      <div className="glass-card" style={{ marginBottom: '3rem' }}>
        <h3 style={{ marginBottom: '1.5rem', textAlign: 'center', color: 'var(--accent)' }}>Summative Volume (Stacked Area Chart)</h3>
        <div style={{ height: 400 }}>
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data.timeline} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
              <XAxis dataKey="year" stroke="var(--text-dim)"/>
              <YAxis stroke="var(--text-dim)"/>
              <Tooltip contentStyle={{ backgroundColor: 'var(--card-bg)', border: '1px solid var(--accent)', color: 'var(--text-main)' }}/>
              <Legend />
              {data.topics.map((t, idx) => (
                <Area 
                  key={t.id} 
                  type="monotone" 
                  dataKey={`Topic ${t.id}`} 
                  name={`T${t.id}: ${t.label}`}
                  stackId="1" 
                  stroke={TOPIC_COLORS[idx % TOPIC_COLORS.length]} 
                  fill={TOPIC_COLORS[idx % TOPIC_COLORS.length]} 
                />
              ))}
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="glass-card">
        <h3 style={{ marginBottom: '1.5rem', textAlign: 'center', color: 'var(--accent-dark)' }}>Independent Velocity (Multi-Line Chart)</h3>
        <div style={{ height: 400 }}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data.timeline} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
              <XAxis dataKey="year" stroke="var(--text-dim)"/>
              <YAxis stroke="var(--text-dim)"/>
              <Tooltip contentStyle={{ backgroundColor: 'var(--bg-color)', border: '1px solid var(--accent)', color: 'var(--text-main)' }}/>
              <Legend />
              {data.topics.map((t, idx) => (
                <Line 
                  key={t.id} 
                  type="monotone" 
                  dataKey={`Topic ${t.id}`} 
                  name={`T${t.id}: ${t.label}`}
                  stroke={TOPIC_COLORS[idx % TOPIC_COLORS.length]} 
                  strokeWidth={2}
                  dot={{ r: 2 }}
                  activeDot={{ r: 6 }}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

    </div>
  );
}
