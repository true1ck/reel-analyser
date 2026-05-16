import { useState, useEffect, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { fetchJob, getVideoUrl, retryJob, deleteJob, sendChatMessage } from '../utils/api';
import { getCategoryMeta } from './CollectionsPage';

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

function fmt(n) {
  if (!n && n !== 0) return '—';
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K';
  return n.toLocaleString();
}

function parseQuickOverview(md) {
  if (!md) return {};
  const overview = {};
  const extract = (key) => {
    const regex = new RegExp(`(?:\\*\\*|-)?\\s*${key}\\s*(?:\\*\\*)?:?\\s*(.+)`, 'i');
    const match = md.match(regex);
    return match ? match[1].trim() : null;
  };
  overview.summary = extract('Summary');
  overview.audience = extract('Target Audience');
  overview.intent = extract('Content Intent');
  overview.difficulty = extract('Difficulty');
  return overview;
}

function partitionAnalysis(md) {
  if (!md) return { report: '', extras: '' };
  
  // Split by any line that looks like a header (starts with emoji or ## or **)
  // This regex finds the position of headers to split the text into sections
  const headerRegex = /\n(?=(?:[^\n\w]*[📊🗣️🌐🛠️🔗💡🎯📋📝📂🏆]|\s*##|\s*\*\*))/g;
  const sections = md.split(headerRegex);
  
  let reportSections = [];
  let extraSections = [];
  
  const extraKeywords = ['original transcript', 'english translation'];
  
  sections.forEach(section => {
    const trimmed = section.trim();
    if (!trimmed) return;
    
    // Check the first line of the section for keywords
    const firstLine = trimmed.split('\n')[0].toLowerCase();
    const isExtra = extraKeywords.some(kw => firstLine.includes(kw));
    
    if (isExtra) {
      extraSections.push(trimmed);
    } else {
      reportSections.push(trimmed);
    }
  });
  
  return { 
    report: reportSections.join('\n\n').trim(), 
    extras: extraSections.join('\n\n').trim() 
  };
}

export default function ReportPage() {
  const { id } = useParams();
  const [job, setJob] = useState(null);
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState(false);
  const [activeTab, setActiveTab] = useState('report');

  const [chatMessages, setChatMessages] = useState([
    { role: 'ai', text: 'Hi! I am your AI assistant for this video. How can I help?' }
  ]);
  const [chatInput, setChatInput] = useState('');
  const [isChatting, setIsChatting] = useState(false);
  const messagesEndRef = useRef(null);

  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [chatMessages]);
  useEffect(() => { 
    fetchJob(id).then(setJob).catch(console.error).finally(() => setLoading(false)); 
  }, [id]);

  const [showSkills, setShowSkills] = useState(false);
  const [skillFilter, setSkillFilter] = useState('');
  const [activeSkillIdx, setActiveSkillIdx] = useState(0);

  const AVAILABLE_SKILLS = [
    { cmd: '\\reanalyse', desc: 'Re-analyze video with Vision AI' },
    { cmd: '\\summarize', desc: 'Generate a short summary' },
    { cmd: '\\extract_tools', desc: 'List all tools mentioned' },
    { cmd: '\\virality_check', desc: 'Deep dive into virality' },
  ];

  if (loading) return <div className="rp-v3-loader">Loading...</div>;
  if (!job) return <div className="rp-v3-loader">Report not found.</div>;

  const overview = parseQuickOverview(job.analysis_md);
  const partitioned = partitionAnalysis(job.analysis_md);
  const catMeta = getCategoryMeta(job.category);


  const filteredSkills = AVAILABLE_SKILLS.filter(s => s.cmd.startsWith(skillFilter));

  const handleChatChange = (e) => {
    const val = e.target.value;
    setChatInput(val);
    const lastWord = val.split(' ').at(-1);
    if (lastWord.startsWith('\\')) {
      setShowSkills(true);
      setSkillFilter(lastWord);
      setActiveSkillIdx(0);
    } else {
      setShowSkills(false);
    }
  };

  const insertSkill = (cmd) => {
    const words = chatInput.split(' ');
    words[words.length - 1] = cmd + ' ';
    setChatInput(words.join(' '));
    setShowSkills(false);
  };

  const handleChatKeyDown = (e) => {
    if (!showSkills || filteredSkills.length === 0) return;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActiveSkillIdx(p => (p + 1) % filteredSkills.length);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActiveSkillIdx(p => (p - 1 + filteredSkills.length) % filteredSkills.length);
    } else if (e.key === 'Tab' || e.key === 'Enter') {
      e.preventDefault();
      insertSkill(filteredSkills[activeSkillIdx].cmd);
    } else if (e.key === 'Escape') {
      setShowSkills(false);
    }
  };

  const handleChatSubmit = async (e) => {
    e.preventDefault();
    if (!chatInput.trim() || isChatting) return;
    const msg = chatInput.trim();
    
    // Add user message
    setChatMessages(prev => [...prev, { role: 'user', text: msg }]);
    setChatInput('');
    setShowSkills(false);
    setIsChatting(true);

    // Immediate feedback for long-running commands
    if (msg.startsWith('\\reanalyse')) {
      setChatMessages(prev => [...prev, { role: 'system', text: 'Initiating deep re-analysis with Vision AI... this may take 1-2 minutes.' }]);
    } else if (msg.startsWith('\\virality_check')) {
      setChatMessages(prev => [...prev, { role: 'system', text: 'Calculating virality metrics and market positioning...' }]);
    }

    try {
      const res = await sendChatMessage(job.id, msg);
      setChatMessages(prev => [...prev, { role: 'ai', text: res.reply }]);
    } catch (err) {
      console.error('Chat error:', err);
      const errMsg = err.message.includes('Failed to fetch') 
        ? 'Backend unreachable. Please ensure the server is running on port 8000.'
        : `Error: ${err.message}`;
      setChatMessages(prev => [...prev, { role: 'ai', text: errMsg }]);
    } finally { setIsChatting(false); }
  };

  return (
    <div className="rp-v3-wrapper">
      {/* ── TOP HEADER ── */}
      <header className="rp-v3-header">
        <div className="rp-v3-header-left">
          <Link to="/" className="rp-v3-back">←</Link>
          <div className="rp-v3-title-stack">
            <h1 className="rp-v3-title">{job.title || 'Video Analysis'}</h1>
            <div className="rp-v3-meta">
              <span>{job.platform}</span>
              <span className="dot">•</span>
              <span>{formatDate(job.completed_at)}</span>
              <span className="dot">•</span>
              <span className={`rp-v3-status ${job.status !== 'done' ? 'rp-v3-status--processing' : ''}`}>
                ● {job.status === 'done' ? 'Complete' : job.status.toUpperCase()}
              </span>
            </div>
          </div>
        </div>
        <div className="rp-v3-header-actions">
          <button className="rp-v3-btn" onClick={() => {navigator.clipboard.writeText(job.analysis_md); setCopied(true); setTimeout(()=>setCopied(false), 2000)}}>{copied ? 'Copied!' : 'Copy Analysis'}</button>
          <a href={`http://localhost:8000/api/jobs/${job.id}/pdf`} className="rp-v3-btn" download>Download PDF</a>
          <button className="rp-v3-btn rp-v3-btn--danger" onClick={() => confirm('Delete?') && deleteJob(job.id).then(()=>window.location.href='/')}>Delete</button>
        </div>
      </header>

      {/* ── THREE COLUMN CONTENT ── */}
      <div className="rp-v3-content">
        
        {/* COLUMN 1: VIDEO & STATS */}
        <div className="rp-v3-col rp-v3-col--left">
          <div className="rp-v3-card">
            <div className="rp-v3-video">
              <video controls src={getVideoUrl(job.id)} />
            </div>
          </div>
          
          <div className="rp-v3-card">
            <div className="rp-v3-card-header">Video Information</div>
            <div className="rp-v3-info-list">
              <div className="rp-v3-info-item"><span>Category</span><strong>{catMeta.label}</strong></div>
              <div className="rp-v3-info-item"><span>Published</span><strong>{job.published_at ? new Date(job.published_at).toLocaleDateString() : 'Unknown'}</strong></div>
              <div className="rp-v3-info-item"><span>Duration</span><strong>{formatMs(job.duration_sec * 1000)}</strong></div>
              <div className="rp-v3-info-item"><span>Reel ID</span><code>{job.reel_id}</code></div>
              <div className="rp-v3-info-item"><span>Source</span><a href={job.url} target="_blank" rel="noreferrer">Instagram ↗</a></div>
            </div>
          </div>

          <div className="rp-v3-card">
            <div className="rp-v3-card-header">Creator</div>
            <div className="rp-v3-creator">
              <div className="rp-v3-avatar">{(job.owner_username || '?')[0].toUpperCase()}</div>
              <div>
                <div className="rp-v3-name">{job.owner_name || 'Creator'}</div>
                <div className="rp-v3-handle">@{job.owner_username}</div>
              </div>
            </div>
          </div>
        </div>

        {/* COLUMN 2: ANALYSIS */}
        <div className="rp-v3-col rp-v3-col--main">
          <div className="rp-v3-overview--bento">
            <div className="rp-v3-ov-item--bento"><span>Audience</span><p>{overview.audience || 'Target audience info'}</p></div>
            <div className="rp-v3-ov-item--bento"><span>Intent</span><p>{overview.intent || 'Content intent info'}</p></div>
            <div className="rp-v3-ov-item--bento rp-v3-ov-item--full"><span>Summary</span><p>{overview.summary || 'Summary extracting...'}</p></div>
          </div>

          <div className="rp-v3-card rp-v3-card--flex">
            <div className="rp-v3-tabs">
              <button className={activeTab === 'report' ? 'active' : ''} onClick={() => setActiveTab('report')}>Analysis</button>
              <button className={activeTab === 'transcript' ? 'active' : ''} onClick={() => setActiveTab('transcript')}>Transcript</button>
              <button className={activeTab === 'virality' ? 'active' : ''} onClick={() => setActiveTab('virality')}>Virality</button>
            </div>
            <div className="rp-v3-tab-body">
              {activeTab === 'report' && <div className="rp-v3-md"><ReactMarkdown remarkPlugins={[remarkGfm]}>{partitioned.report}</ReactMarkdown></div>}
              {activeTab === 'transcript' && (
                <div className="rp-v3-text">
                  {job.transcript && <div>{job.transcript}</div>}
                  {partitioned.extras && (
                    <div className="rp-v3-md" style={{ marginTop: job.transcript ? '24px' : '0', borderTop: job.transcript ? '1px solid var(--border-color)' : 'none', paddingTop: job.transcript ? '24px' : '0' }}>
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>{partitioned.extras}</ReactMarkdown>
                    </div>
                  )}
                  {!job.transcript && !partitioned.extras && 'No transcript.'}
                </div>
              )}
              {activeTab === 'virality' && (
                <div className="rp-v3-stats">
                  <div className="rp-v3-stat"><span>Views</span><strong>{fmt(job.view_count)}</strong></div>
                  <div className="rp-v3-stat"><span>Plays</span><strong>{fmt(job.play_count || 0)}</strong></div>
                  <div className="rp-v3-stat"><span>Likes</span><strong>{fmt(job.like_count)}</strong></div>
                  <div className="rp-v3-stat"><span>Comments</span><strong>{fmt(job.comment_count)}</strong></div>
                  <div className="rp-v3-stat"><span>Shares</span><strong>{fmt(job.share_count)}</strong></div>
                  <div className="rp-v3-stat">
                    <span>Hook Rate</span>
                    <strong>{job.view_count > 0 ? ((job.play_count || 0) / job.view_count).toFixed(2) + 'x' : '0x'}</strong>
                  </div>
                  <div className="rp-v3-stat">
                    <span>Engagement</span>
                    <strong>{job.view_count > 0 ? (((job.like_count + job.comment_count + job.share_count) / job.view_count) * 100).toFixed(1) + '%' : '0%'}</strong>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* COLUMN 3: CHAT */}
        <div className="rp-v3-col rp-v3-col--right">
          <div className="rp-v3-card rp-v3-chat-card">
            <div className="rp-v3-card-header">AI Chat Assistant</div>
            <div className="rp-v3-messages">
              {chatMessages.map((m, i) => (
                <div key={i} className={`rp-v3-msg rp-v3-msg--${m.role}`}>
                   <ReactMarkdown>{m.text}</ReactMarkdown>
                </div>
              ))}
              {isChatting && (
                <div className="rp-v3-msg rp-v3-msg--ai rp-v3-msg-thinking">
                  <div className="rp-v3-dot" />
                  <div className="rp-v3-dot" />
                  <div className="rp-v3-dot" />
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
            <div className="rp-v3-chat-footer">
              {showSkills && filteredSkills.length > 0 && (
                <div className="rp-v3-skills-dropdown">
                  {filteredSkills.map((skill, idx) => (
                    <div 
                      key={skill.cmd} 
                      className={`rp-v3-skill-item ${idx === activeSkillIdx ? 'active' : ''}`}
                      onClick={() => insertSkill(skill.cmd)}
                      onMouseEnter={() => setActiveSkillIdx(idx)}
                    >
                      <span className="rp-v3-skill-cmd">{skill.cmd}</span>
                      <span className="rp-v3-skill-desc">{skill.desc}</span>
                    </div>
                  ))}
                </div>
              )}
              <form className="rp-v3-chat-form" onSubmit={handleChatSubmit}>
                <input 
                  type="text" 
                  placeholder="Type a message or \ for commands..." 
                  value={chatInput} 
                  onChange={handleChatChange}
                  onKeyDown={handleChatKeyDown}
                  disabled={isChatting} 
                />
                <button type="submit" disabled={isChatting}>➤</button>
              </form>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}
