import { useState, useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import { fetchTopReels, fetchCreators, fetchTrendingHashtags } from '../utils/api';
import './HubPage.css';

const SEARCH_STEPS = [
  { icon: '🧠', label: 'Embedding your query...' },
  { icon: '🔍', label: 'Scanning vector database...' },
  { icon: '📚', label: 'Retrieving top reports...' },
  { icon: '🌐', label: 'Searching the web...' },
  { icon: '✨', label: 'Synthesising answer...' },
];

const EXAMPLE_QUERIES = [
  'How to grow on Instagram using reels?',
  'Best productivity tools recommended',
  'Entrepreneurship and business tips',
  'Marketing strategies that work in 2024',
  'How to get more views on short videos?',
];

const DISCOVER_TABS = [
  { id: 'likes',      icon: '❤️',  label: 'Most Liked',     sortBy: 'likes' },
  { id: 'hook_rate',  icon: '🎣',  label: 'Best Hook Rate', sortBy: 'hook_rate' },
  { id: 'engagement', icon: '📊',  label: 'Most Engaging',  sortBy: 'engagement' },
  { id: 'shares',     icon: '🔗',  label: 'Most Shared',    sortBy: 'shares' },
  { id: 'creators',   icon: '👤',  label: 'Top Creators',   sortBy: 'creators' },
  { id: 'hashtags',   icon: '#️⃣',  label: 'Trending Tags',  sortBy: 'hashtags' },
];

function fmt(n) {
  if (!n && n !== 0) return '—';
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K';
  return n?.toLocaleString?.() ?? n;
}

export default function HubPage() {
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [stepIndex, setStepIndex] = useState(0);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [focused, setFocused] = useState(false);
  const stepIntervalRef = useRef(null);
  const inputRef = useRef(null);

  // Discover state
  const [activeDiscover, setActiveDiscover] = useState(null);
  const [discoverData, setDiscoverData] = useState(null);
  const [discoverLoading, setDiscoverLoading] = useState(false);

  const loadDiscover = async (tab) => {
    if (activeDiscover === tab.id) {
      setActiveDiscover(null);
      setDiscoverData(null);
      return;
    }
    setActiveDiscover(tab.id);
    setDiscoverData(null);
    setDiscoverLoading(true);
    try {
      let data;
      if (tab.id === 'creators') data = await fetchCreators(15);
      else if (tab.id === 'hashtags') data = await fetchTrendingHashtags(20);
      else data = await fetchTopReels(tab.sortBy, 10);
      setDiscoverData(data);
    } catch (e) {
      setDiscoverData([]);
    } finally {
      setDiscoverLoading(false);
    }
  };

  // Restore state from sessionStorage on component mount
  useEffect(() => {
    const savedQuery = sessionStorage.getItem('hub_last_query');
    const savedResult = sessionStorage.getItem('hub_last_result');
    if (savedQuery) setQuery(savedQuery);
    if (savedResult) {
      try { setResult(JSON.parse(savedResult)); } catch (e) {}
    }
  }, []);

  const startStepAnimation = () => {
    setStepIndex(0);
    stepIntervalRef.current = setInterval(() => {
      setStepIndex(prev => {
        if (prev >= SEARCH_STEPS.length - 1) return prev;
        return prev + 1;
      });
    }, 900);
  };

  const stopStepAnimation = () => {
    if (stepIntervalRef.current) {
      clearInterval(stepIntervalRef.current);
      stepIntervalRef.current = null;
    }
  };

  const handleSearch = async (e) => {
    if (e) e.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    startStepAnimation();
    try {
      const res = await fetch('http://localhost:8000/api/chat/global', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: query, limit: 5 })
      });
      if (!res.ok) throw new Error('Search failed');
      const data = await res.json();
      setResult(data);
      sessionStorage.setItem('hub_last_query', query);
      sessionStorage.setItem('hub_last_result', JSON.stringify(data));
    } catch (err) {
      setError(err.message);
    } finally {
      stopStepAnimation();
      setLoading(false);
    }
  };

  const handleExampleClick = (example) => {
    setQuery(example);
    setTimeout(() => {
      handleSearch(null);
      inputRef.current?.blur();
    }, 50);
  };

  return (
    <div className="hub-page wrapper">
      {/* Header */}
      <header className="hub-header">
        <div className="hub-header__icon">🧠</div>
        <h1 className="hub-header__title">
          <span className="gradient-text">AI Research Hub</span>
        </h1>
        <p className="hub-header__sub">Ask anything across your entire library — powered by semantic search + live web.</p>
      </header>

      {/* ── DISCOVER SECTION ───────────────────────────────────────────────────── */}
      <div className="hub-discover">
        <div className="hub-discover__label">⚡ Discover</div>
        <div className="hub-discover__tabs">
          {DISCOVER_TABS.map(tab => (
            <button
              key={tab.id}
              className={`hub-discover__tab ${activeDiscover === tab.id ? 'hub-discover__tab--active' : ''}`}
              onClick={() => loadDiscover(tab)}
            >
              <span>{tab.icon}</span>
              <span>{tab.label}</span>
            </button>
          ))}
        </div>

        {activeDiscover && (
          <div className="hub-discover__panel glass">
            {discoverLoading && (
              <div className="hub-discover__loading">
                <span className="hub-search-spinner" />
                <span>Loading...</span>
              </div>
            )}

            {!discoverLoading && discoverData && activeDiscover === 'creators' && (
              <>
                <div className="hub-lb-header">
                  <span className="hub-lb-rank">#</span>
                  <span>Creator</span>
                  <span>Reels</span>
                  <span>Total Views</span>
                  <span>Total Likes</span>
                </div>
                {discoverData.map((c, i) => (
                  <div key={c.owner_username} className="hub-lb-row">
                    <span className="hub-lb-rank hub-lb-rank--num">{i + 1}</span>
                    <span className="hub-lb-creator">@{c.owner_username}{c.owner_name ? ` · ${c.owner_name}` : ''}</span>
                    <span className="hub-lb-stat">{c.reel_count}</span>
                    <span className="hub-lb-stat">{fmt(c.total_views)}</span>
                    <span className="hub-lb-stat" style={{color:'#f43f5e'}}>❤️ {fmt(c.total_likes)}</span>
                  </div>
                ))}
              </>
            )}

            {!discoverLoading && discoverData && activeDiscover === 'hashtags' && (
              <div className="hub-hashtags-grid">
                {discoverData.map((h, i) => (
                  <div key={h.tag} className="hub-hashtag-card">
                    <span className="hub-hashtag-rank">#{i+1}</span>
                    <span className="hub-hashtag-tag">#{h.tag}</span>
                    <span className="hub-hashtag-stat">{h.count} reels</span>
                    <span className="hub-hashtag-views">{fmt(h.total_views)} views</span>
                  </div>
                ))}
              </div>
            )}

            {!discoverLoading && discoverData && !['creators','hashtags'].includes(activeDiscover) && (
              <>
                <div className="hub-lb-header">
                  <span className="hub-lb-rank">#</span>
                  <span>Title</span>
                  <span>Creator</span>
                  <span>❤️ Likes</span>
                  <span>👁 Views</span>
                  {activeDiscover === 'hook_rate' && <span>🎣 Hook</span>}
                  {activeDiscover === 'engagement' && <span>📊 Eng%</span>}
                </div>
                {discoverData.map((r, i) => (
                  <Link key={r.id} to={`/report/${r.id}`} className="hub-lb-row hub-lb-row--link">
                    <span className="hub-lb-rank hub-lb-rank--num">{i + 1}</span>
                    <span className="hub-lb-title">{r.title || r.reel_id}</span>
                    <span className="hub-lb-creator">{r.owner_username ? `@${r.owner_username}` : '—'}</span>
                    <span className="hub-lb-stat" style={{color:'#f43f5e'}}>❤️ {fmt(r.like_count)}</span>
                    <span className="hub-lb-stat">👁 {fmt(r.view_count)}</span>
                    {activeDiscover === 'hook_rate' && (
                      <span className="hub-lb-stat" style={{color: r.hook_rate >= 2 ? '#00d4a8' : r.hook_rate >= 1 ? '#f5a623' : '#e74c3c'}}>
                        {r.hook_rate != null ? r.hook_rate.toFixed(2) + 'x' : '—'}
                      </span>
                    )}
                    {activeDiscover === 'engagement' && (
                      <span className="hub-lb-stat" style={{color: r.engagement_rate >= 0.15 ? '#00d4a8' : '#f5a623'}}>
                        {r.engagement_rate != null ? (r.engagement_rate * 100).toFixed(1) + '%' : '—'}
                      </span>
                    )}
                  </Link>
                ))}
              </>
            )}

            {!discoverLoading && discoverData?.length === 0 && (
              <div className="hub-empty">No data yet — analyze some reels first!</div>
            )}
          </div>
        )}
      </div>

      <div className={`hub-search-wrap ${focused ? 'hub-search-wrap--focused' : ''} ${loading ? 'hub-search-wrap--loading' : ''}`}>
        <div className="hub-search-glow" />
        <form className="hub-search-form" onSubmit={handleSearch}>
          <span className="hub-search-icon">
            {loading ? (
              <span className="hub-search-spinner" />
            ) : (
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
              </svg>
            )}
          </span>
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={e => setQuery(e.target.value)}
            onFocus={() => setFocused(true)}
            onBlur={() => setFocused(false)}
            placeholder="Ask your library anything…"
            className="hub-search-input"
            disabled={loading}
            autoComplete="off"
          />
          {query && !loading && (
            <button type="button" className="hub-search-clear" onClick={() => { setQuery(''); setResult(null); setError(null); }}>
              ✕
            </button>
          )}
          <button type="submit" className="hub-search-btn" disabled={loading || !query.trim()}>
            {loading ? 'Searching' : 'Search'}
          </button>
        </form>

        {/* Example queries - shown when empty and not loading */}
        {!query && !loading && !result && (
          <div className="hub-examples">
            <span className="hub-examples__label">Try:</span>
            {EXAMPLE_QUERIES.map((ex, i) => (
              <button key={i} className="hub-example-chip" onClick={() => handleExampleClick(ex)}>
                {ex}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Loading Steps */}
      {loading && (
        <div className="hub-loading">
          <div className="hub-loading__steps">
            {SEARCH_STEPS.map((step, i) => (
              <div key={i} className={`hub-loading__step ${i < stepIndex ? 'done' : i === stepIndex ? 'active' : 'pending'}`}>
                <span className="hub-loading__step-icon">{i < stepIndex ? '✓' : step.icon}</span>
                <span className="hub-loading__step-label">{step.label}</span>
              </div>
            ))}
          </div>
          <div className="hub-loading__bar">
            <div className="hub-loading__bar-fill" style={{ width: `${((stepIndex + 1) / SEARCH_STEPS.length) * 100}%` }} />
          </div>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="hub-error glass">
          <span>⚠️</span>
          <div>
            <strong>Search failed</strong>
            <p>{error}</p>
          </div>
          <button onClick={handleSearch} className="hub-error__retry">Retry</button>
        </div>
      )}

      {/* Results */}
      {result && !loading && (
        <div className="hub-results">
          {/* Answer */}
          <div className="hub-answer glass">
            <div className="hub-answer__header">
              <span className="hub-answer__icon">✨</span>
              <h2>AI Answer</h2>
              <span className="hub-answer__meta">{result.total_reports_searched} chunks searched</span>
            </div>
            <div className="hub-answer__body">
              <ReactMarkdown>{result.answer}</ReactMarkdown>
            </div>
          </div>

          <div className="hub-sources-grid">
            {/* Library Sources */}
            <div className="hub-library">
              <h3 className="hub-section-title">
                <span>📚</span> From Your Library
                <span className="hub-section-count">{result.sources.length} match{result.sources.length !== 1 ? 'es' : ''}</span>
              </h3>
              {result.sources.length === 0 ? (
                <div className="hub-empty">No matching reports found in your library.</div>
              ) : (
                <div className="hub-source-cards">
                  {result.sources.map((src, i) => (
                    <Link
                      to={`/report/${src.job_id}`}
                      className="hub-source-card glass"
                      key={src.job_id}
                      style={{ animationDelay: `${i * 0.08}s` }}
                    >
                      <div className="hub-source-card__rank">#{i + 1}</div>
                      <div className="hub-source-card__content">
                        <div className="hub-source-card__title">{src.title || 'Untitled Video'}</div>
                        <div className="hub-source-card__meta">
                          <span className="hub-badge">{src.category}</span>
                          {src.subcategory && <span className="hub-badge hub-badge--sub">{src.subcategory}</span>}
                          <span className="hub-stat">👁️ {src.view_count?.toLocaleString?.() || 0}</span>
                          <span className="hub-stat">❤️ {src.like_count?.toLocaleString?.() || 0}</span>
                        </div>
                        <p className="hub-source-card__summary">{src.match_summary}</p>
                        <div className="hub-source-card__cta">View Full Report →</div>
                      </div>
                    </Link>
                  ))}
                </div>
              )}
            </div>

            {/* Web Results */}
            {result.web_results?.length > 0 && (
              <div className="hub-web">
                <h3 className="hub-section-title">
                  <span>🌐</span> From the Web
                  <span className="hub-section-count">{result.web_results.length} result{result.web_results.length !== 1 ? 's' : ''}</span>
                </h3>
                <div className="hub-web-cards">
                  {result.web_results.map((r, i) => (
                    <a href={r.url} target="_blank" rel="noopener noreferrer" className="hub-web-card glass" key={i} style={{ animationDelay: `${i * 0.1}s` }}>
                      <div className="hub-web-card__title">{r.title}</div>
                      <p className="hub-web-card__snippet">{r.snippet}</p>
                      <div className="hub-web-card__url">{r.url}</div>
                    </a>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
