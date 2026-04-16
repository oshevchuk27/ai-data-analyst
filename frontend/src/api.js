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
  const res = await fetch(`${BASE}/api/agent_analyse`, {
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

/**
 * Stream the agent reasoning trace via Server-Sent Events.
 *
 * Calls onStep for each Think/Act event as it arrives, onStepResult when a
 * tool output is ready (to patch the last Act), onDone when the agent
 * finishes, and onError on failure.
 *
 * Returns a cancel function that aborts the request.
 *
 * @param {string} prompt
 * @param {{ role: string, content: string }[]} history
 * @param {(event: object) => void} onStep
 * @param {(output: string) => void} onStepResult
 * @param {(data: { summary: string, charts: string[] }) => void} onDone
 * @param {(err: Error) => void} onError
 * @returns {() => void} cancel
 */
export function analyzeStream(prompt, history = [], onStep, onStepResult, onDone, onError) {
  const controller = new AbortController();

  const run = async () => {
    let res;
    try {
      res = await fetch(`${BASE}/api/agent_analyse/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt, history }),
        signal: controller.signal,
      });
    } catch (err) {
      if (err.name !== 'AbortError') onError(err);
      return;
    }

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      onError(new Error(err.detail || 'Request failed'));
      return;
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        // SSE events are separated by double newlines
        const parts = buffer.split('\n\n');
        buffer = parts.pop(); // keep incomplete trailing chunk

        for (const part of parts) {
          const line = part.trim();
          if (!line.startsWith('data: ')) continue;
          try {
            const data = JSON.parse(line.slice(6));
            if (data.type === 'step') onStep(data.event);
            else if (data.type === 'step_result') onStepResult(data.output);
            else if (data.type === 'done') onDone(data);
            else if (data.type === 'error') onError(new Error(data.message));
          } catch (_) {
            // ignore malformed JSON
          }
        }
      }
    } catch (err) {
      if (err.name !== 'AbortError') onError(err);
    }
  };

  run();
  return () => controller.abort();
}

export async function healthCheck() {
  const res = await fetch(`${BASE}/health`);
  return res.json();
}
