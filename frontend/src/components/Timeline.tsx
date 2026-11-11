import { countRender } from "../perf";
import { useEffect, useMemo, useRef, useState } from "react";
import { actions, activeTab, rangeKey, recordingExtent, useApp, type PlayMode } from "../store";
import { api } from "../api";
import { envelopePath, panSpan, pullEdge, shownWindow, type Span } from "../timelineView";
import { fmtNum, useT } from "../i18n";
import { Icon } from "../icons";
import { FindingsDock } from "./StartCard";
import { findingText, plotFinding } from "./HealthRow";
import { openMenu } from "./Overlays";

/* The timeline: one bar under the plots for the whole recording. Its handle IS the cursor - moving
   one moves the other - so the time plots, X-Y plots, maps (and later the 3D view) all follow the
   same time. Below the track: when each open file has data, and its log events / the user's notes
   as marks to jump to. */

const SPEEDS = [0.25, 0.5, 1, 2, 5, 10, 30, 60];

/** Elapsed time as a clock: s.ss under a minute, m:ss.s under an hour, else h:mm:ss. */
function fmtClock(sec: number, span: number): string {
  const neg = sec < 0 ? "-" : "";
  const a = Math.abs(sec);
  if (span < 60) return `${neg}${a.toFixed(2)}`;
  const h = Math.floor(a / 3600), m = Math.floor((a % 3600) / 60), s = a % 60;
  if (span < 3600) return `${neg}${m}:${s.toFixed(1).padStart(4, "0")}`;
  return `${neg}${h}:${String(m).padStart(2, "0")}:${String(Math.floor(s)).padStart(2, "0")}`;
}

/** F28: seconds as recorded - the same number as the axes, the cursor and the Inspector. */
function fmtSec(v: number, span: number, lang: string): string {
  const d = span < 60 ? 2 : span < 3600 ? 1 : 0;
  return v.toLocaleString(lang === "he" ? "he-IL" : "en-US", { minimumFractionDigits: d, maximumFractionDigits: d, useGrouping: false });
}

