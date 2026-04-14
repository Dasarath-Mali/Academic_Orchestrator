// app.js – Shared utilities for the Academic Orchestrator dashboard

/**
 * Highlight the active nav link based on current path.
 */
(function markActiveNav() {
  const path = window.location.pathname;
  document.querySelectorAll('.nav-link').forEach(link => {
    link.classList.toggle('active', link.getAttribute('href') === path);
  });
})();

/**
 * Format a datetime string into a readable local format.
 * @param {string} iso - ISO 8601 datetime string
 * @returns {string}
 */
function formatDate(iso) {
  const d = new Date(iso);
  return d.toLocaleString('en-IN', {
    day: 'numeric', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit'
  });
}

/**
 * Calculate days remaining until a date.
 * @param {string} iso
 * @returns {number} - negative if in the past
 */
function daysUntil(iso) {
  return Math.ceil((new Date(iso) - new Date()) / 86400000);
}

/**
 * Minimal markdown renderer (bold, headers, lists).
 * @param {string} text
 * @returns {string} HTML string
 */
function renderMarkdown(text) {
  if (!text) return '';
  return text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`(.+?)`/g, '<code>$1</code>')
    .replace(/^#### (.+)$/gm, '<h4>$1</h4>')
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/^- (.+)$/gm, '<li>$1</li>')
    .replace(/(<li>.*<\/li>)/gs, '<ul>$1</ul>')
    .replace(/\n{2,}/g, '</p><p>')
    .replace(/\n/g, '<br>');
}

/**
 * Show a temporary toast notification.
 * @param {string} message
 * @param {'success'|'error'|'info'} type
 */
function showToast(message, type = 'info') {
  const existing = document.getElementById('toast-container');
  if (existing) existing.remove();

  const container = document.createElement('div');
  container.id = 'toast-container';
  container.style.cssText = `
    position: fixed; bottom: 24px; right: 24px; z-index: 1000;
    background: var(--bg-card); border: 1px solid var(--border);
    border-radius: 10px; padding: 14px 20px;
    font-family: var(--font); font-size: 14px;
    box-shadow: 0 8px 32px rgba(0,0,0,0.4);
    max-width: 360px; line-height: 1.4;
    color: ${{ success: 'var(--green)', error: 'var(--red)', info: 'var(--accent)' }[type]};
    animation: slideIn 0.2s ease;
  `;
  container.textContent = message;

  const style = document.createElement('style');
  style.textContent = `@keyframes slideIn { from { transform: translateY(20px); opacity:0 } to { transform:translateY(0); opacity:1 } }`;
  document.head.appendChild(style);
  document.body.appendChild(container);

  setTimeout(() => container.remove(), 4000);
}

/**
 * Generic fetch wrapper with error handling.
 * @param {string} url
 * @param {RequestInit} [options]
 * @returns {Promise<any>}
 */
async function apiFetch(url, options = {}) {
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
  return data;
}
