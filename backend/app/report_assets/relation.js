/* The relation box of the offline pages (the 2D map and the 3D view, 1.26) - the app's relation box
   (RelationPanel.tsx) in plain JS: the reference and the compared object at the page's time - range,
   horizontal distance, Δalt, bearing, relative bearing, closure, closest-approach time, heading Δ. The
   pair is chosen in its header (solid ring: the reference, dashed: compared); the toolbar's Relation
   button shows / hides it. Objects: {name, color, t[], E[], N[], U[] | null, yaw[] | null} in local metres
   (east / north / up) on one origin. */
function svRelation(host, objs, S, pair, onPair, onSeek) {
  "use strict";
  const api = { pair: { p: 0, s: 1 }, update: function () {}, el: null, at: null };
  const bs = function (a, v) { let lo = 0, hi = a.length - 1; while (lo < hi) { const m = (lo + hi + 1) >> 1; if (a[m] <= v) lo = m; else hi = m - 1; } return lo; };
  const wrap = function (d) { return ((d + 540) % 360) - 180; };
  // an object at time t (interpolated; angles the short way), null outside its span
  const at = function (o, t) {
    const n = o.t.length;
    if (!n || t < o.t[0] - 1e-9 || t > o.t[n - 1] + 1e-9) return null;
    const k = bs(o.t, t), k2 = Math.min(n - 1, k + 1), f = o.t[k2] > o.t[k] ? (t - o.t[k]) / (o.t[k2] - o.t[k]) : 0;
    const L = function (a) { return a ? a[k] + (a[k2] - a[k]) * f : null; };
    const y = o.yaw && o.yaw[k] !== null && o.yaw[k2] !== null ? o.yaw[k] + wrap(o.yaw[k2] - o.yaw[k]) * f : null;
    return { e: L(o.E), n: L(o.N), u: o.U ? L(o.U) : null, yaw: y };
  };
  api.at = at;
  const idx = function (name, d) { const i = objs.findIndex(function (o) { return o.name === name; }); return i >= 0 ? i : d; };
  api.pair.p = idx(pair && pair.primary, 0);
  api.pair.s = idx(pair && pair.secondary, api.pair.p === 0 ? 1 : 0);
  if (api.pair.s === api.pair.p) api.pair.s = api.pair.p === 0 ? 1 : 0;
  if (objs.length < 2) return api;
  const dist = function (m) { const a = Math.abs(m); return a >= 1000 ? (m / 1000).toFixed(a >= 10000 ? 1 : 2) + " km" : m.toFixed(a >= 100 ? 0 : 1) + " m"; };
  const deg = function (v) { return v === null ? "—" : v.toFixed(1) + "°"; };
  const box = document.createElement("div"); box.className = "svrel"; box.setAttribute("role", "region"); box.setAttribute("aria-label", S.relation);
  const head = document.createElement("div"); head.className = "svrel-head";
  const fold = document.createElement("button"); fold.className = "svrel-fold"; fold.textContent = "▾"; fold.title = S.fold;
  const sel = function (cls, label, v) {
    const l = document.createElement("label"); l.className = cls; l.title = label;
    const ring = document.createElement("i"); ring.className = "svring " + (cls === "svrel-ref" ? "p" : "s");
    const s = document.createElement("select"); s.setAttribute("aria-label", label);
    objs.forEach(function (o, i) { const op = document.createElement("option"); op.value = i; op.textContent = o.name; s.append(op); });
    s.value = String(v); l.append(ring, s); return { l: l, s: s };
  };
  const ref = sel("svrel-ref", S.ref, api.pair.p), cmp = sel("svrel-cmp", S.cmp, api.pair.s);
  const swap = document.createElement("button"); swap.className = "svrel-swap"; swap.textContent = "⇄"; swap.title = S.swap;
  const close = document.createElement("button"); close.className = "svrel-close"; close.textContent = "×"; close.title = S.hide;
  head.append(fold, ref.l, swap, cmp.l, close);
  const body = document.createElement("div"); body.className = "svrel-body";
  box.append(head, body); host.append(box);
  api.el = box;
  let lastT = null;
  const changed = function () { onPair && onPair(api.pair); if (lastT !== null) api.update(lastT); };
  ref.s.onchange = function () { api.pair.p = +ref.s.value; if (api.pair.s === api.pair.p) { api.pair.s = objs.findIndex(function (_, i) { return i !== api.pair.p; }); cmp.s.value = api.pair.s; } changed(); };
  cmp.s.onchange = function () { api.pair.s = +cmp.s.value; if (api.pair.s === api.pair.p) { api.pair.p = objs.findIndex(function (_, i) { return i !== api.pair.s; }); ref.s.value = api.pair.p; } changed(); };
  swap.onclick = function () { const p = api.pair.p; api.pair.p = api.pair.s; api.pair.s = p; ref.s.value = api.pair.p; cmp.s.value = api.pair.s; changed(); };
  fold.onclick = function () { body.hidden = !body.hidden; fold.textContent = body.hidden ? "▸" : "▾"; fold.title = body.hidden ? S.unfold : S.fold; };
  close.onclick = function () { api.show(false); };
  api.onShow = null;
  api.show = function (on) { box.hidden = !on; if (api.onShow) api.onShow(on); };
  api.shown = function () { return !box.hidden; };
  api.update = function (t) {
    lastT = t;
    const P = objs[api.pair.p], Q = objs[api.pair.s];
    const p0 = at(P, t), s0 = at(Q, t), p1 = at(P, t + 0.5), s1 = at(Q, t + 0.5);
    body.textContent = "";
    if (!p0 || !s0) { body.textContent = S.noTime; return; }
    const de = s0.e - p0.e, dn = s0.n - p0.n, du = p0.u !== null && s0.u !== null ? s0.u - p0.u : null;
    const horiz = Math.hypot(de, dn), slant = du !== null ? Math.hypot(horiz, du) : null;
    const brg = (Math.atan2(de, dn) * 180 / Math.PI + 360) % 360;
    const rows = [[S.range, dist(slant !== null ? slant : horiz)]];
    if (slant !== null) rows.push([S.horiz, dist(horiz)]);
    if (du !== null) rows.push([S.dalt, (du >= 0 ? "+" : "") + dist(du)]);
    rows.push([S.bearing, deg(brg)]);
    if (p0.yaw !== null) rows.push([S.relBearing, deg(wrap(brg - p0.yaw))]);
    if (p1 && s1) {
      const r0 = slant !== null ? slant : horiz;
      const de1 = s1.e - p1.e, dn1 = s1.n - p1.n, du1 = du !== null && p1.u !== null && s1.u !== null ? s1.u - p1.u : 0;
      const r1 = du !== null ? Math.hypot(de1, dn1, du1) : Math.hypot(de1, dn1);
      rows.push([S.closure, (-(r1 - r0) / 0.5).toFixed(1) + " m/s"]);
      const v = [(de1 - de) / 0.5, (dn1 - dn) / 0.5, du !== null ? (du1 - du) / 0.5 : 0], rr = [de, dn, du || 0];
      const vv = v[0] * v[0] + v[1] * v[1] + v[2] * v[2];
      const tca = vv > 1e-9 ? -(rr[0] * v[0] + rr[1] * v[1] + rr[2] * v[2]) / vv : null;
      if (tca !== null && tca > 0 && tca < 3600) rows.push([S.tca, tca.toFixed(1) + " s", t + tca]);   // a click: go there
    }
    if (p0.yaw !== null && s0.yaw !== null) rows.push([S.hdgDiff, deg(wrap(s0.yaw - p0.yaw))]);
    rows.forEach(function (r) { const d = document.createElement("div"); const a = document.createElement("span"); const b = document.createElement("bdi");
      a.textContent = r[0]; b.textContent = r[1]; b.dir = "ltr"; d.append(a, b); body.append(d);
      if (r[2] !== undefined && onSeek) { d.className = "seek"; d.title = S.tcaGo; d.tabIndex = 0;
        const go = function () { onSeek(r[2]); }; d.onclick = go; d.onkeydown = function (e) { if (e.key === "Enter") go(); }; } });
    api.value = { horiz: horiz, slant: slant, bearing: brg };          // for tests
  };
  return api;
}

