import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { fetchJob, getVideoUrl, retryJob, deleteJob } from '../utils/api';
import { getCategoryMeta } from './CollectionsPage';

function formatMs(ms) {
  if (!ms) return '—';
  const s = Math.round(ms / 1000);
  if (s < 60) return `${s}s`;
  return `${Math.floor(s / 60)}m ${s % 60}s`;
}

function formatDate(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleString();
}

/** Extract quick overview fields from the analysis markdown */
function parseQuickOverview(md) {
  if (!md) return null;
  const overview = {};
  const diffMatch = md.match(/\*\*Difficulty\*\*:\s*(.+)/i);
  const timeMatch = md.match(/\*\*Time to Follow\*\*:\s*(.+)/i);
  const summaryMatch = md.match(/\*\*Summary\*\*:\s*(.+)/i);
  const catMatch = md.match(/###\s*📂\s*CATEGORY:\s*(\S+)/i);
  if (diffMatch) overview.difficulty = diffMatch[1].trim();
  if (timeMatch) overview.timeEstimate = timeMatch[1].trim();
  if (summaryMatch) overview.summary = summaryMatch[1].trim();
  if (catMatch) overview.category = catMatch[1].trim().toLowerCase();
  return Object.keys(overview).length > 0 ? overview : null;
}

/** Custom renderer for checklist items */
function ChecklistRenderer({ children }) {
  // Convert markdown checkboxes to interactive ones
  const text = String(children);
  if (text.includes('[ ]') || text.includes('[x]')) {
    const isChecked = text.includes('[x]');
    const label = text.replace(/\[[ x]\]\s*/, '');
    return (
      <label className="report-checklist-item">
        <input type="checkbox" defaultChecked={isChecked} />
        <span>{label}</span>
      </label>
    );
  }
  return <li>{children}</li>;
}

export default function ReportPage() {
  const { id } = useParams();
  const [job, setJob] = useState(null);
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    fetchJob(id).then(setJob).catch(console.error).finally(() => setLoading(false));
  }, [id]);

  if (loading) return <div className="page"><div className="spinner" /></div>;
  if (!job) return <div className="page"><p>Job not found.</p></div>;

  const handleRetry = async () => {
    try { const updated = await retryJob(id); setJob(updated); } catch (e) { alert(e.message); }
  };
  const handleDelete = async () => {
    if (!confirm('Delete this analysis?')) return;
    try { await deleteJob(id); window.location.href = '/'; } catch (e) { alert(e.message); }
  };
  const handleCopyReport = () => {
    navigator.clipboard.writeText(job.analysis_md || '');
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const overview = parseQuickOverview(job.analysis_md);
  const catMeta = getCategoryMeta(job.category);

  return (
    <div className="page">
      <Link to="/" className="back-link">← Back to Dashboard</Link>

      <div className="report-header">
        <h1 className="page__title">{job.title || job.reel_id}</h1>
        <div className="report-header__actions">
          {job.status === 'done' && (
            <>
              <button className="btn btn--ghost btn--sm" onClick={handleCopyReport}>
                {copied ? '✅ Copied!' : '📋 Copy Report'}
              </button>
              <a 
                href={`http://localhost:8000/api/jobs/${job.id}/pdf`} 
                className="btn btn--primary btn--sm" 
                style={{ textDecoration: 'none' }}
                download
              >
                📄 Download PDF
              </a>
            </>
          )}
          {job.status === 'failed' && <button className="btn btn--primary btn--sm" onClick={handleRetry}>🔄 Retry</button>}
          <button className="btn btn--danger btn--sm" onClick={handleDelete}>🗑 Delete</button>
        </div>
      </div>

      {job.status === 'failed' && (
        <div className="glass" style={{ padding: 20, marginBottom: 24, borderColor: 'var(--error)' }}>
          <strong style={{ color: 'var(--error)' }}>❌ Analysis Failed</strong>
          <p style={{ color: 'var(--text-secondary)', marginTop: 8 }}>{job.error_message}</p>
        </div>
      )}

      {job.status === 'done' && (
        <div className="report-page">
          <div className="report-sidebar">
            <div className="report-sidebar__video">
              <video controls preload="metadata" src={getVideoUrl(job.id)} />
            </div>

            {/* Quick Overview Card */}
            {overview && (
              <div className="report-overview glass">
                {overview.summary && (
                  <p className="report-overview__summary">{overview.summary}</p>
                )}
                <div className="report-overview__badges">
                  {overview.difficulty && (
                    <span className={`difficulty-badge difficulty-badge--${overview.difficulty.toLowerCase()}`}>
                      {overview.difficulty}
                    </span>
                  )}
                  {overview.timeEstimate && (
                    <span className="time-badge">⏱️ {overview.timeEstimate}</span>
                  )}
                </div>
              </div>
            )}

            <div className="report-sidebar__meta glass">
              <div className="report-sidebar__meta-item">
                <span className="report-sidebar__meta-label">Category</span>
                <span className="category-badge" style={{ '--cat-color': catMeta.color }}>
                  {catMeta.icon} {catMeta.label}
                </span>
              </div>
              {job.subcategory && (
                <div className="report-sidebar__meta-item">
                  <span className="report-sidebar__meta-label">Subcategory</span>
                  <span className="report-sidebar__meta-value">{job.subcategory}</span>
                </div>
              )}
              <div className="report-sidebar__meta-item">
                <span className="report-sidebar__meta-label">Platform</span>
                <span className="report-sidebar__meta-value" style={{ textTransform: 'capitalize' }}>{job.platform}</span>
              </div>
              <div className="report-sidebar__meta-item">
                <span className="report-sidebar__meta-label">Video ID</span>
                <span className="report-sidebar__meta-value">{job.reel_id}</span>
              </div>
              <div className="report-sidebar__meta-item">
                <span className="report-sidebar__meta-label">Status</span>
                <span className="report-sidebar__meta-value" style={{ color: 'var(--accent-teal)' }}>✅ Complete</span>
              </div>
              <div className="report-sidebar__meta-item">
                <span className="report-sidebar__meta-label">Processing</span>
                <span className="report-sidebar__meta-value">{formatMs(job.processing_ms)}</span>
              </div>
              <div className="report-sidebar__meta-item">
                <span className="report-sidebar__meta-label">Analyzed</span>
                <span className="report-sidebar__meta-value">{formatDate(job.completed_at)}</span>
              </div>
              <div className="report-sidebar__meta-item">
                <span className="report-sidebar__meta-label">URL</span>
                <span className="report-sidebar__meta-value"><a href={job.url} target="_blank" rel="noopener" style={{ color: 'var(--accent-purple)', textDecoration: 'none' }}>Open ↗</a></span>
              </div>
            </div>
          </div>

          <div className="report-content glass">
            <ReactMarkdown 
              remarkPlugins={[remarkGfm]}
              components={{
                // Make checkboxes interactive
                input: ({ type, checked, ...props }) => {
                  if (type === 'checkbox') {
                    return <input type="checkbox" defaultChecked={checked} className="report-checkbox" />;
                  }
                  return <input type={type} {...props} />;
                }
              }}
            >
              {job.analysis_md || '*No analysis content*'}
            </ReactMarkdown>

            {job.transcript && (
              <>
                <h3>📝 Full Transcript</h3>
                <p style={{ fontStyle: 'italic' }}>{job.transcript}</p>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