export default function Timeline() {
  countRender("Timeline");
  const t = useT();
  const lang = useApp((s) => s.lang);
  const timeFormat = useApp((s) => s.timeFormat);
  const runs = useApp((s) => s.runs);
  const cursor = useApp((s) => s.cursor);
  const playing = useApp((s) => s.playing);
  const playMode = useApp((s) => s.playMode);
  const speed = useApp((s) => s.playSpeed);
  const windowSec = useApp((s) => s.windowSec);
  const open = useApp((s) => s.timelineOpen);
  const logs = useApp((s) => s.logs);
  const notes = useApp((s) => s.ws.notes);
  const trackRef = useRef<HTMLDivElement>(null);
  const raf = useRef(0);
  const ext = useMemo(() => recordingExtent(runs), [runs]);
  const data = useMemo(() => runs.filter((r) => r.format !== "derived" && r.end > r.start), [runs]);

  // marks along the track: errors / warnings of flight logs, and the user's notes
  // U2: the health check's findings, each a mark that plots its signals (as its "Plot" link)
  const findingMarks = useApp((s) => s.findingMarks);
  const fmarks = useMemo(() => data.flatMap((r) => (findingMarks[r.id] ?? []).map((f) => ({ f, runId: r.id,
    t: (f.t ?? f.spans[0]?.[0] ?? 0) + (logs[r.id]?.timeOffset || 0) }))), [data, findingMarks, logs]);
  const fclusters = useMemo(() => {
    const out: (typeof fmarks)[] = [];
    const sorted = [...fmarks].sort((a, b) => a.t - b.t);
    const gap = ext ? (ext[1] - ext[0]) * 0.015 : 0;           // closer than a mark's width on a usual timeline
    for (const m of sorted) {
      const last = out[out.length - 1];
      if (last && m.t - last[last.length - 1].t <= gap) last.push(m); else out.push([m]);
    }
    return out;
  }, [fmarks, ext]);
  const marks = useMemo(() => {
    const out: { t: number; text: string; level: string }[] = [];
    for (const r of data) {
      const L = logs[r.id];
      if (!L) continue;
      for (const e of L.events) {
        if (e.kind === "mode" || e.level === "info") continue;
        out.push({ t: e.t + (L.timeOffset || 0), text: e.text, level: e.level });
      }
    }
    for (const n of notes ?? []) out.push({ t: n.t, text: n.text, level: "note" });
    return out;
  }, [data, logs, notes]);

  // R3: the active plot's first line, faint behind the track (its shape over the whole recording), and
  // what the plots show as a window on the track - dragged to move along, its edges pulled to zoom
  const tab = useApp((s) => activeTab(s.ws));
  const dataVersion = useApp((s) => s.dataVersion);
  const vplot = useMemo(() => {
    const time = (p: (typeof tab.plots)[number]) => (p.mode ?? "time") === "time" && p.signals.some((x) => !x.state);
    return (tab.plots[tab.active] && time(tab.plots[tab.active])) ? tab.plots[tab.active] : tab.plots.find(time) ?? null;
  }, [tab]);
  const vsig = vplot?.signals.find((x) => !x.state) ?? null;
  const vkey = vplot ? rangeKey(tab, vplot) : null;
  const vrange = useApp((s) => (vkey ? s.ranges[vkey] ?? null : null));
  const [env, setEnv] = useState<{ d: string; color: string } | null>(null);
  const envKey = open && vsig && ext ? `${vsig.sig}|${vsig.tOffset ?? 0}|${ext[0]}|${ext[1]}|${dataVersion}` : "";
  useEffect(() => {
    if (!envKey || !vsig || !ext) { setEnv(null); return; }
    let gone = false;
    const off = vsig.tOffset ?? 0;
    api.data([vsig.sig], null, null, 500).then(([sr]) => {
      if (gone || !sr || sr.missing) return;
      const x = Float64Array.from(sr.x, (v) => v + off);
      setEnv({ d: envelopePath(x, sr.y, ext[0], ext[1]), color: vsig.color });
    }).catch(() => { if (!gone) setEnv(null); });
    return () => { gone = true; };
  }, [envKey]);          // eslint-disable-line react-hooks/exhaustive-deps

  if (!ext) return null;
  const [t0, t1] = ext;
  const span = t1 - t0;
  const frac = (v: number) => Math.min(1, Math.max(0, (v - t0) / span));
  const now = cursor.on && cursor.t1 !== null ? cursor.t1 : null;
  // F28: one way of writing a moment - seconds as recorded (default), or a clock from the start (Settings)
  const clock = (v: number) => (timeFormat === "clock" ? fmtClock(v - t0, span) : fmtSec(v, span, lang));

  /* dragging on the track: the time follows the pointer, at most once per frame */
  const timeAt = (clientX: number) => {
    const r = trackRef.current!.getBoundingClientRect();
    return t0 + Math.min(1, Math.max(0, (clientX - r.left) / r.width)) * span;
  };
  const onDown = (e: React.PointerEvent) => {
    if (e.button !== 0) return;
    e.preventDefault();
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
    if (useApp.getState().playing) useApp.setState({ playing: false });
    actions.setTime(timeAt(e.clientX));
    let x = e.clientX;
    const move = (ev: PointerEvent) => {
      x = ev.clientX;
      if (raf.current) return;
      raf.current = requestAnimationFrame(() => { raf.current = 0; actions.setTime(timeAt(x)); });
    };
    const up = () => {
      window.removeEventListener("pointermove", move); window.removeEventListener("pointerup", up);
      if (raf.current) { cancelAnimationFrame(raf.current); raf.current = 0; }
      const tt = timeAt(x);
      actions.setTime(tt); actions.followTime(tt);
    };
    window.addEventListener("pointermove", move); window.addEventListener("pointerup", up);
  };
  const onKey = (e: React.KeyboardEvent) => {
    const step = span / 100;
    if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
      e.preventDefault(); e.stopPropagation();
      const tt = Math.min(t1, Math.max(t0, (now ?? t0) + (e.key === "ArrowRight" ? step : -step)));
      actions.setTime(tt); actions.followTime(tt);
    }
  };
  const jump = (v: number) => { actions.setTime(v); actions.followTime(v); };
  const win = shownWindow(vrange, ext);
  /* the window: drag its body to move what the plots show, an edge to zoom; one Backspace undoes it */
  const onWin = (e: React.PointerEvent, part: "body" | 0 | 1) => {
    if (e.button !== 0 || !win || !vkey) return;
    e.preventDefault(); e.stopPropagation();
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
    const start: Span = win, x0 = e.clientX, w = trackRef.current!.getBoundingClientRect().width;
    let moved = false;
    const move = (ev: PointerEvent) => {
      const dt = ((ev.clientX - x0) / w) * span;
      if (!moved && Math.abs(ev.clientX - x0) < 2) return;
      if (!moved) { actions.pushZoomStep(vkey, { x: start }); moved = true; }
      const r = part === "body" ? panSpan(start, dt, ext) : pullEdge(start, part, timeAt(ev.clientX), ext, span / 2000);
      actions.setRange(vkey, r, { history: false });
    };
    const up = () => { window.removeEventListener("pointermove", move); window.removeEventListener("pointerup", up); };
    window.addEventListener("pointermove", move); window.addEventListener("pointerup", up);
  };

  const track = (
    <div className="tl-track" ref={trackRef} dir="ltr" role="slider" tabIndex={0} aria-label={t("timeline")}
      aria-valuemin={0} aria-valuemax={Math.round(span * 1000) / 1000} aria-valuenow={now === null ? 0 : Math.round((now - t0) * 1000) / 1000}
      aria-valuetext={now === null ? t("tlHint") : clock(now)}
      title={t("tlHint")} onPointerDown={onDown} onKeyDown={onKey}>
      {open && env?.d && (
        <svg className="tl-env" viewBox="0 0 1000 100" preserveAspectRatio="none" aria-hidden="true">
          <path d={env.d} style={{ stroke: env.color }} vectorEffect="non-scaling-stroke" />
        </svg>)}
      <div className="tl-rail" />
      {now !== null && playMode === "draw" && <div className="tl-shown" style={{ left: 0, width: `${frac(now) * 100}%` }} />}
      {now !== null && playMode === "window" && (
        <div className="tl-shown" style={{ left: `${frac(now - windowSec) * 100}%`, width: `${(frac(now) - frac(now - windowSec)) * 100}%` }} />)}
      {cursor.on && cursor.dual && cursor.t2 !== null && <div className="tl-mark2" style={{ left: `${frac(cursor.t2) * 100}%` }} />}
      {open && win && (
        <div className="tl-view" style={{ left: `${frac(win[0]) * 100}%`, width: `${(frac(win[1]) - frac(win[0])) * 100}%` }}
          title={t("tlViewHint")} onPointerDown={(e) => onWin(e, "body")}
          onDoubleClick={(e) => { e.stopPropagation(); if (vkey) actions.setRange(vkey, null); }}>
          <span className="tl-edge a" onPointerDown={(e) => onWin(e, 0)} />
          <span className="tl-edge b" onPointerDown={(e) => onWin(e, 1)} />
        </div>)}
      {now !== null && <div className="tl-handle" style={{ left: `${frac(now) * 100}%` }} />}
    </div>
  );

  if (!open) {
    return (
      <div className="timeline slim">
        <FindingsDock />
        {track}
        <button className="iconbtn sm" onClick={() => useApp.setState({ timelineOpen: true })} title={t("tlExpand")} aria-label={t("tlExpand")}>
          <Icon.Chevron style={{ transform: "rotate(180deg)" }} />
        </button>
      </div>
    );
  }

  return (
    <div className="timeline" role="group" aria-label={t("timeline")}>
      <FindingsDock />
      <div className="tl-controls">
        <button className="iconbtn" onClick={() => jump(t0)} title={`${t("tlStart")} (Home)`} aria-label={t("tlStart")}>
          <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><rect x="5" y="5" width="2.5" height="14" rx="1" /><path d="M19 5L9 12l10 7z" /></svg>
        </button>
        <button className="iconbtn tl-play" aria-pressed={playing} onClick={() => actions.togglePlay()}
          title={`${playing ? t("pause") : t("play")} (P)`} aria-label={playing ? t("pause") : t("play")}>
          {playing ? <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><rect x="6" y="5" width="4" height="14" rx="1" /><rect x="14" y="5" width="4" height="14" rx="1" /></svg>
            : <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M7 5l12 7-12 7z" /></svg>}
        </button>
      </div>
      <div className="tl-body">
        {track}
        {/* one thin row per file (when it has data), the event marks over them */}
        <div className="tl-lanes" dir="ltr" style={{ height: 4 + Math.min(4, data.length) * 4 }}>
          {data.slice(0, 4).map((r, k) => (
            <div key={r.id} className="tl-cover" title={r.name}
              style={{ top: 2 + k * 4, left: `${frac(r.start) * 100}%`, width: `${Math.max(0.3, (frac(r.end) - frac(r.start)) * 100)}%` }} />
          ))}
          {marks.map((m, i) => (
            <button key={i} className={`tl-event ${m.level}`} style={{ left: `${frac(m.t) * 100}%` }}
              title={`${clock(m.t)} · ${m.text}`} aria-label={m.text} onClick={() => jump(m.t)} />
          ))}
          {fclusters.map((c, i) => {
            const texts = c.map((m) => findingText(t, m.f));
            const plot = (m: typeof c[number]) => plotFinding(m.f, m.runId, t(`hTitle_${m.f.code}` as "hTitle_vibration"));
            return (
              <button key={`f${i}`} className={`tl-finding ${c.some((m) => m.f.level === "error") ? "error" : "warning"}`}
                style={{ left: `${frac(c[0].t) * 100}%` }} aria-label={texts.join("; ")}
                title={`${c.map((m, k) => `${clock(m.t)} · ${texts[k]}`).join("\n")}\n${t("findingMarkHint")}`}
                // findings close together are one mark: a click lists them (each plots its signals)
                onClick={(e) => (c.length === 1 ? plot(c[0]) : openMenu(e, c.map((m, k) => ({ label: texts[k], run: () => plot(m) }))))} />
            );
          })}
        </div>
      </div>
      <span className="tl-clock" title={now === null ? "" : fmtNum(now, lang, 9)}>
        {now === null ? "–" : clock(now)} <span className="hint">/ {timeFormat === "clock" ? fmtClock(span, span) : clock(t0 + span)}</span>
      </span>
      <select className="mini-select" dir="ltr" value={speed} onChange={(e) => useApp.setState({ playSpeed: Number(e.target.value) })}
        aria-label={t("tlSpeed")} title={t("tlSpeed")}>
        {(SPEEDS.includes(speed) ? SPEEDS : [...SPEEDS, speed].sort((a, b) => a - b)).map((v) => <option key={v} value={v}>×{v}</option>)}
      </select>
      <select className="mini-select" value={playMode} onChange={(e) => useApp.setState({ playMode: e.target.value as PlayMode })}
        aria-label={t("tlMode")} title={t("tlMode")}>
        <option value="cursor">{t("tlModeAll")}</option>
        <option value="draw">{t("tlModeDraw")}</option>
        <option value="window">{t("tlModeWindow")}</option>
      </select>
      {playMode === "window" && (
        <label className="tl-window" title={t("tlWindow")}>
          <input type="number" min={0.1} step="any" value={windowSec} aria-label={t("tlWindow")}
            onChange={(e) => { const v = Number(e.target.value); if (v > 0) useApp.setState({ windowSec: v }); }} />
          <span className="hint">{t("tlSeconds")}</span>
        </label>
      )}
      <button className="iconbtn sm" onClick={() => useApp.setState({ timelineOpen: false })} title={t("tlCollapse")} aria-label={t("tlCollapse")}>
        <Icon.Chevron />
      </button>
    </div>
  );
}
