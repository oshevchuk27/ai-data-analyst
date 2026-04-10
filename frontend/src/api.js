/**
 * api.js — typed client for the AI Data Analyst backend.
 */

const BASE = import.meta.env.VITE_API_URL || '';

/**
 * @param {string} prompt
 * @param {{ role: string, content: string }[]} history
 * @returns {Promise<import('./types').AnalyzeResponse>}
 */
export async function analyze(prompt, history = []) {
  const res = await fetch(`${BASE}/api/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ prompt, history }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Request failed');
  }

  return res.json();
}

export async function healthCheck() {
  const res = await fetch(`${BASE}/health`);
  return res.json();
}
