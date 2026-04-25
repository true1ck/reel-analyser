import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { fetchJobs, fetchCollections } from '../utils/api';
import { getCategoryMeta } from './CollectionsPage';

const STATUS_OPTIONS = ['', 'done', 'failed', 'queued', 'downloading', 'transcribing', 'analyzing'];

function formatDate(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function formatMs(ms) {
  if (!ms) return '—';
  const s = Math.round(ms / 1000);
  return s < 60 ? `${s}s` : `${Math.floor(s / 60)}m ${s % 60}s`;
}

export default function HistoryPage() {
  const [jobs, setJobs] = useState([]);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState('');
  const [category, setCategory] = useState('');
  const [page, setPage] = useState(0);
  const [availableCategories, setAvailableCategories] = useState([]);
  const navigate = useNavigate();
  const pageSize = 20;

  useEffect(() => {
    fetchCollections().then(data => {
      setAvailableCategories(data.collections.map(c => c.category));
    }).catch(console.error);
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => {
      fetchJobs({
        status: status || undefined,
        category: category || undefined,
        search: search || undefined,
        limit: pageSize,
        offset: page * pageSize,
      })
        .then(data => { setJobs(data.jobs); setTotal(data.total); })
        .catch(console.error);
    }, 300); // Debounce search
    return () => clearTimeout(timer);
  }, [search, status, category, page]);

  const totalPages = Math.ceil(total / pageSize);

  return (
    <div className="page">
      <h1 className="page__title"><span className="gradient-text">History</span></h1>
      <p className="page__subtitle">{total} total analyses</p>

      <div className="history-controls">
        <input className="search-input" type="text" placeholder="🔍 Search reels, transcripts, tools..." value={search} onChange={e => { setSearch(e.target.value); setPage(0); }} />
        <select className="filter-select" value={category} onChange={e => { setCategory(e.target.value); setPage(0); }}>
          <option value="">All Categories</option>
          {availableCategories.map(c => (
            <option key={c} value={c}>{getCategoryMeta(c).icon} {c}</option>
          ))}
        </select>
        <select className="filter-select" value={status} onChange={e => { setStatus(e.target.value); setPage(0); }}>
          <option value="">All Status</option>
          {STATUS_OPTIONS.filter(Boolean).map(s => <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>)}
        </select>
      </div>

      {jobs.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state__icon">📂</div>
          <div className="empty-state__title">No results</div>
          <div className="empty-state__text">{search ? 'Try a different search term' : 'No analyses yet — go to the Dashboard to get started!'}</div>
        </div>
      ) : (
        <>
          <table className="history-table">
            <thead>
              <tr><th>Reel ID</th><th>Title</th><th>Category</th><th>Status</th><th>Processing</th><th>Date</th></tr>
            </thead>
            <tbody>
              {jobs.map(j => {
                const catMeta = getCategoryMeta(j.category);
                return (
                  <tr key={j.id} onClick={() => j.status === 'done' ? navigate(`/report/${j.id}`) : null}>
                    <td className="history-table__reel-id">{j.reel_id}</td>
                    <td className="history-table__title">{j.title || '—'}</td>
                    <td>
                      <span className="category-badge" style={{ '--cat-color': catMeta.color }}>
                        {catMeta.icon} {catMeta.label}
                      </span>
                      {j.subcategory && <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: 4 }}>↳ {j.subcategory}</div>}
                    </td>
                    <td><span className={`status-badge status-badge--${j.status}`}><span className={`status-dot status-dot--${j.status}`} />{j.status}</span></td>
                    <td className="history-table__time">{formatMs(j.processing_ms)}</td>
                    <td className="history-table__time">{formatDate(j.created_at)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {totalPages > 1 && (
            <div style={{ display: 'flex', justifyContent: 'center', gap: 8, marginTop: 24 }}>
              <button className="btn btn--ghost btn--sm" disabled={page === 0} onClick={() => setPage(p => p - 1)}>← Prev</button>
              <span style={{ padding: '6px 14px', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Page {page + 1} of {totalPages}</span>
              <button className="btn btn--ghost btn--sm" disabled={page >= totalPages - 1} onClick={() => setPage(p => p + 1)}>Next →</button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
