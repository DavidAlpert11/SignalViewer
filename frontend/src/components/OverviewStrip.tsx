import { useEffect, useMemo, useState } from "react";
import { api, type RunOverview } from "../api";
import { actions, activeTab, fileLabel, rangeKey, useApp } from "../store";
import { fmtNum, useT } from "../i18n";
import { getPrefValue, setPref } from "../prefs";

const PHASE_COLORS = ["#7F77DD", "#1D9E75", "#D85A30", "#378ADD", "#BA7517", "#888780", "#D4537E", "#639922"];
const hue = (label: string) => PHASE_COLORS[[...label].reduce((s, c) => (s * 31 + c.charCodeAt(0)) >>> 0, 7) % PHASE_COLORS.length];

/** Investigation step 7: above the plots, the whole run at a glance - its phases (the mode / phase
 *  signal), automatic flags (stuck or saturated signals, gaps, spikes: places worth a look, not
 *  faults) and where the plots are zoomed. A click on a flag or a phase goes there. */
export default function OverviewStrip() {
  const t = useT();
  const lang = useApp((s) => s.lang);
  const runs = useApp((s) => s.runs);
  const ws = useApp((s) => s.ws);
  const ranges = useApp((s) => s.ranges);
  const dataVersion = useApp((s) => s.dataVersion);
  const [hidden, setHidden] = useState(!!getPrefValue<boolean>("overviewOff"));
  const files = runs.filter((r) => r.format !== "derived");
  const tab = activeTab(ws);
  const plot = tab.plots[tab.active];
  const fromPlot = plot?.signals.map((s) => s.sig.slice(0, s.sig.indexOf("/"))).find((rid) => files.some((f) => f.id === rid));
  const [chosen, setChosen] = useState<string | null>(null);
  const rid = (chosen && files.some((f) => f.id === chosen) ? chosen : null) ?? fromPlot ?? files[0]?.id;
  const [ov, setOv] = useState<RunOverview | null>(null);

  useEffect(() => {
    if (!rid || hidden) { setOv(null); return; }
    let gone = false;
    api.overview(rid).then((r) => { if (!gone) setOv(r); }).catch(() => { if (!gone) setOv(null); });
    return () => { gone = true; };
  }, [rid, dataVersion, hidden]);

  // flags close together on the strip are one marker (the list on hover)
  const clusters = useMemo(() => {
    if (!ov) return [];
    const span = Math.max(ov.end - ov.start, 1e-9);
    const out: { a: number; b: number; items: RunOverview["flags"] }[] = [];
    for (const f of ov.flags) {
      const last = out[out.length - 1];
      if (last && f.a - last.a < span * 0.006) { last.items.push(f); last.b = Math.max(last.b, f.b); }
      else out.push({ a: f.a, b: f.b, items: [f] });
    }
    return out;
  }, [ov]);

  if (!files.length) return null;
  if (hidden) {
    return <button className="ov-show linklike" onClick={() => { setPref("overviewOff", false); setHidden(false); }}>▸ {t("ovShow")}</button>;
  }
  const span = ov ? Math.max(ov.end - ov.start, 1e-9) : 1;
  const pct = (x: number) => `${Math.max(0, Math.min(100, ((x - (ov?.start ?? 0)) / span) * 100))}%`;
  const width = (a: number, b: number) => `${Math.max(0.2, ((Math.min(b, ov!.end) - Math.max(a, ov!.start)) / span) * 100)}%`;
  const view = plot ? ranges[rangeKey(tab, plot)] : null;
  const flagText = (f: RunOverview["flags"][0]) => t(`ovFlag_${f.kind}` as "ovFlag_stuck", { signal: f.signal, a: fmtNum(f.a, lang, 5),
    b: fmtNum(f.b, lang, 5), s: fmtNum(f.b - f.a, lang, 3), v: f.value !== undefined ? fmtNum(f.value, lang, 5) : "" });
  const go = (a: number, b: number) => {
    const pad = Math.max((b - a) * 0.5, 1);
    actions.showSpan(a - pad, b + pad);
    useApp.setState({ cursor: { ...useApp.getState().cursor, on: true, dual: b > a, t1: a, t2: b > a ? b : null, active: 1 } });
  };
  const bad = (k: string) => k === "saturated" || k === "gap";
  return (
    <div className="ov-strip" role="region" aria-label={t("ovTitle")}>
      <div className="ov-summary">
        {files.length > 1 ? (
          <select className="ov-file" value={rid} onChange={(e) => setChosen(e.target.value)} aria-label={t("ovFile")}>
            {files.map((f) => <option key={f.id} value={f.id}>{fileLabel(runs, f.id)}</option>)}
          </select>
        ) : <span className="ov-name">{fileLabel(runs, rid!)}</span>}
        {ov && <span className="muted">{t("ovSummary", { d: fmtNum(ov.end - ov.start, lang, 4), p: ov.phases.length, f: ov.flags.length })}
          {ov.partial ? ` ${t("ovPartial", { n: ov.scanned })}` : ""}</span>}
      </div>
      <div className="ov-track">
        {ov?.phases.map((p, i) => (
          <button key={i} className="ov-phase" style={{ left: pct(p.a), width: width(p.a, p.b), background: hue(p.label) }}
            title={`${ov.phaseSignal}: ${p.label} · ${fmtNum(p.a, lang, 5)} – ${fmtNum(p.b, lang, 5)} s`} onClick={() => go(p.a, p.b)}>
            <span>{p.label}</span>
          </button>
        ))}
        {view && ov && <div className="ov-view" style={{ left: pct(view[0]), width: width(view[0], view[1]) }} aria-hidden="true" />}
        {clusters.map((c, i) => (
          <button key={i} className={`ov-flag${c.items.some((f) => bad(f.kind)) ? " bad" : ""}`} style={{ left: pct(c.a) }}
            title={c.items.map(flagText).join("\n")} aria-label={c.items.map(flagText).join("; ")} onClick={() => go(c.a, c.b)}>
            {c.items.length > 1 ? c.items.length : ""}
          </button>
        ))}
      </div>
      <button className="iconbtn sm ov-hide" aria-label={t("ovHide")} title={t("ovHide")} onClick={() => { setPref("overviewOff", true); setHidden(true); }}>×</button>
    </div>
  );
}
