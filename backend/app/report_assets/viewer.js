/* Signal Viewer — standalone interactive report viewer.
   Everything this file needs is embedded in the HTML: uPlot, the data and this script.
   Time signals carry several min/max resolution levels; zooming switches to the
   finest level that keeps the visible point count reasonable, so detail appears
   as you zoom in without any server. */
(function () {
  "use strict";
  var R = JSON.parse(document.getElementById("sv-data").textContent);
  var root = document.documentElement;
  var T = R.strings;
  // R1: a replay page has one time for the whole page (report.py's _replay); a report keeps a cursor per plot
  var RP = R.replay || null;

  function dec(b64, Ctor) {
    var bin = atob(b64), u = new Uint8Array(bin.length);
    for (var i = 0; i < bin.length; i++) u[i] = bin.charCodeAt(i);
    return new Ctor(u.buffer);
  }
  function arr(o) {
    if (!o.__x) { o.__x = dec(o.x, Float64Array); o.__y = dec(o.y, Float32Array); }
    return [o.__x, o.__y];
  }
  function fmt(v, d) {
    if (v === null || v === undefined || !isFinite(v)) return "—";
    var a = Math.abs(v);
    if (a !== 0 && (a >= 1e6 || a < 1e-3)) return v.toExponential(3);
    return Number(v.toPrecision(d || 5)).toLocaleString(R.lang === "he" ? "he-IL" : "en-US", { maximumSignificantDigits: d || 5 });
  }
  function ticks(u, splits) {
    return splits.map(function (v) {
      if (v === null || !isFinite(v)) return "";
      var a = Math.abs(v);
      if (a !== 0 && (a < 1e-3 || a >= 1e6)) return v.toExponential(0).replace("e+", "e");
      return String(+v.toPrecision(6));
    });
  }
  function lowerBound(a, v) { var lo = 0, hi = a.length; while (lo < hi) { var m = (lo + hi) >> 1; if (a[m] < v) lo = m + 1; else hi = m; } return lo; }
  function interp(x, y, t) {
    var n = x.length; if (!n) return null;
    if (t <= x[0]) return y[0]; if (t >= x[n - 1]) return y[n - 1];
    var i = lowerBound(x, t); var t0 = x[i - 1], t1 = x[i];
    return t1 === t0 ? y[i] : y[i - 1] + (y[i] - y[i - 1]) * (t - t0) / (t1 - t0);
  }
  function css(name) { return getComputedStyle(root).getPropertyValue(name).trim(); }

  var orderedLines = function (u, si) {
    var xs = u.data[si][0], ys = u.data[si][1], p = new Path2D(), pen = false;
    for (var i = 0; i < xs.length; i++) {
      var y = ys[i];
      if (y === null || !isFinite(y)) { pen = false; continue; }
      var cx = u.valToPos(xs[i], "x", true), cy = u.valToPos(y, "y", true);
      if (pen) p.lineTo(cx, cy); else { p.moveTo(cx, cy); pen = true; }
    }
    var b = u.bbox, clip = new Path2D(); clip.rect(b.left, b.top, b.width, b.height);
    return { stroke: p, fill: null, clip: clip, band: null, gaps: null, flags: 0 };
  };

  function flag(ctx, x, top, text, bg, fg, b) {
    var r = devicePixelRatio || 1;
    ctx.font = 11 * r + "px " + getComputedStyle(document.body).fontFamily;
    ctx.textBaseline = "middle"; ctx.textAlign = "left";
    var tw = ctx.measureText(text).width + 10 * r, th = 17 * r, fx = x + 1;
    if (fx + tw > b.left + b.width) fx = x - tw;
    ctx.fillStyle = bg; ctx.fillRect(fx, top, tw, th);
    ctx.fillStyle = fg; ctx.fillText(text, fx + 5 * r, top + th / 2 + r);
  }

  /* ------------------------------------------------------------- one plot */
  function Plot(spec, host) {
    this.spec = spec; this.host = host; this.cursor = RP && spec.mode === "time" ? RP.t : null; this.u = null;
    this.legend = host.querySelector(".legend"); this.canvas = host.querySelector(".canvas");
    this.hidden = {};
    this.build();
  }
  Plot.prototype.timeData = function (x0, x1) {
    var tables = [];
    this.spec.signals.forEach(function (s) {
      var lv = s.levels, pick = lv[0];
      if (x0 !== null) {
        for (var k = lv.length - 1; k >= 0; k--) {           // finest first
          var a = arr(lv[k]), c = lowerBound(a[0], x1) - lowerBound(a[0], x0);
          if (c <= 20000 || k === 0) { pick = lv[k]; break; }
        }
      }
      var d = arr(pick), xs = d[0], ys = d[1], i0 = 0, i1 = xs.length;
      if (x0 !== null && pick !== lv[0]) { i0 = Math.max(0, lowerBound(xs, x0) - 2); i1 = Math.min(xs.length, lowerBound(xs, x1) + 2); }
      var X = Array.prototype.slice.call(xs, i0, i1), Y = new Array(i1 - i0);
      for (var i = i0; i < i1; i++) Y[i - i0] = isFinite(ys[i]) ? ys[i] : null;
      tables.push([X, Y]);
    });
    return tables.length === 1 ? tables[0] : uPlot.join(tables, tables.map(function () { return [1]; }));
  };
  Plot.prototype.build = function () {
    var self = this, spec = this.spec;
    if (this.u) this.u.destroy();
    var axis = { stroke: css("--axis"), grid: { stroke: css("--grid"), width: 1 }, ticks: { stroke: css("--grid"), width: 1 },
      font: "11px " + getComputedStyle(document.body).fontFamily, labelFont: "11px " + getComputedStyle(document.body).fontFamily };
    var w = this.canvas.clientWidth || 800, h = 340, amber = css("--amber"), amberInk = css("--amber-ink");
    var opts, data;
    var drawCursor = function (u) {
      if (self.cursor === null || spec.mode !== "time") return;
      var b = u.bbox, x = Math.round(u.valToPos(self.cursor, "x", true)) + 0.5;
      if (x < b.left || x > b.left + b.width) return;
      var ctx = u.ctx; ctx.save(); ctx.strokeStyle = amber; ctx.lineWidth = 1.5 * (devicePixelRatio || 1);
      ctx.beginPath(); ctx.moveTo(x, b.top); ctx.lineTo(x, b.top + b.height); ctx.stroke();
      flag(ctx, x, b.top, fmt(self.cursor, 7), amber, amberInk, b); ctx.restore();
    };
    var drawStates = function (u) {
      var b = u.bbox, ctx = u.ctx; ctx.save();
      spec.signals.forEach(function (s, k) {
        if (!s.states || self.hidden[k]) return;
        s.states.forEach(function (p, i) {
          var x = Math.round(u.valToPos(p[0], "x", true)) + 0.5;
          if (x < b.left || x > b.left + b.width) return;
          if (i > 0) { ctx.globalAlpha = 0.55; ctx.strokeStyle = s.color; ctx.lineWidth = devicePixelRatio || 1;
            ctx.beginPath(); ctx.moveTo(x, b.top); ctx.lineTo(x, b.top + b.height); ctx.stroke(); ctx.globalAlpha = 1; }
          flag(ctx, x, b.top + (20 + k * 19) * (devicePixelRatio || 1), String(p[1]), s.color, "#fff", b);
        });
      });
      ctx.restore();
    };
    var series = [{}].concat(spec.signals.map(function (s, k) {
      var o = { stroke: s.color, width: s.width || 1.5, points: { show: false }, show: !self.hidden[k], label: s.label };
      if (spec.mode === "xy") o.paths = orderedLines;
      else if (s.state) o.paths = uPlot.paths.stepped({ align: 1 });
      if (spec.mode === "time" && s.axis === "right") o.scale = "y2";   // T47: the second value axis
      return o;
    }));
    var hasRight = spec.mode === "time" && spec.signals.some(function (s) { return s.axis === "right"; });
    if (spec.mode === "time") {
      var r0 = spec.range;
      data = this.timeData(r0 ? r0[0] : null, r0 ? r0[1] : null);
      opts = { width: w, height: h, padding: [8, 12, 0, 4], legend: { show: false },
        cursor: { y: false, drag: { x: true, y: false, setScale: false }, bind: { dblclick: function () { return null; } } },
        scales: hasRight ? { x: { time: false, auto: !r0, range: r0 ? function () { return [r0[0], r0[1]]; } : undefined }, y2: { auto: true } }
          : { x: { time: false, auto: !r0, range: r0 ? function () { return [r0[0], r0[1]]; } : undefined } },
        axes: [Object.assign({}, axis, { size: 34 }), Object.assign({}, axis, { size: 56, values: ticks })]
          .concat(hasRight ? [Object.assign({}, axis, { scale: "y2", side: 1, size: 56, values: ticks, grid: { show: false } })] : []),
        series: series,
        hooks: { draw: [drawStates, drawCursor], setSelect: [function (u) {
          if (u.select.width < 4) return;
          var a = u.posToVal(u.select.left, "x"), c = u.posToVal(u.select.left + u.select.width, "x");
          u.setSelect({ left: 0, top: 0, width: 0, height: 0 }, false); self.zoom(a, c);
        }] } };
    } else if (spec.mode === "env") {
      // T14b: envelope of many runs - min…max (faint), percentile band, median
      var E = spec.env, c = spec.envColor || "#3D8BFD";
      if (!E) return;
      var f32 = function (k) { return Array.from(dec(E[k], Float32Array), function (v) { return isFinite(v) ? v : null; }); };
      data = [Array.from(dec(E.t, Float64Array)), f32("min"), f32("max"), f32("lo"), f32("hi"), f32("median")];
      var faint = { stroke: c + "55", width: 0.75, points: { show: false } };
      opts = { width: w, height: h, padding: [8, 12, 0, 4], legend: { show: false },
        cursor: { y: false, drag: { x: true, y: false, setScale: true } },
        scales: { x: { time: false } },
        axes: [Object.assign({}, axis, { size: 34 }), Object.assign({}, axis, { size: 56, values: ticks })],
        series: [{}, faint, faint, faint, faint, { stroke: c, width: 2, points: { show: false } }],
        bands: [{ series: [2, 1], fill: c + "22" }, { series: [4, 3], fill: c + "55" }] };
    } else if (spec.mode === "xy") {
      data = [null].concat(spec.signals.map(function (s) { var d = arr(s); return [Array.from(d[0]), Array.from(d[1], function (v) { return isFinite(v) ? v : null; })]; }));
      opts = { mode: 2, width: w, height: h, padding: [8, 12, 0, 4], legend: { show: false },
        cursor: { drag: { x: true, y: true, uni: 20, setScale: true }, points: { show: false } },
        scales: { x: { time: false, auto: true }, y: { auto: true } },
        axes: [Object.assign({}, axis, { size: 46, label: spec.xLabel, labelSize: 14, labelGap: 2 }), Object.assign({}, axis, { size: 56, values: ticks })],
        series: series };
    } else {
      // a log axis cannot reach far below 1e-15 (uPlot's tick search never ends): smaller values at a floor
      var top = 0;
      spec.signals.forEach(function (s) { arr(s)[1].forEach(function (v) { if (isFinite(v) && v > top) top = v; }); });
      var floor = Math.max(1e-15, top * 1e-12);
      var tables = spec.signals.map(function (s) { var d = arr(s); return [Array.from(d[0]), Array.from(d[1], function (v) { return !isFinite(v) ? null : !spec.log ? v : v > 0 ? Math.max(v, floor) : null; })]; });
      data = tables.length === 1 ? tables[0] : uPlot.join(tables, tables.map(function () { return [1]; }));
      opts = { width: w, height: h, padding: [8, 12, 0, 4], legend: { show: false },
        cursor: { y: false, drag: { x: true, y: false, setScale: true } },
        scales: { x: { time: false }, y: spec.log ? { distr: 3 } : { auto: true } },
        axes: [Object.assign({}, axis, { size: 46, label: spec.mode === "step" ? "s" : "Hz", labelSize: 14, labelGap: 2 }), Object.assign({}, axis, { size: 60, values: ticks })],
        series: series };
    }
    this.u = new uPlot(opts, data, this.canvas);
    var u = this.u;
    if (spec.mode === "time") {
      u.over.addEventListener("wheel", function (e) {
        e.preventDefault();
        var rc = u.over.getBoundingClientRect(), xv = u.posToVal(e.clientX - rc.left, "x"), f = e.deltaY < 0 ? 0.8 : 1.25;
        self.zoom(xv - (xv - u.scales.x.min) * f, xv + (u.scales.x.max - xv) * f);
      }, { passive: false });
      u.over.addEventListener("dblclick", function () { self.zoom(null, null); });
      var downX = 0;
      u.over.addEventListener("mousedown", function (e) { downX = e.clientX; });
      u.over.addEventListener("mouseup", function (e) {
        if (Math.abs(e.clientX - downX) > 3) return;
        var v = u.posToVal(e.clientX - u.over.getBoundingClientRect().left, "x");
        if (RP) { setTime(v, true); return; }                  // R1: every plot and map follows
        self.cursor = v;
        u.redraw(false); self.renderLegend();
      });
    } else {
      u.over.addEventListener("dblclick", function () { self.build(); });
    }
    this.renderLegend();
  };
  Plot.prototype.zoom = function (a, b, solo) {
    if (RP && RP.link !== false && !solo) { plots.forEach(function (p) { if (p.spec.mode === "time" && p.u) p.zoom(a, b, true); }); return; }   // R1: one zoom (a live report: each its own)
    var u = this.u;
    if (a === null) {
      u.setData(this.timeData(null, null), true);
    } else {
      u.setData(this.timeData(a, b), false);
      u.setScale("x", { min: a, max: b });
    }
  };
  Plot.prototype.renderLegend = function () {
    var self = this, spec = this.spec, html = "";
    spec.signals.forEach(function (s, k) {
      var val = "";
      if (spec.mode === "time" && self.cursor !== null) {
        var u = self.u, xs = u.data[0], ys = u.data[k + 1], X = [], Y = [];
        for (var i = 0; i < xs.length; i++) if (ys[i] !== null && ys[i] !== undefined) { X.push(xs[i]); Y.push(ys[i]); }
        val = fmt(interp(X, Y, self.cursor));
      } else if (spec.mode === "fft" && isFinite(s.peak)) val = fmt(s.peak, 4) + " Hz";
      html += '<button class="chip' + (self.hidden[k] ? " off" : "") + '" data-k="' + k + '" title="' + T.toggle + '">' +
        '<span class="sw" style="background:' + s.color + '"></span><span class="nm">' + s.label.replace(/</g, "&lt;") + "</span>" +
        (val ? '<span class="val">' + val + "</span>" : "") + "</button>";
    });
    this.legend.innerHTML = html;
    Array.prototype.forEach.call(this.legend.querySelectorAll(".chip"), function (b) {
      b.onclick = function () {
        var k = +b.getAttribute("data-k"); self.hidden[k] = !self.hidden[k];
        self.u.setSeries(k + 1, { show: !self.hidden[k] }); self.renderLegend();
      };
    });
  };

  /* ------------------------------------------------------------- page */
  var plots = [];
  function renderTab(i) {
    plots.forEach(function (p) { p.u && p.u.destroy(); });
    plots = [];
    Array.prototype.forEach.call(document.querySelectorAll(".tabbtn"), function (b, j) { b.setAttribute("aria-selected", String(i === j)); });
    Array.prototype.forEach.call(document.querySelectorAll(".tabpane"), function (p, j) { p.hidden = i !== j; });
    var pane = document.querySelectorAll(".tabpane")[i];
    Array.prototype.forEach.call(pane.querySelectorAll(".plot"), function (host) {
      var spec = R.tabs[i].plots[+host.getAttribute("data-p")];
      if (spec.mode === "spec" || spec.mode === "xyz" || spec.mode === "geo" || spec.mode === "3d") return;   // an image / the map's (or 3D view's) own page
      plots.push(new Plot(spec, host));
    });
  }
  var current = 0;
  Array.prototype.forEach.call(document.querySelectorAll(".tabbtn"), function (b, j) { b.onclick = function () { current = j; renderTab(j); }; });
  document.getElementById("theme").onclick = function () {
    root.setAttribute("data-theme", root.getAttribute("data-theme") === "dark" ? "light" : "dark");
    plots.forEach(function (p) { p.build(); });
  };
  var resizeTimer = 0;
  window.addEventListener("resize", function () {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(function () { plots.forEach(function (p) { p.u.setSize({ width: p.canvas.clientWidth, height: 340 }); }); }, 120);
  });
  window.addEventListener("beforeprint", function () { plots.forEach(function (p) { p.u.setSize({ width: 680, height: 300 }); }); });

  /* ------------------------------------------------------------- R1: the replay */
  var setTime = function () {};
  if (RP) (function () {
    // the recording's span: as the app gave it, else every time signal's first and last sample
    var lo = Infinity, hi = -Infinity;
    if (RP.extent) { lo = RP.extent[0]; hi = RP.extent[1]; }
    else R.tabs.forEach(function (tb) { tb.plots.forEach(function (sp) {
      if (sp.mode !== "time") return;
      sp.signals.forEach(function (s) { var x = arr(s.levels[0])[0]; if (x.length) { lo = Math.min(lo, x[0]); hi = Math.max(hi, x[x.length - 1]); } });
    }); });
    if (!(hi > lo)) { var bar0 = document.getElementById("rp"); if (bar0) bar0.hidden = true; return; }
    var span = hi - lo;
    var m = /[#&]t=(-?[\d.]+)/.exec(location.hash || "");      // a link to a later moment wins
    if (m && isFinite(+m[1])) RP.t = +m[1];
    if (RP.t === null || !isFinite(RP.t)) RP.t = lo;
    RP.t = Math.min(hi, Math.max(lo, RP.t));
    plots.forEach(function (p) { if (p.spec.mode === "time") { p.cursor = RP.t; p.u.redraw(false); p.renderLegend(); } });

    var track = document.getElementById("rp-track"), head = document.getElementById("rp-head"), fill = document.getElementById("rp-fill");
    var clock = document.getElementById("rp-clock"), playBtn = document.getElementById("rp-play"), speedSel = document.getElementById("rp-speed");
    var dec = span < 60 ? 2 : span < 3600 ? 1 : 0;
    var frac = function (v) { return Math.min(1, Math.max(0, (v - lo) / span)); };
    var frames = function () { return Array.prototype.slice.call(document.querySelectorAll("iframe.mapframe")); };
    var tell = function (f, extra) { try { f.contentWindow.postMessage(Object.assign({ sv: "replay", t: RP.t }, extra || {}), "*"); } catch (e) { /* not loaded yet */ } };
    frames().forEach(function (f) { f.addEventListener("load", function () { tell(f, { hideTime: true, dark: root.getAttribute("data-theme") === "dark" }); }); tell(f, { hideTime: true }); });
    var lastLegend = 0;
    setTime = function (v, settle) {
      RP.t = Math.min(hi, Math.max(lo, v));
      var now = performance.now(), legends = settle || now - lastLegend > 90;   // values: ~10 a second while playing
      if (legends) lastLegend = now;
      plots.forEach(function (p) {
        if (p.spec.mode !== "time" || !p.u) return;
        p.cursor = RP.t;
        var sx = p.u.scales.x;                                  // playing past the shown range: the window follows
        if (playing && sx && isFinite(sx.min) && (RP.t > sx.max || RP.t < sx.min) && (sx.max - sx.min) < span * 0.98) {
          var w = sx.max - sx.min, a = Math.max(lo, Math.min(hi - w, RP.t - w * 0.1));
          p.zoom(a, a + w, true);
        }
        p.u.redraw(false);
        if (legends) p.renderLegend();
      });
      frames().forEach(function (f) { tell(f); });
      head.style.left = frac(RP.t) * 100 + "%"; fill.style.width = frac(RP.t) * 100 + "%";
      clock.textContent = RP.t.toFixed(dec) + " s";
      track.setAttribute("aria-valuetext", clock.textContent);
      if (settle) { try { history.replaceState(null, "", "#t=" + RP.t.toFixed(3)); } catch (e) { /* a frame without history */ } }
    };
    // the marks: the log's errors and warnings, the health check's findings, the user's notes
    var marks = document.getElementById("rp-marks");
    RP.events.forEach(function (ev) {
      if (ev.t < lo || ev.t > hi) return;
      var i = document.createElement("i");
      i.className = ev.level; i.style.left = frac(ev.t) * 100 + "%"; i.title = ev.t.toFixed(dec) + " s · " + ev.text;
      i.addEventListener("pointerdown", function (e) { e.stopPropagation(); stop(); setTime(ev.t, true); });
      marks.appendChild(i);
    });
    var timeAt = function (x) { var b = track.getBoundingClientRect(); return lo + Math.min(1, Math.max(0, (x - b.left) / b.width)) * span; };
    track.addEventListener("pointerdown", function (e) {
      if (e.button !== 0) return;
      stop(); track.setPointerCapture(e.pointerId); setTime(timeAt(e.clientX));
      var move = function (ev) { setTime(timeAt(ev.clientX)); };
      var up = function (ev) { track.removeEventListener("pointermove", move); track.removeEventListener("pointerup", up); setTime(timeAt(ev.clientX), true); };
      track.addEventListener("pointermove", move); track.addEventListener("pointerup", up);
    });
    track.addEventListener("keydown", function (e) {
      if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
      e.preventDefault(); stop(); setTime(RP.t + (e.key === "ArrowRight" ? 1 : -1) * span / 200, true);
    });
    // play: the recording's own pace times the speed; at the end it stops
    var playing = false, raf = 0, last = 0;
    var tick = function (now) {
      var dt = (now - last) / 1000; last = now;
      var v = RP.t + dt * (+speedSel.value || 1);
      if (v >= hi) { setTime(hi, true); stop(); return; }
      setTime(v); raf = requestAnimationFrame(tick);
    };
    var label = function () { playBtn.innerHTML = playing ? "&#10074;&#10074;" : "&#9654;"; var l = playing ? T.rpPause : T.rpPlay; playBtn.title = l + " (Space)"; playBtn.setAttribute("aria-label", l); playBtn.setAttribute("aria-pressed", String(playing)); };
    function stop() { if (!playing) return; playing = false; cancelAnimationFrame(raf); label(); setTime(RP.t, true); }
    var play = function () { if (playing) { stop(); return; } if (RP.t >= hi) RP.t = lo; playing = true; label(); last = performance.now(); raf = requestAnimationFrame(tick); };
    playBtn.addEventListener("click", play);
    document.getElementById("rp-start").addEventListener("click", function () { stop(); setTime(lo, true); });
    // Space plays anywhere but in a field - also right after a click on the bar's own buttons (a focused
    // button would otherwise take Space as a click: "to the start" again instead of Play)
    var spaceIsPlay = function (e) {
      var tg = e.target && e.target.tagName, inBar = e.target && e.target.closest && e.target.closest("#rp");
      return e.key === " " && tg !== "SELECT" && tg !== "INPUT" && tg !== "TEXTAREA" && (tg !== "BUTTON" || inBar);
    };
    document.addEventListener("keydown", function (e) { if (spaceIsPlay(e)) { e.preventDefault(); if (!e.repeat) play(); } });
    document.addEventListener("keyup", function (e) { if (spaceIsPlay(e)) e.preventDefault(); });
    document.getElementById("theme").addEventListener("click", function () { frames().forEach(function (f) { tell(f, { dark: root.getAttribute("data-theme") === "dark" }); }); });
    // another tab's plots are new objects: they start on the page's time
    var shown = renderTab;
    renderTab = function (i) { shown(i); setTime(RP.t, true); };
    // a map's or a 3D view's page asks for a moment (its relation box: "Closest in")
    addEventListener("message", function (e) { var m = e.data; if (m && m.sv === "replay-seek" && isFinite(m.t)) { stop(); setTime(+m.t, true); } });
    window.__replay = { get t() { return RP.t; }, lo: lo, hi: hi, get playing() { return playing; } };   // for tests
    setTime(RP.t, true);
  })();
  renderTab(0);
  if (RP) setTime(RP.t, true);
})();
