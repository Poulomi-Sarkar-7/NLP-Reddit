import React, { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Link } from 'react-router-dom';
import Home from './pages/Home';
import Topics from './pages/Topics';
import TopicDetail from './pages/TopicDetail';
import ConsolidatedTimeline from './pages/ConsolidatedTimeline';
import ConversationSystem from './pages/ConversationSystem';
import { LayoutDashboard, Moon, Sun, TrendingUp, MessageCircle } from 'lucide-react';

function App() {
  const [theme, setTheme] = useState('light');

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme(prev => prev === 'light' ? 'dark' : 'light');
  };

  return (
    <BrowserRouter>
      <div className="app-container">
        <header className="header-nav">
          <Link to="/" className="logo flex items-center" style={{ display: 'flex', alignItems: 'center' }}>
            <LayoutDashboard className="mr-2" style={{ marginRight: '0.5rem' }} /> NLP Explorer
          </Link>
          <nav style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
            <Link to="/topics" className="btn-secondary">Topics List</Link>
            <Link to="/timeline" className="btn-secondary"><TrendingUp size={16} style={{marginRight: 4}}/> Timeline</Link>
            <Link to="/conversation" className="btn-secondary"><MessageCircle size={16} style={{marginRight: 4}}/> Conversation</Link>
            <button onClick={toggleTheme} className="btn-secondary" title="Toggle Theme" style={{ padding: '0.5rem' }}>
              {theme === 'light' ? <Moon size={18} /> : <Sun size={18} />}
            </button>
          </nav>
        </header>
        
        <main>
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/topics" element={<Topics />} />
            <Route path="/topic/:id" element={<TopicDetail />} />
            <Route path="/timeline" element={<ConsolidatedTimeline />} />
            <Route path="/conversation" element={<ConversationSystem />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}

export default App;
