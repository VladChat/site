const bar = document.createElement('div');
bar.className = 'progress';
document.body.appendChild(bar);
document.addEventListener('scroll', () => {
  const h = document.documentElement;
  const scrolled = (h.scrollTop) / (h.scrollHeight - h.clientHeight);
  bar.style.width = (scrolled * 100).toFixed(2) + '%';
});
