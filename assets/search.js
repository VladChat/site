(async function(){
  const input = document.getElementById('q');
  const results = document.getElementById('results');
  if (!input || !results) return;
  const data = await fetch('/feeds/search.json', {cache:'no-store'}).then(r=>r.json()).catch(()=>[]);
  input.addEventListener('input', () => {
    const q = input.value.toLowerCase();
    results.innerHTML='';
    if (!q) return;
    const hits = data.filter(p => (p.title.toLowerCase().includes(q) || (p.description||'').toLowerCase().includes(q))).slice(0,20);
    hits.forEach(p => {
      const el = document.createElement('div');
      el.className='article-card';
      el.innerHTML = `<a href="${p.url}"><strong>${p.title}</strong></a><div class="meta">${p.date}</div><p>${p.description||''}</p>`;
      results.appendChild(el);
    });
  });
})();
