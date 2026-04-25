import { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { fetchCollections, fetchJobs } from '../utils/api';

// Helper to generate a consistent color based on string hash
function stringToColor(str) {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    hash = str.charCodeAt(i) + ((hash << 5) - hash);
  }
  const h = hash % 360;
  return `hsl(${h}, 70%, 65%)`;
}

export function getCategoryMeta(categoryName) {
  const cat = categoryName || 'Uncategorized';
  
  // Some predefined mappings for common dynamic categories
  const lowerCat = cat.toLowerCase();
  let icon = '📂';
  if (lowerCat.includes('code') || lowerCat.includes('software') || lowerCat.includes('dev')) icon = '💻';
  else if (lowerCat.includes('ai') || lowerCat.includes('machine learning')) icon = '🤖';
  else if (lowerCat.includes('design') || lowerCat.includes('ui') || lowerCat.includes('ux')) icon = '🎨';
  else if (lowerCat.includes('market') || lowerCat.includes('seo') || lowerCat.includes('growth')) icon = '📢';
  else if (lowerCat.includes('productiv')) icon = '⚡';
  else if (lowerCat.includes('finance') || lowerCat.includes('money') || lowerCat.includes('invest')) icon = '💰';
  
  return {
    icon,
    color: stringToColor(cat),
    label: cat
  };
}

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

export default function CollectionsPage() {
  const [collections, setCollections] = useState([]);
  const [selectedCategory, setSelectedCategory] = useState(null);
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  // Check URL params for pre-selected category
  useEffect(() => {
    const cat = searchParams.get('category');
    if (cat) setSelectedCategory(cat);
  }, [searchParams]);

  useEffect(() => {
    fetchCollections()
      .then(data => setCollections(data.collections))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (selectedCategory) {
      fetchJobs({ category: selectedCategory, status: 'done', limit: 100 })
        .then(data => setJobs(data.jobs))
        .catch(console.error);
    }
  }, [selectedCategory]);

  const handleCategoryClick = (cat) => {
    setSelectedCategory(cat === selectedCategory ? null : cat);
    if (cat !== selectedCategory) {
      setSearchParams({ category: cat });
    } else {
      setSearchParams({});
    }
  };

  if (loading) return <div className="page"><div className="spinner" /></div>;

  return (
    <div className="page">
      <h1 className="page__title"><span className="gradient-text">Collections</span></h1>
      <p className="page__subtitle">Your analyzed reels, organized by category</p>

      <div className="collections-grid">
        {collections.map(col => {
          const key = col.category;
          const count = col.completed || 0;
          const isActive = selectedCategory === key;
          const meta = getCategoryMeta(key);
          return (
            <div
              key={key}
              className={`collection-card glass ${isActive ? 'collection-card--active' : ''} ${count === 0 ? 'collection-card--empty' : ''}`}
              onClick={() => count > 0 && handleCategoryClick(key)}
              style={{ '--cat-color': meta.color }}
            >
              <div className="collection-card__icon">{meta.icon}</div>
              <div className="collection-card__info">
                <div className="collection-card__label">{meta.label}</div>
                <div className="collection-card__desc">{count} analyses in this collection</div>
              </div>
              <div className="collection-card__count" style={{ color: meta.color }}>
                {count}
              </div>
            </div>
          );
        })}
      </div>

      {selectedCategory && (
        <div className="collection-detail">
          <div className="collection-detail__header">
            <h2 className="collection-detail__title">
              <span style={{ marginRight: 8 }}>{getCategoryMeta(selectedCategory).icon}</span>
              {selectedCategory}
            </h2>
            <span className="collection-detail__count">{jobs.length} report{jobs.length !== 1 ? 's' : ''}</span>
          </div>

          {jobs.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state__icon">📂</div>
              <div className="empty-state__title">No reports in this collection</div>
            </div>
          ) : (
            <div className="collection-detail__grid">
              {jobs.map(j => (
                <div key={j.id} className="collection-report-card glass" onClick={() => navigate(`/report/${j.id}`)}>
                  <div className="collection-report-card__header">
                    <span className="collection-report-card__title">{j.title || j.reel_id}</span>
                    <span className="category-badge" style={{ '--cat-color': getCategoryMeta(j.category).color }}>
                      {getCategoryMeta(j.category).icon} {j.category}
                    </span>
                  </div>
                  <div className="collection-report-card__meta">
                    <span>{formatDate(j.completed_at)}</span>
                    <span>{formatMs(j.processing_ms)}</span>
                  </div>
                  {j.subcategory && (
                    <div style={{fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: 8}}>
                      ↳ {j.subcategory}
                    </div>
                  )}
                  {j.analysis_md && (
                    <p className="collection-report-card__preview">
                      {j.analysis_md.replace(/[#*\[\]`]/g, '').substring(0, 150)}...
                    </p>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
