import { useNavigate } from 'react-router-dom';

const STATUS_LABELS = {
  queued: 'Queued', downloading: 'Downloading', transcribing: 'Transcribing',
  analyzing: 'Analyzing', done: 'Complete', failed: 'Failed',
};

const PLATFORM_ICONS = {
  instagram: '📸',
  youtube: '📹',
  tiktok: '🎵',
};

export default function JobCard({ job }) {
  const navigate = useNavigate();
  const isDone = job.status === 'done';
  const isFailed = job.status === 'failed';
  const fillClass = isFailed ? 'progress-bar__fill--failed' : isDone ? 'progress-bar__fill--done' : '';

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
        <span className={`status-badge status-badge--${job.status}`}>
          <span className={`status-dot status-dot--${job.status}`} />
          {STATUS_LABELS[job.status] || job.status}
        </span>
      </div>
      <div className="progress-bar">
        <div className="progress-bar__track">
          <div className={`progress-bar__fill ${fillClass}`} style={{ width: `${job.progress_pct}%` }} />
        </div>
        <div className="progress-bar__label">
          <span>{job.current_step || (isDone ? 'Analysis complete' : isFailed ? job.error_message : 'Waiting...')}</span>
          <span>{job.progress_pct}%</span>
        </div>
      </div>
    </div>
  );
}
