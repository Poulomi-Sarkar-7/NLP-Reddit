import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, Legend } from 'recharts';

const COLORS = [
  '#853953', '#ab4b6d', '#bc6282', 
  '#612D53', '#793c68', '#914b7e', 
  '#401d36', '#2C2C2C', '#5a5a5a', '#8a8a8a'
];

export default function Topics() {
  const [topics, setTopics] = useState([]);
  const navigate = useNavigate();

  useEffect(() => {
    axios.get('http://localhost:5000/api/topics')
      .then(res => setTopics(res.data))
      .catch(err => console.error(err));
  }, []);

  const handleChartClick = (data) => {
    if(data && data.topic_id) {
       navigate(`/topic/${data.topic_id}`);
    }
  };

  return (
    <div style={{ animation: 'fadeIn 0.5s ease' }}>
      <div className="section-title">Topic Landscape</div>
      <p style={{ color: 'var(--text-dim)', marginBottom: '2rem' }}>
        Click on any chart element or topic box below to dive into the specific analysis, stance breakdowns, and timeline.
      </p>

      <div className="grid-cols-2" style={{ marginBottom: '3rem' }}>
        <div className="glass-card">
          <h3 style={{ marginBottom: '1.5rem', textAlign: 'center' }}>Topic Distribution (Bar)</h3>
          <div style={{ height: 300 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={topics} onClick={(data) => {
                  if (data && data.activePayload && data.activePayload.length > 0) {
                      handleChartClick(data.activePayload[0].payload);
                  }
              }}>
                <XAxis dataKey="topic_id" stroke="var(--text-dim)"/>
                <YAxis stroke="var(--text-dim)"/>
                <Tooltip cursor={{ fill: 'rgba(255,255,255,0.05)' }} contentStyle={{ backgroundColor: 'var(--card-bg)', border: '1px solid var(--accent)' }}/>
                <Bar dataKey="share" fill="var(--accent-light)" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="glass-card">
          <h3 style={{ marginBottom: '1.5rem', textAlign: 'center' }}>Topic Share (Donut)</h3>
          <div style={{ height: 300 }}>
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={topics}
                  cx="50%" cy="50%"
                  innerRadius={80}
                  outerRadius={120}
                  paddingAngle={5}
                  dataKey="share"
                  nameKey="label"
                  onClick={handleChartClick}
                >
                  {topics.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} style={{ cursor: 'pointer', outline: 'none' }}/>
                  ))}
                </Pie>
                <Tooltip contentStyle={{ backgroundColor: 'var(--card-bg)', border: '1px solid var(--accent)', color: 'white' }}/>
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <h3 style={{ marginBottom: '1.5rem', fontSize: '1.3rem' }}>Topic Breakdown</h3>
      <div className="grid-cols-3">
        {topics.map(topic => (
          <div key={topic.topic_id} className="topic-box" onClick={() => navigate(`/topic/${topic.topic_id}`)}>
            <div>
              <div style={{ fontWeight: '800', marginBottom: '0.5rem', color: 'var(--accent)' }}>
                Topic {topic.topic_id}: {topic.label}
              </div>
            </div>
            <span className={`tag tag-${topic.status.toLowerCase()}`}>
              {topic.status}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