/* The toolbar both pages share: its words, the camera (Free · Centre · Close) and the object it is on
   (default the reference). `set(mode)` is called on a change. */
function svToolbar(S, objs, start, set) {
  "use strict";
  const $ = function (id) { return document.getElementById(id); };
  const words = { camT: S.camera, objT: S.object, timeT: S.time, help: S.help };
  Object.keys(words).forEach(function (id) { if ($(id)) $(id).textContent = words[id]; });
  [["zin", S.zin], ["zout", S.zout], ["fit", S.fit], ["theme", S.theme], ["rel", S.relationHint], ["top", S.top], ["trail", S.trail]].forEach(function (p) {
    const b = $(p[0]); if (b) { b.title = p[1]; b.setAttribute("aria-label", p[1]); } });
  if ($("rel")) $("rel").textContent = S.relation;
  if ($("slider")) $("slider").setAttribute("aria-label", S.time);
  const cams = Array.prototype.slice.call(document.querySelectorAll("#cam button"));
  const label = { free: S.camFree, centre: S.camCentre, close: S.camClose }, hint = { free: S.camFreeHint, centre: S.camCentreHint, close: S.camCloseHint };
  cams.forEach(function (b) { b.textContent = label[b.dataset.cam]; b.title = hint[b.dataset.cam]; });
  const sel = $("obj");
  objs.forEach(function (o, i) { const op = document.createElement("option"); op.value = i; op.textContent = o.name; sel.append(op); });
  sel.value = String(start.obj);
  const h = svHash.read();
  const st = { mode: ["free", "centre", "close"].indexOf(h.cam) >= 0 ? h.cam : start.mode, obj: h.obj !== undefined && objs[+h.obj] ? +h.obj : start.obj };
  sel.value = String(st.obj);
  const show = function () { cams.forEach(function (b) { const on = b.dataset.cam === st.mode; b.classList.toggle("on", on); b.setAttribute("aria-checked", String(on)); }); };
  cams.forEach(function (b) { b.addEventListener("click", function () { st.mode = b.dataset.cam; show(); set(st, true); }); });
  sel.addEventListener("change", function () { st.obj = +sel.value; if (st.mode === "free") st.mode = "centre"; show(); set(st, true); });
  show();
  return { st: st, free: function () { if (st.mode !== "free") { st.mode = "free"; show(); set(st, false); } } };
}

