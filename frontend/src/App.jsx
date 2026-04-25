import React, { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Link } from 'react-router-dom';
import Home from './pages/Home';
import Topics from './pages/Topics';
import TopicDetail from './pages/TopicDetail';
import ConsolidatedTimeline from './pages/ConsolidatedTimeline';
import ConversationSystem from './pages/ConversationSystem';
import Users from './pages/Users';
import Keywords from './pages/Keywords';
import Sorting from './pages/Sorting';
import { LayoutDashboard, Moon, Sun, TrendingUp, MessageCircle, Users as UsersIcon, KeyRound, ArrowUpDown } from 'lucide-react';
import dashImage from './assets/dash1.jpg';
import dashImageDark from './assets/dash2.jpg';

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
        <div style={{ marginBottom: '1rem' }}>
          <img
            src={theme === 'dark' ? dashImageDark : dashImage}
            alt="Dashboard banner"
            style={{
              width: '100%',
              display: 'block',
              borderRadius: '16px',
              border: '1px solid var(--card-border)'
            }}
          />
        </div>
        <header className="header-nav">
          <Link to="/" className="logo flex items-center" style={{ display: 'flex', alignItems: 'center' }}>
            <LayoutDashboard className="mr-2" style={{ marginRight: '0.5rem' }} /> NLP Explorer
          </Link>
          <nav style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
            <Link to="/topics" className="btn-secondary">Topics List</Link>
            <Link to="/timeline" className="btn-secondary"><TrendingUp size={16} style={{marginRight: 4}}/> Timeline</Link>
            <Link to="/conversation" className="btn-secondary"><MessageCircle size={16} style={{marginRight: 4}}/> Conversation</Link>
            <Link to="/users" className="btn-secondary"><UsersIcon size={16} style={{marginRight: 4}}/> Users</Link>
            <Link to="/keywords" className="btn-secondary"><KeyRound size={16} style={{marginRight: 4}}/> Keywords</Link>
            <Link to="/sorting" className="btn-secondary"><ArrowUpDown size={16} style={{marginRight: 4}}/> Sorting</Link>
            <button onClick={toggleTheme} className="btn-secondary" title="Toggle Theme" style={{ padding: '0.5rem' }}>
              {theme === 'light' ? <Moon size={18} /> : <Sun size={18} />}
            </button>
          </nav>
        </header>
        
        <main>
          <Routes>
            <Route path="/" element={<Home theme={theme} />} />
            <Route path="/topics" element={<Topics />} />
            <Route path="/topic/:id" element={<TopicDetail />} />
            <Route path="/timeline" element={<ConsolidatedTimeline />} />
            <Route path="/conversation" element={<ConversationSystem />} />
            <Route path="/users" element={<Users />} />
            <Route path="/keywords" element={<Keywords />} />
            <Route path="/sorting" element={<Sorting />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}

export default App;
