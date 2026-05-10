import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { getCategoryMeta } from '../pages/CollectionsPage';
import { stopJob } from '../utils/api';

const STATUS_LABELS = {
  queued: 'Queued', downloading: 'Downloading', transcribing: 'Transcribing',
  analyzing: 'Analyzing', done: 'Complete', failed: 'Failed',
  cancelled: 'Cancelled',
};

const PLATFORM_ICONS = {
  instagram: '📸',
  youtube: '📹',
  tiktok: '🎵',
};

export default function JobCard({ job }) {
  const navigate = useNavigate();
  const [error, setError] = useState(null);
  const isDone = job.status === 'done';
  const isFailed = job.status === 'failed';
  const isCancelled = job.status === 'cancelled';
  const isActive = ['downloading', 'transcribing', 'analyzing', 'queued'].includes(job.status);
  
  const fillClass = isFailed ? 'progress-bar__fill--failed' : isCancelled ? 'progress-bar__fill--cancelled' : isDone ? 'progress-bar__fill--done' : '';
  const catMeta = getCategoryMeta(job.category);

  const handleStop = async (e) => {
    e.stopPropagation();
    setError(null);
    console.log(`Stopping job: ${job.id} (${job.reel_id})`);
    try {
      await stopJob(job.id);
    } catch (err) {
      console.error('Failed to stop job:', err);
      setError(err.message);
      // Auto-clear error after 3 seconds
      setTimeout(() => setError(null), 3000);
    }
  };

  return (
    <div className={`job-card glass ${isDone ? 'job-card--clickable' : ''}`} onClick={() => isDone && navigate(`/report/${job.id}`)}>
      <div className="job-card__header">
        <div>
          <div className="job-card__id">
            <span style={{ marginRight: 8 }}>{PLATFORM_ICONS[job.platform] || '🎥'}</span>
            {job.reel_id}
          </div>
          {job.title && <div className="job-card__title">{job.title}</div>}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          {error && <span className="job-card__error">{error}</span>}
          {isActive && (
            <button className="stop-button" onClick={handleStop} title="Stop Analysis">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
              </svg>
              STOP
            </button>
          )}
          {isDone && job.category && (
            <span className="category-badge category-badge--sm" style={{ '--cat-color': catMeta.color }}>
              {catMeta.icon}
            </span>
          )}
          <span className={`status-badge status-badge--${job.status}`}>
            <span className={`status-dot status-dot--${job.status}`} />
            {STATUS_LABELS[job.status] || job.status}
          </span>
        </div>
      </div>
      <div className="progress-bar">
        <div className="progress-bar__track">
          <div className={`progress-bar__fill ${fillClass}`} style={{ width: `${job.progress_pct}%` }} />
        </div>
        <div className="progress-bar__label">
          <span>{job.current_step || (isDone ? 'Analysis complete' : isFailed ? job.error_message : isCancelled ? 'Analysis cancelled' : 'Waiting...')}</span>
          <span>{job.progress_pct}%</span>
        </div>
      </div>
    </div>
  );
}