/* The time a page moves to: its own slider, or - inside a replay page or a live report - the page's one time
   (the report's viewer.js listens for "replay-seek"). */
function svSeek(slider, t, draw) {
  "use strict";
  if (window.parent && window.parent !== window) { try { window.parent.postMessage({ sv: "replay-seek", t: t }, "*"); } catch (e) { /* no parent page */ } }
  slider.value = Math.min(+slider.max, Math.max(+slider.min, t)); draw();
}

/* The trail: the whole track, or only the last seconds of it (a long flight over the same field reads better). */
function svTrail(S, onChange) {
  "use strict";
  const sel = document.getElementById("trail");
  if (!sel) return { sec: 0 };
  const st = { sec: 0 };
  document.getElementById("trailT").textContent = S.trail;
  [["0", S.trailAll], ["60", "60 s"], ["20", "20 s"]].forEach(function (p) { const o = document.createElement("option"); o.value = p[0]; o.textContent = p[1]; sel.append(o); });
  sel.onchange = function () { st.sec = +sel.value; onChange(); };
  return st;
}

/* A page opened on its own keeps the view in its address: #t=…&cam=…&obj=… - a link to the same moment, camera
   and object (paste it with the file). Inside a report the report's own address keeps the time. */
const svHash = {
  read: function () {
    const out = {};
    (location.hash || "").replace(/^#/, "").split("&").forEach(function (kv) { const p = kv.split("="); if (p.length === 2) out[p[0]] = decodeURIComponent(p[1]); });
    return out;
  },
  write: function (t, cam) {
    if (window.parent && window.parent !== window) return;
    try { history.replaceState(null, "", "#t=" + (+t).toFixed(2) + "&cam=" + cam.mode + "&obj=" + cam.obj); } catch (e) { /* a page without history */ }
  },
};
