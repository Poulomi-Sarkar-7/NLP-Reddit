import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { FileText } from 'lucide-react';

export default function Reports() {
  const [reports, setReports] = useState([]);
  const [selected, setSelected] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    axios.get('http://localhost:5000/api/reports/list')
      .then((res) => {
        const items = res.data.reports || [];
        setReports(items);
        if (items.length) setSelected(items[0].id);
      })
      .catch((e) => {
        setError(e?.response?.data?.error || 'Failed to load reports list.');
      });
  }, []);

  const selectedUrl = selected ? `http://localhost:5000/api/reports/file/${selected}` : '';

  return (
    <div style={{ animation: 'fadeIn 0.5s ease' }}>
      <div className="section-title">Reports</div>
      <p style={{ color: 'var(--text-dim)', marginBottom: '1.5rem' }}>
        Select a report label to view the PDF.
      </p>

      {error && (
        <div className="glass-card" style={{ borderColor: '#f87171', marginBottom: '1.5rem' }}>
          <h3 style={{ color: '#f87171', marginBottom: '0.35rem' }}>Error</h3>
          <p>{error}</p>
        </div>
      )}

      <div className="grid-cols-2">
        <div className="glass-card">
          <h3 style={{ marginBottom: '1rem' }}>Available Reports</h3>
          <div style={{ display: 'grid', gap: '0.65rem' }}>
            {reports.map((r) => (
              <button
                key={r.id}
                className="btn-secondary"
                style={{
                  justifyContent: 'flex-start',
                  borderColor: selected === r.id ? 'var(--accent)' : 'var(--card-border)',
                  background: selected === r.id ? 'rgba(133,57,83,0.08)' : 'transparent'
                }}
                onClick={() => setSelected(r.id)}
              >
                <FileText size={16} style={{ marginRight: 8 }} /> {r.label}
              </button>
            ))}
          </div>
        </div>

        <div className="glass-card">
          <h3 style={{ marginBottom: '1rem' }}>Preview</h3>
          {selected ? (
            <iframe
              title="Report Preview"
              src={selectedUrl}
              style={{ width: '100%', height: '80vh', border: '1px solid var(--card-border)', borderRadius: '8px' }}
            />
          ) : (
            <p style={{ color: 'var(--text-dim)' }}>Select a report to view.</p>
          )}
        </div>
      </div>
    </div>
  );
}
