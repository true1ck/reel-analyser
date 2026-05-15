import { useState, useEffect, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { fetchJob, getVideoUrl, retryJob, deleteJob, sendChatMessage } from '../utils/api';
import { getCategoryMeta } from './CollectionsPage';
import StatsPanel from '../components/StatsPanel';

function formatMs(ms) {
  if (!ms) return '—';
  const s = Math.round(ms / 1000);
  if (s < 60) return `${s}s`;
  return `${Math.floor(s / 60)}m ${s % 60}s`;
}

function formatDate(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('en-GB').replace(/\//g, '/');
}

/** Extract quick overview fields from the analysis markdown */
function parseQuickOverview(md) {
  if (!md) return {};
  const overview = {};
  const summaryMatch = md.match(/\*\*Summary\*\*:\s*(.+)/i);
  const audienceMatch = md.match(/\*\*Target Audience\*\*:\s*(.+)/i);
  const intentMatch = md.match(/\*\*Content Intent\*\*:\s*(.+)/i);
  const diffMatch = md.match(/\*\*Difficulty\*\*:\s*(.+)/i);
  const timeMatch = md.match(/\*\*Time to Follow\*\*:\s*(.+)/i);
  if (summaryMatch) overview.summary = summaryMatch[1].trim();
  if (audienceMatch) overview.audience = audienceMatch[1].trim();
  if (intentMatch) overview.intent = intentMatch[1].trim();
  if (diffMatch) overview.difficulty = diffMatch[1].trim();
  if (timeMatch) overview.timeEstimate = timeMatch[1].trim();
  return overview;
}

export default function ReportPage() {
  const { id } = useParams();
  const [job, setJob] = useState(null);
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState(false);
  const [transcriptTab, setTranscriptTab] = useState('report');

  // Chat state
  const AVAILABLE_SKILLS = [
    { cmd: '\\reanalyse', desc: 'Re-watch video with Vision AI' },
    { cmd: '\\summarize', desc: 'Generate a short summary' },
    { cmd: '\\extract_tools', desc: 'List all tools mentioned' },
  ];

  const [chatMessages, setChatMessages] = useState([
    { role: 'ai', text: 'Hi! Ask me anything about this video, or type `\\` to see available commands.' }
  ]);
  const [chatInput, setChatInput] = useState('');
  const [isChatting, setIsChatting] = useState(false);
  const [showSkills, setShowSkills] = useState(false);
  const [skillFilter, setSkillFilter] = useState('');
  const [activeSkillIdx, setActiveSkillIdx] = useState(0);
  const messagesEndRef = useRef(null);

  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [chatMessages]);
  useEffect(() => { fetchJob(id).then(setJob).catch(console.error).finally(() => setLoading(false)); }, [id]);

  if (loading) return <div className="rp-loading"><div className="spinner" /></div>;
  if (!job) return <div className="rp-loading"><p>Job not found.</p></div>;

  const handleRetry = async () => { try { const u = await retryJob(id); setJob(u); } catch (e) { alert(e.message); } };
  const handleDelete = async () => { if (!confirm('Delete this analysis?')) return; try { await deleteJob(id); window.location.href = '/'; } catch (e) { alert(e.message); } };
  const handleCopyReport = () => { navigator.clipboard.writeText(job.analysis_md || ''); setCopied(true); setTimeout(() => setCopied(false), 2000); };

  const filteredSkills = AVAILABLE_SKILLS.filter(s => s.cmd.startsWith(skillFilter));

  const handleChatChange = (e) => {
    const val = e.target.value;
    setChatInput(val);
    const lastWord = val.split(' ').at(-1);
    if (lastWord.startsWith('\\')) { setShowSkills(true); setSkillFilter(lastWord); setActiveSkillIdx(0); }
    else setShowSkills(false);
  };

  const insertSkill = (cmd) => {
    const words = chatInput.split(' ');
    words[words.length - 1] = cmd + ' ';
    setChatInput(words.join(' '));
    setShowSkills(false);
  };

  const handleChatKeyDown = (e) => {
    if (!showSkills || filteredSkills.length === 0) return;
    if (e.key === 'ArrowDown') { e.preventDefault(); setActiveSkillIdx(p => (p + 1) % filteredSkills.length); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setActiveSkillIdx(p => (p - 1 + filteredSkills.length) % filteredSkills.length); }
    else if (e.key === 'Tab' || e.key === 'Enter') { e.preventDefault(); insertSkill(filteredSkills[activeSkillIdx].cmd); }
    else if (e.key === 'Escape') setShowSkills(false);
  };

  const handleChatSubmit = async (e) => {
    e.preventDefault();
    if (!chatInput.trim() || isChatting) return;
    const userMsg = chatInput.trim();
    setChatMessages(prev => [...prev, { role: 'user', text: userMsg }]);
    setChatInput('');
    setIsChatting(true);
    try {
      const response = await sendChatMessage(job.id, userMsg);
      setChatMessages(prev => [...prev, { role: 'ai', text: response.reply }]);
    } catch (err) {
      setChatMessages(prev => [...prev, { role: 'system', text: `**Error:** ${err.message}` }]);
    } finally { setIsChatting(false); }
  };

  const overview = parseQuickOverview(job.analysis_md);
  const catMeta = getCategoryMeta(job.category);

  // Parse hashtags from job
  let hashtags = [];
  try { hashtags = JSON.parse(job.hashtags_json || '[]'); } catch {}

  return (
    <div className="rp-page">
      {/* ── Top Header ── */}
      <div className="rp-header">
        <div className="rp-header__left">
          <div className="rp-header__title-row">
            <Link to="/" className="rp-back-link">←</Link>
            <h1 className="rp-title">{job.title || job.reel_id}</h1>
            {job.status === 'done' && <span className="rp-verified">✓</span>}
          </div>
          <div className="rp-hashtags">
            {hashtags.slice(0, 5).map((tag, i) => (
              <span key={i} className="rp-hashtag">#{tag}</span>
            ))}
          </div>
        </div>
        <div className="rp-header__actions">
          {job.status === 'done' && (
            <>
              <button className="rp-btn rp-btn--ghost" onClick={handleCopyReport}>
                <span>📋</span> {copied ? 'Copied!' : 'Copy Report'}
              </button>
              <a href={`http://localhost:8000/api/jobs/${job.id}/pdf`} className="rp-btn rp-btn--ghost" download>
                <span>📄</span> Download PDF
              </a>
            </>
          )}
          {job.status === 'failed' && <button className="rp-btn rp-btn--ghost" onClick={handleRetry}>🔄 Retry</button>}
          <button className="rp-btn rp-btn--danger" onClick={handleDelete}>🗑 Delete</button>
        </div>
      </div>

      {/* ── Failed Banner ── */}
      {job.status === 'failed' && (
        <div className="rp-error-banner">
          <strong>❌ Analysis Failed</strong>
          <p>{job.error_message}</p>
        </div>
      )}

      {/* ── Main Bento Grid ── */}
      {job.status === 'done' && (
        <div className="rp-grid">

          {/* VIDEO — top left */}
          <div className="rp-card rp-card--video">
            <video controls preload="metadata" src={getVideoUrl(job.id)} />
          </div>

          {/* QUICK OVERVIEW — top middle */}
          <div className="rp-card rp-card--overview">
            <h2 className="rp-card__title">Quick Overview</h2>
            <div className="rp-overview-list">
              {overview.summary && (
                <div className="rp-overview-item">
                  <span className="rp-overview-item__icon">📄</span>
                  <div>
                    <div className="rp-overview-item__label">Summary</div>
                    <div className="rp-overview-item__text">{overview.summary}</div>
                  </div>
                </div>
              )}
              {overview.audience && (
                <div className="rp-overview-item">
                  <span className="rp-overview-item__icon">👥</span>
                  <div>
                    <div className="rp-overview-item__label">Target Audience</div>
                    <div className="rp-overview-item__text">{overview.audience}</div>
                  </div>
                </div>
              )}
              {overview.intent && (
                <div className="rp-overview-item">
                  <span className="rp-overview-item__icon">🎯</span>
                  <div>
                    <div className="rp-overview-item__label">Content Intent</div>
                    <div className="rp-overview-item__text">{overview.intent}</div>
                  </div>
                </div>
              )}
              {overview.difficulty && (
                <div className="rp-overview-item">
                  <span className="rp-overview-item__icon">⚡</span>
                  <div>
                    <div className="rp-overview-item__label">Difficulty</div>
                    <div className="rp-overview-item__text">{overview.difficulty}</div>
                  </div>
                </div>
              )}
              {overview.timeEstimate && (
                <div className="rp-overview-item">
                  <span className="rp-overview-item__icon">⏱️</span>
                  <div>
                    <div className="rp-overview-item__label">Time to Follow</div>
                    <div className="rp-overview-item__text">{overview.timeEstimate}</div>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* CHAT — right, spans all rows */}
          <div className="rp-card rp-card--chat">
            <div className="rp-chat__header">
              <h2 className="rp-card__title">Chat with Video</h2>
              <Link to="/" className="rp-chat__close">✕</Link>
            </div>
            <div className="rp-chat__tab-bar">
              <span className="rp-chat__tab rp-chat__tab--active">Chat History</span>
            </div>
            <div className="rp-chat__messages">
              {chatMessages.map((msg, idx) => (
                <div key={idx} className={`rp-bubble rp-bubble--${msg.role}`}>
                  {msg.role === 'ai' && <span className="rp-bubble__avatar">🤖</span>}
                  <div className="rp-bubble__text">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.text}</ReactMarkdown>
                  </div>
                </div>
              ))}
              {isChatting && (
                <div className="rp-bubble rp-bubble--ai">
                  <span className="rp-bubble__avatar">🤖</span>
                  <div className="rp-bubble__text chat-bubble--loading">
                    <span className="dot"/><span className="dot"/><span className="dot"/>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
            <div className="rp-chat__suggestions">
              <button className="rp-suggestion" onClick={() => setChatInput('What are the key points?')}>What are the key points?</button>
              <button className="rp-suggestion" onClick={() => setChatInput('Who is the target audience?')}>Who is the target audience?</button>
              <button className="rp-suggestion" onClick={() => setChatInput('What makes this video viral?')}>What makes this video viral?</button>
            </div>
            <form className="rp-chat__form" onSubmit={handleChatSubmit}>
              <div className="rp-chat__input-wrap">
                {showSkills && filteredSkills.length > 0 && (
                  <div className="skills-dropdown">
                    {filteredSkills.map((skill, idx) => (
                      <div key={skill.cmd}
                        className={`skills-dropdown__item ${idx === activeSkillIdx ? 'skills-dropdown__item--active' : ''}`}
                        onClick={() => insertSkill(skill.cmd)}
                        onMouseEnter={() => setActiveSkillIdx(idx)}
                      >
                        <span className="skills-dropdown__cmd">{skill.cmd}</span>
                        <span className="skills-dropdown__desc">{skill.desc}</span>
                      </div>
                    ))}
                  </div>
                )}
                <input
                  type="text"
                  className="rp-chat__input"
                  placeholder="Type your message..."
                  value={chatInput}
                  onChange={handleChatChange}
                  onKeyDown={handleChatKeyDown}
                  disabled={isChatting}
                  autoComplete="off"
                />
              </div>
              <button type="submit" className="rp-chat__send" disabled={isChatting || !chatInput.trim()}>➤</button>
            </form>
          </div>

          {/* DETAILS & METRICS — middle left */}
          <div className="rp-card rp-card--metrics">
            <h2 className="rp-card__title">Details & Metrics</h2>
            <div className="rp-metrics-list">
              <div className="rp-metric-row">
                <span className="rp-metric-row__label">Category</span>
                <span className="rp-metric-row__value">
                  <span className="category-badge" style={{ '--cat-color': catMeta.color }}>{catMeta.icon} {catMeta.label}</span>
                </span>
              </div>
              <div className="rp-metric-row">
                <span className="rp-metric-row__label">Platform</span>
                <span className="rp-metric-row__value" style={{ textTransform: 'capitalize' }}>{job.platform}</span>
              </div>
              <div className="rp-metric-row">
                <span className="rp-metric-row__label">Status</span>
                <span className="rp-status-pill">Complete</span>
              </div>
              <div className="rp-metric-row">
                <span className="rp-metric-row__label">Time Spent</span>
                <span className="rp-metric-row__value">{formatMs(job.processing_ms)}</span>
              </div>
              <div className="rp-metric-row">
                <span className="rp-metric-row__label">Analyzed</span>
                <span className="rp-metric-row__value">{formatDate(job.completed_at)}</span>
              </div>
              <div className="rp-metric-row">
                <span className="rp-metric-row__label">Open Original Link</span>
                <a href={job.url} target="_blank" rel="noopener" className="rp-metric-row__link">↗</a>
              </div>
            </div>
            {/* Virality stats tucked in below */}
            <StatsPanel job={job} onJobUpdate={setJob} />
          </div>

          {/* TRANSCRIPT & ANALYSIS — middle center */}
          <div className="rp-card rp-card--transcript">
            <div className="rp-tabs">
              <button className={`rp-tab ${transcriptTab === 'report' ? 'rp-tab--active' : ''}`} onClick={() => setTranscriptTab('report')}>Full Analysis</button>
              <button className={`rp-tab ${transcriptTab === 'transcript' ? 'rp-tab--active' : ''}`} onClick={() => setTranscriptTab('transcript')}>Transcript</button>
            </div>
            <div className="rp-transcript-body">
              {transcriptTab === 'report' ? (
                <div className="report-content">
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    components={{
                      input: ({ type, checked }) => {
                        if (type === 'checkbox') return <input type="checkbox" defaultChecked={checked} className="report-checkbox" />;
                        return <input type={type} />;
                      }
                    }}
                  >
                    {job.analysis_md || '*No analysis content yet.*'}
                  </ReactMarkdown>
                </div>
              ) : (
                <p className="rp-transcript-text">
                  {job.transcript || 'No transcript available.'}
                </p>
              )}
            </div>
          </div>

          {/* CREATOR — bottom left */}
          <div className="rp-card rp-card--creator">
            <h2 className="rp-card__title">Creator</h2>
            <div className="rp-creator">
              <div className="rp-creator__avatar">
                {(job.owner_username || '?')[0].toUpperCase()}
              </div>
              <div className="rp-creator__info">
                <a href={job.url} target="_blank" rel="noopener" className="rp-creator__name">
                  {job.owner_name || job.owner_username || 'Unknown'}
                </a>
                <span className="rp-creator__handle">@{job.owner_username || 'unknown'}</span>
              </div>
            </div>
          </div>

          {/* TOOLS & RESOURCES — bottom center */}
          <div className="rp-card rp-card--tools">
            <h2 className="rp-card__title">Tools & Resources</h2>
            <div className="rp-tools-grid">
              <a href={`http://localhost:8000/api/jobs/${job.id}/pdf`} className="rp-tool-btn" download>
                <span className="rp-tool-btn__icon">📄</span>
                <span className="rp-tool-btn__label">Download PDF</span>
                <span className="rp-tool-btn__arrow">»</span>
              </a>
              <button className="rp-tool-btn" onClick={handleCopyReport}>
                <span className="rp-tool-btn__icon">📋</span>
                <span className="rp-tool-btn__label">Copy Report</span>
                <span className="rp-tool-btn__arrow">»</span>
              </button>
            </div>
          </div>

        </div>
      )}
    </div>
  );
}
