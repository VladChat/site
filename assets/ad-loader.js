document.addEventListener('DOMContentLoaded', async () => {
  const BASE = (document.querySelector('meta[name="site-base"]')?.content || '').replace(/\/$/, '');
  const slots = document.querySelectorAll('.ad-slot[data-ad]');
  for (const el of slots) {
    const name = el.getAttribute('data-ad');
    try {
      const res = await fetch(BASE + `/ads/${name}.html`, { cache: 'no-store' });
      if (res.ok) el.innerHTML = await res.text();
    } catch (e) { /* noop */ }
  }
});