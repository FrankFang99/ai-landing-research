/* docs/assets/render.js
 * 渲染 SITE_DATA 到页面
 */
(function () {
  const D = window.SITE_DATA || {};
  const $ = (s) => document.querySelector(s);

  // ===== meta pills =====
  if (D.stats) {
    if (D.stats.last_update) {
      $('#meta-updated').textContent = '最近更新：' + D.stats.last_update;
    }
    if (D.stats.total_cases !== undefined) {
      $('#meta-count').textContent = '案例数：' + D.stats.total_cases;
    }
  }

  // ===== industries =====
  const ig = $('#industries-grid');
  if (ig && Array.isArray(D.industries)) {
    ig.innerHTML = D.industries.map((it) => `
      <div class="ind-card">
        <div class="ind-rank">No.${String(it.rank).padStart(2, '0')}</div>
        <div class="ind-name">${escapeHtml(it.name)}</div>
        <div class="ind-priority">${escapeHtml(it.priority)} · ${escapeHtml(it.tag || '')}</div>
        <div class="ind-desc">${escapeHtml(it.desc || '')}</div>
      </div>
    `).join('');
  }

  // ===== latest =====
  const lg = $('#latest-grid');
  if (lg) {
    if (!Array.isArray(D.latest) || D.latest.length === 0) {
      lg.innerHTML = '<div class="empty">暂无最新更新 — 等下周 cron 第一次跑完就有了。</div>';
    } else {
      lg.innerHTML = D.latest.map((c) => `
        <a class="latest-card" href="${escapeAttr(c.url || '#')}" target="_blank" rel="noopener">
          <span class="latest-tag">${escapeHtml(c.industry || '案例')}</span>
          <h4>${escapeHtml(c.title)}</h4>
          <p>${escapeHtml(c.summary || '')}</p>
          <div class="latest-foot">
            <span>${escapeHtml(c.source || '')}</span>
            <span class="latest-date">${escapeHtml(c.date || '')}</span>
          </div>
        </a>
      `).join('');
    }
  }

  function escapeHtml(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }
  function escapeAttr(s) {
    return escapeHtml(s);
  }
})();