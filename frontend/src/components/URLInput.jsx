import { useState } from 'react';

export default function URLInput({ onSubmit, disabled }) {
  const [text, setText] = useState('');

  const urls = text.split(/[\n,]+/).map(s => s.trim()).filter(Boolean);
  const count = urls.length;

  const handleSubmit = () => {
    if (count === 0 || disabled) return;
    onSubmit(urls);
    setText('');
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && e.metaKey) handleSubmit();
  };

  return (
    <div className="url-input">
      <div className="url-input__card glass">
        <label className="url-input__label">📋 Paste Video URLs (Instagram, YouTube, TikTok)</label>
        <textarea
          className="url-input__textarea"
          placeholder={"Paste one or more URLs here...\nhttps://www.instagram.com/reel/ABC123/\nhttps://www.youtube.com/shorts/XYZ789\nhttps://www.tiktok.com/@user/video/123456"}
          value={text}
          onChange={e => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={disabled}
        />
        <div className="url-input__footer">
          <span className="url-input__count">
            {count > 0 ? <><strong>{count}</strong> video{count !== 1 ? 's' : ''} detected</> : 'Enter URLs above'}
          </span>
          <button className="btn btn--primary" onClick={handleSubmit} disabled={count === 0 || disabled}>
            🚀 Analyze {count > 0 ? `${count} Video${count !== 1 ? 's' : ''}` : ''}
          </button>
        </div>
      </div>
    </div>
  );
}
