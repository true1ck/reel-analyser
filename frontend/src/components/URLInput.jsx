import { useState } from 'react';

export default function URLInput({ onSubmit, onChannelSubmit, disabled }) {
  const [activeTab, setActiveTab] = useState('direct'); // 'direct' or 'channel'
  const [text, setText] = useState('');
  
  // Channel form state
  const [channelUrl, setChannelUrl] = useState('');
  const [limit, setLimit] = useState(1);
  const [category, setCategory] = useState('');

  const urls = text.split(/[\n,]+/).map(s => s.trim()).filter(Boolean);
  const count = urls.length;

  const handleDirectSubmit = () => {
    if (count === 0 || disabled) return;
    onSubmit(urls);
    setText('');
  };

  const handleChannelSubmit = () => {
    if (!channelUrl || disabled) return;
    if (onChannelSubmit) {
      onChannelSubmit(channelUrl.trim(), limit, category.trim() || 'Uncategorized');
      setChannelUrl('');
    }
  };

  const handleKeyDownDirect = (e) => {
    if (e.key === 'Enter' && e.metaKey) handleDirectSubmit();
  };

  const handleKeyDownChannel = (e) => {
    if (e.key === 'Enter' && e.metaKey) handleChannelSubmit();
  };

  return (
    <div className="url-input">
      <div className="url-input__card glass" style={{ padding: '1.5rem' }}>
        <div style={{ display: 'flex', gap: '1rem', marginBottom: '1rem', borderBottom: '1px solid rgba(255,255,255,0.1)', paddingBottom: '0.5rem' }}>
          <button 
            className={`btn ${activeTab === 'direct' ? 'btn--primary' : 'btn--secondary'}`} 
            onClick={() => setActiveTab('direct')}
            style={{ flex: 1, borderRadius: '8px' }}
          >
            📋 Direct Video URLs
          </button>
          <button 
            className={`btn ${activeTab === 'channel' ? 'btn--primary' : 'btn--secondary'}`} 
            onClick={() => setActiveTab('channel')}
            style={{ flex: 1, borderRadius: '8px' }}
          >
            📺 Channel / Profile
          </button>
        </div>

        {activeTab === 'direct' ? (
          <>
            <label className="url-input__label">Paste Video URLs (Instagram, YouTube, TikTok)</label>
            <textarea
              className="url-input__textarea"
              placeholder={"Paste one or more URLs here...\nhttps://www.instagram.com/reel/ABC123/\nhttps://www.youtube.com/shorts/XYZ789\nhttps://www.tiktok.com/@user/video/123456"}
              value={text}
              onChange={e => setText(e.target.value)}
              onKeyDown={handleKeyDownDirect}
              disabled={disabled}
            />
            <div className="url-input__footer">
              <span className="url-input__count">
                {count > 0 ? <><strong>{count}</strong> video{count !== 1 ? 's' : ''} detected</> : 'Enter URLs above'}
              </span>
              <button className="btn btn--primary" onClick={handleDirectSubmit} disabled={count === 0 || disabled}>
                🚀 Analyze {count > 0 ? `${count} Video${count !== 1 ? 's' : ''}` : ''}
              </button>
            </div>
          </>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div>
              <label className="url-input__label">Channel or Profile URL</label>
              <input
                type="text"
                className="input"
                style={{ width: '100%', padding: '0.75rem', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.2)', background: 'rgba(0,0,0,0.2)', color: 'white' }}
                placeholder="https://www.youtube.com/@channel / https://instagram.com/profile"
                value={channelUrl}
                onChange={e => setChannelUrl(e.target.value)}
                onKeyDown={handleKeyDownChannel}
                disabled={disabled}
              />
            </div>
            <div style={{ display: 'flex', gap: '1rem' }}>
              <div style={{ flex: 1 }}>
                <label className="url-input__label">Number of Videos (Limit)</label>
                <input
                  type="number"
                  className="input"
                  style={{ width: '100%', padding: '0.75rem', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.2)', background: 'rgba(0,0,0,0.2)', color: 'white' }}
                  min={1}
                  max={50}
                  value={limit}
                  onChange={e => setLimit(parseInt(e.target.value) || 1)}
                  disabled={disabled}
                />
              </div>
              <div style={{ flex: 2 }}>
                <label className="url-input__label">Category / Folder</label>
                <input
                  type="text"
                  className="input"
                  style={{ width: '100%', padding: '0.75rem', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.2)', background: 'rgba(0,0,0,0.2)', color: 'white' }}
                  placeholder="e.g. Cooking Videos"
                  value={category}
                  onChange={e => setCategory(e.target.value)}
                  disabled={disabled}
                />
              </div>
            </div>
            <div className="url-input__footer" style={{ marginTop: '0.5rem' }}>
              <span className="url-input__count">
                Fetch and analyze top {limit} videos automatically (skips existing)
              </span>
              <button className="btn btn--primary" onClick={handleChannelSubmit} disabled={!channelUrl || disabled}>
                🤖 Fetch & Analyze
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
