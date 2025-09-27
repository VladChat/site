document.addEventListener('DOMContentLoaded', async () => {
  const slots = document.querySelectorAll('.ad-slot[data-ad]');
  for (const el of slots) {
    const name = el.getAttribute('data-ad');
    try {
      const res = await fetch(`/ads/${name}.html`, { cache: 'no-store' });
      if (res.ok) el.innerHTML = await res.text();
    } catch (e) { /* noop */ }
  }
});
