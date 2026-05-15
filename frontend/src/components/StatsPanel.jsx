import { useState, useMemo } from 'react';
import { refreshJobMetadata } from '../utils/api';

function fmt(n) {
  if (!n && n !== 0) return '—';
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K';
  return n.toLocaleString();
}

function MetricBadge({ label, value, icon, color, tooltip }) {
  return (
    <div className="sp-metric" title={tooltip}>
      <span className="sp-metric__icon">{icon}</span>
      <div>
        <div className="sp-metric__value" style={{ color }}>{value}</div>
        <div className="sp-metric__label">{label}</div>
      </div>
    </div>
  );
}

function HookRateBar({ rate }) {
  if (rate == null) return null;
  const pct = Math.min(rate * 50, 100); // >2x = 100%
  const color = rate >= 2 ? '#00d4a8' : rate >= 1 ? '#f5a623' : '#e74c3c';
  const label = rate >= 2 ? '🔥 Viral' : rate >= 1 ? '👍 Good' : '📉 Low';
  return (
    <div className="sp-bar-wrap">
      <div className="sp-bar-label">
        <span>🎣 Hook Rate</span>
        <span style={{ color }}>{rate.toFixed(2)}x {label}</span>
      </div>
      <div className="sp-bar-track">
        <div className="sp-bar-fill" style={{ width: `${pct}%`, background: color }} />
      </div>
      <div className="sp-bar-hint">Plays ÷ Views — how many times avg viewer replayed</div>
    </div>
  );
}

function EngagementBar({ rate }) {
  if (rate == null) return null;
  const pct = Math.min(rate * 1000, 100); // 10% = 100%
  const color = rate >= 0.15 ? '#00d4a8' : rate >= 0.05 ? '#f5a623' : '#e74c3c';
  const label = rate >= 0.15 ? '🔥 Viral' : rate >= 0.05 ? '👍 Good' : '📉 Low';
  return (
    <div className="sp-bar-wrap">
      <div className="sp-bar-label">
        <span>📊 Engagement Rate</span>
        <span style={{ color }}>{(rate * 100).toFixed(1)}% {label}</span>
      </div>
      <div className="sp-bar-track">
        <div className="sp-bar-fill" style={{ width: `${pct}%`, background: color }} />
      </div>
      <div className="sp-bar-hint">(Likes + Comments + Shares) ÷ Views</div>
    </div>
  );
}

