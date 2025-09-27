document.addEventListener("DOMContentLoaded", async () => {
  try {
    const res = await fetch("/site/config/ads.json");
    if (!res.ok) return;
    const config = await res.json();
    if (!config.enabled) return;

    config.slots.forEach(slotId => {
      document.querySelectorAll(`[data-ad="${slotId}"]`).forEach(el => {
        el.innerHTML = `
          <div style="
            background: #f0c040;
            color: #000;
            font-weight: bold;
            text-align: center;
            padding: 20px;
            margin: 10px 0;
            border: 2px dashed #333;
          ">
            🚀 Test Ad — ${slotId.toUpperCase()}
          </div>
        `;
      });
    });
  } catch (e) {
    console.error("Ad loader error:", e);
  }
});
