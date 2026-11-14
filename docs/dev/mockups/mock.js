/* PLAN_2026-11-14 mock-ups: the corner switch (?theme=light|dark, ?lang=en|he, ?notes=0) and a small SVG plot
   drawer with made-up but plausible signals. Not app code. */
(function () {
  const q = new URLSearchParams(location.search);
  const theme = q.get("theme") || "dark", lang = q.get("lang") || "en";
  document.documentElement.dataset.theme = theme;
  document.documentElement.lang = lang;
  document.documentElement.dir = lang === "he" ? "rtl" : "ltr";
  window.MOCK = { theme, lang };
  document.addEventListener("DOMContentLoaded", () => {
    if (q.get("notes") === "0") document.body.classList.add("no-notes");
    if (lang === "he") document.querySelectorAll("[data-he]").forEach((e) => { e.textContent = e.dataset.he; });
    const bar = document.createElement("div");
    bar.className = "mockbar";
    const go = (k, v) => { const n = new URLSearchParams(location.search); n.set(k, v); location.search = n.toString(); };
    for (const [label, k, v] of [["Dark", "theme", "dark"], ["Light", "theme", "light"], ["EN", "lang", "en"], ["HE", "lang", "he"],
      [q.get("notes") === "0" ? "Notes on" : "Notes off", "notes", q.get("notes") === "0" ? "1" : "0"]]) {
      const b = document.createElement("button"); b.textContent = label; b.onclick = () => go(k, v); bar.appendChild(b);
    }
    document.body.appendChild(bar);
    document.querySelectorAll("[data-plot]").forEach((el) => drawPlot(el, PLOTS[el.dataset.plot]));
  });

  // deterministic noise
  let seed = 7;
  const rnd = () => { seed = (seed * 16807) % 2147483647; return seed / 2147483647 - 0.5; };
  const C = ["#0072B2", "#E69F00", "#009E73", "#D55E00", "#56B4E9", "#CC79A7"];
  const series = (n, f) => Array.from({ length: n }, (_, i) => f(i / (n - 1), i));
  const PLOTS = {
    att: { y: [-30, 30], ticks: [-30, -15, 0, 15, 30], cur: 0.62, lines: [
      { c: C[4], d: series(420, (x) => 18 * Math.sin(x * 22) * Math.exp(-((x - 0.55) ** 2) * 6) + rnd() * 2.2) },
      { c: C[1], d: series(420, (x) => 18 * Math.sin(x * 22 - 0.25) * Math.exp(-((x - 0.55) ** 2) * 6) + rnd() * 0.8) }] },
    alt: { y: [0, 120], ticks: [0, 40, 80, 120], cur: 0.62, lines: [
      { c: C[2], d: series(300, (x) => (x < 0.08 ? x * 1100 : x > 0.9 ? (1 - x) * 900 : 88 + 12 * Math.sin(x * 9)) + rnd() * 2) },
      { c: C[5], d: series(300, (x) => (x < 0.08 ? x * 1100 : x > 0.9 ? (1 - x) * 900 : 90 + 12 * Math.sin(x * 9 - 0.2))) }] },
    vib: { y: [0, 60], ticks: [0, 30, 60], cur: 0.62, limit: 30, lines: [
      { c: C[0], d: series(420, (x) => 14 + 10 * x + Math.abs(rnd()) * 18 + (x > 0.7 && x < 0.74 ? 22 : 0)) },
      { c: C[3], d: series(420, (x) => 9 + 6 * x + Math.abs(rnd()) * 10) }] },
    pc: null,
  };
  window.MOCK_PLOTS = PLOTS;

  function drawPlot(el, p) {
    if (!p) return;
    const r = el.getBoundingClientRect(), W = Math.max(200, r.width), H = Math.max(80, r.height);
    const L = 40, R = 8, T = 10, B = 20, rtl = document.documentElement.dir === "rtl";
    const sx = (x) => L + x * (W - L - R), sy = (v) => T + (1 - (v - p.y[0]) / (p.y[1] - p.y[0])) * (H - T - B);
    let s = `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">`;
    for (const t of p.ticks) s += `<line class="gridl" x1="${L}" x2="${W - R}" y1="${sy(t)}" y2="${sy(t)}"/><text class="tick" x="${L - 6}" y="${sy(t) + 3}" text-anchor="end">${t}</text>`;
    for (let i = 0; i <= 6; i++) { const x = sx(i / 6); s += `<line class="gridl" x1="${x}" x2="${x}" y1="${T}" y2="${H - B}"/><text class="tick" x="${x}" y="${H - 5}" text-anchor="middle">${i * 40}</text>`; }
    if (p.limit !== undefined) s += `<line x1="${L}" x2="${W - R}" y1="${sy(p.limit)}" y2="${sy(p.limit)}" stroke="var(--danger)" stroke-dasharray="6 4" stroke-width="1"/>`;
    for (const ln of p.lines) {
      const d = ln.d.map((v, i) => `${i ? "L" : "M"}${sx(i / (ln.d.length - 1)).toFixed(1)} ${sy(v).toFixed(1)}`).join("");
      s += `<path d="${d}" fill="none" stroke="${ln.c}" stroke-width="1.4" stroke-linejoin="round"/>`;
    }
    if (p.cur !== undefined) {
      const cx = sx(p.cur);
      s += `<line class="cursor" x1="${cx}" x2="${cx}" y1="${T}" y2="${H - B}"/>`;
      for (const ln of p.lines) { const v = ln.d[Math.round(p.cur * (ln.d.length - 1))]; s += `<circle cx="${cx}" cy="${sy(v)}" r="3.2" fill="${ln.c}" stroke="var(--plot-bg)" stroke-width="1.5"/>`; }
    }
    s += "</svg>";
    el.innerHTML = s + (p.cur !== undefined ? `<span class="flag" style="left:${(sx(p.cur) / W) * 100}%">${(p.cur * 240).toFixed(1)} s</span>` : "");
    el.style.background = "var(--plot-bg)"; el.style.borderRadius = "var(--r-m)";
    if (rtl) el.style.direction = "ltr";       // a time axis runs left to right in Hebrew too (as in the app)
  }
  window.drawPlot = drawPlot;
})();
