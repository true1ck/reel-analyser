import { useState, useEffect, useCallback } from 'react';
import URLInput from '../components/URLInput';
import JobCard from '../components/JobCard';
import { createJobs, createChannelJobs, fetchJobs, fetchStats } from '../utils/api';
import { useWebSocket } from '../hooks/useWebSocket';
import { useNavigate } from 'react-router-dom';

export default function Dashboard() {
  const [jobs, setJobs] = useState([]);
  const [stats, setStats] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const navigate = useNavigate();

  const loadJobs = async () => {
    try {
      const [jobsData, statsData] = await Promise.all([fetchJobs({ limit: 20 }), fetchStats()]);
      setJobs(jobsData.jobs);
      setStats(statsData);
    } catch (e) { console.error(e); }
  };

  useEffect(() => { loadJobs(); }, []);

  const handleWsMessage = useCallback((msg) => {
    setJobs(prev => prev.map(j =>
      j.id === msg.job_id ? { ...j, status: msg.status, progress_pct: msg.progress_pct, current_step: msg.current_step, error_message: msg.error_message } : j
    ));
    if (msg.status === 'done' || msg.status === 'failed') {
      fetchStats().then(setStats).catch(() => {});
    }
  }, []);

  const wsConnected = useWebSocket(handleWsMessage);

  const handleSubmit = async (urls) => {
    setSubmitting(true);
    try {
      const result = await createJobs(urls);
      setJobs(prev => [...result.jobs, ...prev]);
      if (result.invalid_urls?.length > 0) {
        alert(`Invalid URLs skipped:\n${result.invalid_urls.join('\n')}`);
      }
    } catch (e) { alert('Failed to submit: ' + e.message); }
    setSubmitting(false);
  };

  const handleChannelSubmit = async (channelUrl, limit, category) => {
    setSubmitting(true);
    try {
      const result = await createChannelJobs(channelUrl, limit, category);
      if (result.jobs.length === 0) {
        alert('No new videos found (all existing ones were skipped).');
      } else {
        setJobs(prev => [...result.jobs, ...prev]);
      }
    } catch (e) { alert('Failed to submit channel: ' + e.message); }
    setSubmitting(false);
  };


  const activeJobs = jobs.filter(j => !['done', 'failed'].includes(j.status));
  const recentDone = jobs.filter(j => j.status === 'done').slice(0, 5);

  return (
    <div className="page">
      <h1 className="page__title">
        <span className="gradient-text">Dashboard</span>
        {wsConnected && <span style={{ fontSize: '0.5em', color: 'var(--accent-teal)', marginLeft: 12 }}>● Live</span>}
      </h1>
      <p className="page__subtitle">Paste Instagram Reel URLs to analyze them with AI</p>

      {stats && (
        <div className="stats-grid">
          <div className="stat-card glass"><div className="stat-card__value gradient-text">{stats.total_jobs}</div><div className="stat-card__label">Total Analyses</div></div>
          <div className="stat-card glass"><div className="stat-card__value" style={{ color: 'var(--accent-teal)' }}>{stats.completed_jobs}</div><div className="stat-card__label">Completed</div></div>
          <div className="stat-card glass"><div className="stat-card__value" style={{ color: 'var(--warning)' }}>{stats.queued_jobs + stats.processing_jobs}</div><div className="stat-card__label">In Progress</div></div>
          <div className="stat-card glass"><div className="stat-card__value" style={{ color: 'var(--error)' }}>{stats.failed_jobs}</div><div className="stat-card__label">Failed</div></div>
        </div>
      )}

      <URLInput onSubmit={handleSubmit} onChannelSubmit={handleChannelSubmit} disabled={submitting} />

      {activeJobs.length > 0 && (
        <div className="job-queue">
          <h2 className="job-queue__title">⚡ Active Jobs</h2>
          <div className="job-queue__list">
            {activeJobs.map(j => <JobCard key={j.id} job={j} />)}
          </div>
        </div>
      )}

      <div className="job-queue">
        <h2 className="job-queue__title">📄 Recent Reports</h2>
        {recentDone.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state__icon">🎬</div>
            <div className="empty-state__title">No reports yet</div>
            <div className="empty-state__text">Paste some Instagram Reel URLs above to get started!</div>
          </div>
        ) : (
          <div className="job-queue__list">
            {recentDone.map(j => <JobCard key={j.id} job={j} />)}
          </div>
        )}
      </div>
    </div>
  );
}
