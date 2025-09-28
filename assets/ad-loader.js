document.addEventListener("DOMContentLoaded", () => {
  fetch("/site/config/ads.json")
    .then((res) => res.json())
    .then((config) => {
      if (!config.enabled) return;

      Object.entries(config.slots).forEach(([slot, html]) => {
        document.querySelectorAll(`.ad-slot[data-ad="${slot}"]`).forEach((el) => {
          el.innerHTML = html;
        });
      });
    })
    .catch((err) => {
      console.error("Ad loader error:", err);
    });
});
