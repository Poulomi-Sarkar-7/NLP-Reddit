import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';
import { Users, FileText, MessageSquare, ArrowRight } from 'lucide-react';
import cardImage from '../assets/card1.jpg';
import cardImageDark from '../assets/card2.jpg';

export default function Home({ theme = 'light' }) {
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
          from the Reddit community on CS Career Questions. Through Natural Language Processing I 
          seek to uncover patterns and trends in the community. I try to analyse sentiments, time trends,persistent topics, top keywords and more in the computer science career sphere.
          Understanding these patterns helps illuminate the collective mindset of modern software engineers and job seekers. Additionally, I aso built a RAG based convresation agent that can answer questions about the data and trends in the subreddit. This project is a testament to the power of data analysis and NLP in extracting insights from large online communities.
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

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '1.25rem', flexWrap: 'wrap' }}>
        <img
          src={theme === 'dark' ? cardImageDark : cardImage}
          alt="Topic card illustration"
          style={{
            width: 'min(100%, 360px)',
            display: 'block',
            borderRadius: '14px',
            border: '1px solid var(--card-border)'
          }}
        />
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', flex: '1 1 220px' }}>
          <Link to="/topics" className="btn-primary" style={{ fontSize: '1.2rem', padding: '1rem 2rem' }}>
            Proceed to Topic Analysis <ArrowRight />
          </Link>
        </div>
      </div>
    </div>
  );
}