export default function StatsPanel({ job, onJobUpdate }) {
  const [isRefreshing, setIsRefreshing] = useState(false);

  const {
    id, owner_username, owner_name, published_at, duration_sec,
    view_count = 0, play_count = 0, like_count = 0,
    share_count = 0, comment_count = 0,
    hashtags_json = '[]', comments_json = '[]',
    category, subcategory, url,
  } = job;

  const handleRefresh = async () => {
    if (isRefreshing) return;
    setIsRefreshing(true);
    try {
      const updatedJob = await refreshJobMetadata(id);
      if (onJobUpdate) onJobUpdate(updatedJob);
    } catch (err) {
      alert(err.message || 'Failed to refresh metadata');
    } finally {
      setIsRefreshing(false);
    }
  };

  const hookRate = useMemo(() =>
    view_count > 0 ? play_count / view_count : null,
    [play_count, view_count]
  );

  const engagementRate = useMemo(() =>
    view_count > 0 ? (like_count + comment_count + share_count) / view_count : null,
    [like_count, comment_count, share_count, view_count]
  );

  const hashtags = useMemo(() => {
    try { return JSON.parse(hashtags_json || '[]'); } catch { return []; }
  }, [hashtags_json]);

  const comments = useMemo(() => {
    try { return JSON.parse(comments_json || '[]'); } catch { return []; }
  }, [comments_json]);

  const publishDate = useMemo(() => {
    if (!published_at) return null;
    try {
      return new Date(published_at).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
    } catch { return published_at; }
  }, [published_at]);

  const duration = useMemo(() => {
    if (!duration_sec) return null;
    const s = Math.round(duration_sec);
    return s >= 60 ? `${Math.floor(s / 60)}m ${s % 60}s` : `${s}s`;
  }, [duration_sec]);

  // Show panel if we have basic info or if it's currently refreshing
  const hasAnyData = view_count > 0 || like_count > 0 || owner_username || isRefreshing;

  if (!hasAnyData) {
    return (
      <div className="stats-panel glass" style={{ textAlign: 'center', padding: '30px 20px' }}>
        <p style={{ color: 'var(--text-muted)', marginBottom: 16 }}>No virality data found for this reel.</p>
        <button className="btn btn--primary btn--sm" onClick={handleRefresh} disabled={isRefreshing}>
          {isRefreshing ? '🔄 Fetching Data...' : '🔄 Fetch Latest Metadata'}
        </button>
      </div>
    );
  }

  return (
    <div className="stats-panel glass" style={{ position: 'relative' }}>
      {/* Refresh Button Overlay */}
      <button
        onClick={handleRefresh}
        disabled={isRefreshing}
        style={{
          position: 'absolute', top: 16, right: 16,
          background: 'rgba(102,126,234,0.15)', border: '1px solid rgba(102,126,234,0.3)',
          color: 'var(--accent-purple)', borderRadius: 'var(--radius-xl)',
          padding: '4px 10px', fontSize: '0.75rem', fontWeight: 600,
          cursor: isRefreshing ? 'not-allowed' : 'pointer',
          display: 'flex', alignItems: 'center', gap: '6px',
          transition: 'all 0.2s ease', opacity: isRefreshing ? 0.7 : 1
        }}
        onMouseEnter={(e) => { if (!isRefreshing) e.currentTarget.style.background = 'rgba(102,126,234,0.25)' }}
        onMouseLeave={(e) => { if (!isRefreshing) e.currentTarget.style.background = 'rgba(102,126,234,0.15)' }}
      >
        <span style={{ animation: isRefreshing ? 'spin 1s linear infinite' : 'none', display: 'inline-block' }}>🔄</span>
        {isRefreshing ? 'Refreshing...' : 'Refresh'}
      </button>

      {/* Creator + Meta Header */}
      <div className="sp-header" style={{ paddingRight: 80 }}>
        <div className="sp-creator">
          <div className="sp-creator__avatar">
            {(owner_username || '?')[0].toUpperCase()}
          </div>
          <div>
            {owner_username && (
              <a
                href={`https://www.instagram.com/${owner_username}/`}
                target="_blank" rel="noopener noreferrer"
                className="sp-creator__handle"
              >
                @{owner_username}
              </a>
            )}
            {owner_name && owner_name !== owner_username && (
              <div className="sp-creator__name">{owner_name}</div>
            )}
          </div>
        </div>
        <div className="sp-meta-tags">
          {category && <span className="hub-badge">{category}</span>}
          {subcategory && <span className="hub-badge hub-badge--sub">{subcategory}</span>}
          {duration && <span className="sp-tag">⏱ {duration}</span>}
          {publishDate && <span className="sp-tag">📅 {publishDate}</span>}
          <a href={url} target="_blank" rel="noopener noreferrer" className="sp-tag sp-tag--link">
            🔗 View on Instagram
          </a>
        </div>
      </div>

      {/* Engagement Metrics Row */}
      <div className="sp-metrics-row">
        <MetricBadge icon="👁" label="Views" value={fmt(view_count)} color="var(--text-primary)" tooltip="Total unique views" />
        {play_count > 0 && <MetricBadge icon="🔁" label="Plays" value={fmt(play_count)} color="#a78bfa" tooltip="Total play count (includes replays)" />}
        <MetricBadge icon="❤️" label="Likes" value={fmt(like_count)} color="#f43f5e" tooltip="Total likes" />
        <MetricBadge icon="💬" label="Comments" value={fmt(comment_count)} color="#60a5fa" tooltip="Total comments" />
        <MetricBadge icon="🔗" label="Shares" value={fmt(share_count)} color="#34d399" tooltip="Total shares / reposts" />
      </div>

      {/* Virality Bars */}
      <div className="sp-bars">
        <HookRateBar rate={hookRate} />
        <EngagementBar rate={engagementRate} />
      </div>

      {/* Hashtags */}
      {hashtags.length > 0 && (
        <div className="sp-hashtags">
          <span className="sp-section-label">🏷 Hashtags</span>
          <div className="sp-hashtags__list">
            {hashtags.slice(0, 10).map((tag, i) => (
              <span key={i} className="sp-hashtag">#{tag}</span>
            ))}
            {hashtags.length > 10 && <span className="sp-hashtag sp-hashtag--more">+{hashtags.length - 10}</span>}
          </div>
        </div>
      )}

      {/* Top Comments */}
      {comments.length > 0 && (
        <div className="sp-comments">
          <span className="sp-section-label">💬 Top Comments</span>
          {comments.slice(0, 3).map((c, i) => (
            <div key={i} className="sp-comment">
              <span className="sp-comment__author">@{c.author || 'user'}</span>
              <span className="sp-comment__text">{c.text}</span>
              {c.likes > 0 && <span className="sp-comment__likes">❤️ {c.likes}</span>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
