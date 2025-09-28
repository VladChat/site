document.addEventListener('DOMContentLoaded', () => {
  const BASE = (document.querySelector('meta[name="site-base"]')?.content || '').replace(/\/$/, '');
  const url = (BASE ? BASE : '') + '/config/ads.json?v=' + Date.now();
  fetch(url, { cache: 'no-store' })
    .then((res) => res.json())
    .then((config) => {
      if (!config || config.enabled === false) return;
      const slots = config.slots || {};
      Object.entries(slots).forEach(([slot, html]) => {
        document.querySelectorAll(`.ad-slot[data-ad="${slot}"]`).forEach((el) => {
          el.innerHTML = html;
          el.dataset.loaded = '1';
        });
      });
    })
    .catch((err) => {
      console.error('Ad loader error:', err);
    });
});