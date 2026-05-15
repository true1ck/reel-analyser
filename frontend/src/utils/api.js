const API_BASE = 'http://localhost:8000/api';
const WS_URL = 'ws://localhost:8000/ws';

export async function fetchJobs({ status, category, search, limit = 50, offset = 0 } = {}) {
  const params = new URLSearchParams();
  if (status) params.set('status', status);
  if (category) params.set('category', category);
  if (search) params.set('search', search);
  params.set('limit', limit);
  params.set('offset', offset);
  const res = await fetch(`${API_BASE}/jobs?${params}`);
  if (!res.ok) throw new Error('Failed to fetch jobs');
  return res.json();
}

export async function fetchJob(id) {
  const res = await fetch(`${API_BASE}/jobs/${id}`);
  if (!res.ok) throw new Error('Job not found');
  return res.json();
}

export async function createJobs(urls) {
  const res = await fetch(`${API_BASE}/jobs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ urls }),
  });
  if (!res.ok) throw new Error('Failed to create jobs');
  return res.json();
}

export async function createChannelJobs(channel_url, limit = 5, category = "Uncategorized") {
  const res = await fetch(`${API_BASE}/jobs/channel`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ channel_url, limit, category }),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || 'Failed to create channel jobs');
  }
  return res.json();
}

export async function retryJob(id) {
  const res = await fetch(`${API_BASE}/jobs/${id}/retry`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to retry job');
  return res.json();
}

export async function stopJob(id) {
  const res = await fetch(`${API_BASE}/jobs/${id}/stop`, { method: 'POST' });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to stop job');
  }
  return res.json();
}

export async function deleteJob(id) {
  const res = await fetch(`${API_BASE}/jobs/${id}`, { method: 'DELETE' });
  if (!res.ok) throw new Error('Failed to delete job');
  return res.json();
}

export async function updateJob(id, data) {
  const res = await fetch(`${API_BASE}/jobs/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error('Failed to update job');
  return res.json();
}

export async function fetchStats() {
  const res = await fetch(`${API_BASE}/stats`);
  if (!res.ok) throw new Error('Failed to fetch stats');
  return res.json();
}

export async function fetchCollections() {
  const res = await fetch(`${API_BASE}/collections`);
  if (!res.ok) throw new Error('Failed to fetch collections');
  return res.json();
}

export function getVideoUrl(jobId) {
  return `${API_BASE}/jobs/${jobId}/video`;
}

export async function sendChatMessage(jobId, message) {
  const res = await fetch(`${API_BASE}/jobs/${jobId}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message }),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || 'Failed to send message');
  }
  return res.json();
}

export { WS_URL };

// ── Analytics ────────────────────────────────────────────────────────────────

export async function fetchTopReels(sortBy = 'likes', limit = 10) {
  const res = await fetch(`${API_BASE}/analytics/top?sort_by=${sortBy}&limit=${limit}`);
  if (!res.ok) throw new Error('Failed to fetch top reels');
  return res.json();
}

export async function fetchCreators(limit = 20) {
  const res = await fetch(`${API_BASE}/analytics/creators?limit=${limit}`);
  if (!res.ok) throw new Error('Failed to fetch creators');
  return res.json();
}

export async function fetchTrendingHashtags(limit = 20) {
  const res = await fetch(`${API_BASE}/analytics/trending-hashtags?limit=${limit}`);
  if (!res.ok) throw new Error('Failed to fetch hashtags');
  return res.json();
}
