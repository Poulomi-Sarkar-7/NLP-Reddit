import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';
import { Users, FileText, MessageSquare, ArrowRight } from 'lucide-react';

export default function Home() {
  const [stats, setStats] = useState({ total_posts: 0, total_users: 0, total_comments: 0 });

  useEffect(() => {
    axios.get('http://localhost:5000/api/dashboard')
      .then(res => setStats(res.data))
      .catch(err => console.error(err));
  }, []);

  return (
    <div style={{ animation: 'fadeIn 0.5s ease' }}>
      <div className="glass-card" style={{ marginBottom: '2rem' }}>
        <h1 style={{ fontSize: '2rem', marginBottom: '1rem' }}>Reddit Deep Dive: cscareerquestions</h1>
        <p style={{ lineHeight: '1.6', fontSize: '1.1rem', color: 'var(--text-dim)' }}>
          This project analyzes over {stats.total_posts.toLocaleString()} posts and {stats.total_comments.toLocaleString()} comments 
          from the Reddit community. Through Natural Language Processing—specifically Topic Modeling and Sentiment Stance Detection—we 
          seek to uncover the most pressing issues, persistent trends, and controversial discussions in the computer science career sphere.
          Understanding these patterns helps illuminate the collective mindset of modern software engineers and job seekers.
        </p>
      </div>

      <h2 className="section-title">Database Summary</h2>
      <div className="grid-cols-3" style={{ marginBottom: '3rem' }}>
        <div className="glass-card" style={{ textAlign: 'center' }}>
          <FileText size={40} color="var(--accent-light)" style={{ margin: '0 auto 1rem' }}/>
          <div className="stat-value">{stats.total_posts.toLocaleString()}</div>
          <div className="stat-label">Total Posts</div>
        </div>
        <div className="glass-card" style={{ textAlign: 'center' }}>
          <Users size={40} color="var(--accent-light)" style={{ margin: '0 auto 1rem' }}/>
          <div className="stat-value">{stats.total_users.toLocaleString()}</div>
          <div className="stat-label">Unique Users</div>
        </div>
        <div className="glass-card" style={{ textAlign: 'center' }}>
          <MessageSquare size={40} color="var(--accent-light)" style={{ margin: '0 auto 1rem' }}/>
          <div className="stat-value">{stats.total_comments.toLocaleString()}</div>
          <div className="stat-label">Total Comments</div>
        </div>
      </div>

      <div style={{ textAlign: 'center' }}>
        <Link to="/topics" className="btn-primary" style={{ fontSize: '1.2rem', padding: '1rem 2rem' }}>
          Proceed to Topic Analysis <ArrowRight />
        </Link>
      </div>
    </div>
  );
}
