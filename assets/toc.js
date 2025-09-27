document.addEventListener('DOMContentLoaded', () => {
  const toc = document.getElementById('toc');
  if (!toc) return;
  const headers = document.querySelectorAll('article h2, article h3');
  const ul = document.createElement('ul');
  headers.forEach(h => {
    if (!h.id) h.id = h.textContent.trim().toLowerCase().replace(/[^a-z0-9]+/g,'-');
    const li = document.createElement('li');
    if (h.tagName === 'H3') li.style.marginLeft = '12px';
    const a = document.createElement('a');
    a.href = `#${h.id}`;
    a.textContent = h.textContent;
    a.onclick = () => setTimeout(() => { document.getElementById(h.id).scrollIntoView({behavior:'smooth', block:'start'}); }, 50);
    li.appendChild(a);
    ul.appendChild(li);
  });
  toc.appendChild(ul);
});
