import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { fetchJob, getVideoUrl, retryJob, deleteJob } from '../utils/api';

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

export default function ReportPage() {
  const { id } = useParams();
  const [job, setJob] = useState(null);
  const [loading, setLoading] = useState(true);

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

  return (
    <div className="page">
      <Link to="/" className="back-link">← Back to Dashboard</Link>

      <div className="report-header">
        <h1 className="page__title">{job.title || job.reel_id}</h1>
        <div className="report-header__actions">
          {job.status === 'done' && (
            <a 
              href={`http://localhost:8000/api/jobs/${job.id}/pdf`} 
              className="btn btn--primary btn--sm" 
              style={{ textDecoration: 'none' }}
              download
            >
              📄 Download PDF
            </a>
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
            <div className="report-sidebar__meta glass">
              <div className="report-sidebar__meta-item"><span className="report-sidebar__meta-label">Platform</span><span className="report-sidebar__meta-value" style={{ textTransform: 'capitalize' }}>{job.platform}</span></div>
              <div className="report-sidebar__meta-item"><span className="report-sidebar__meta-label">Video ID</span><span className="report-sidebar__meta-value">{job.reel_id}</span></div>
              <div className="report-sidebar__meta-item"><span className="report-sidebar__meta-label">Status</span><span className="report-sidebar__meta-value" style={{ color: 'var(--accent-teal)' }}>✅ Complete</span></div>
              <div className="report-sidebar__meta-item"><span className="report-sidebar__meta-label">Processing</span><span className="report-sidebar__meta-value">{formatMs(job.processing_ms)}</span></div>
              <div className="report-sidebar__meta-item"><span className="report-sidebar__meta-label">Analyzed</span><span className="report-sidebar__meta-value">{formatDate(job.completed_at)}</span></div>
              <div className="report-sidebar__meta-item"><span className="report-sidebar__meta-label">URL</span><span className="report-sidebar__meta-value"><a href={job.url} target="_blank" rel="noopener" style={{ color: 'var(--accent-purple)', textDecoration: 'none' }}>Open ↗</a></span></div>
            </div>
          </div>

          <div className="report-content glass">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
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
