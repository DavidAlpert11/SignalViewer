import { useEffect, useMemo, useRef, useState } from "react";
import { api, type RunOverview } from "../api";
import { actions, activeTab, fileLabel, rangeKey, useApp, type StripRow, type MenuItem } from "../store";
import { fmtNum, useT } from "../i18n";
import { getPrefValue, setPref } from "../prefs";
import { openMenu } from "./Overlays";
import { intersect, saveCondition, union } from "../conditions";
import { inkOn, stateColor } from "../values";

const PHASE_COLORS = ["#7F77DD", "#1D9E75", "#D85A30", "#378ADD", "#BA7517", "#888780", "#D4537E", "#639922"];
const hue = (label: string) => PHASE_COLORS[[...label].reduce((s, c) => (s * 31 + c.charCodeAt(0)) >>> 0, 7) % PHASE_COLORS.length];
export const SEL_COLOR = "#E5534B";
const keyOf = (r: StripRow) => (r.kind === "state" ? `s:${r.name}` : `c:${r.id}`);
type Seg = { a: number; b: number; label: string; v?: number };

/** Investigation step 7: the whole run at a glance - automatic flags, then one row per state signal
 *  or named condition (the user's; by default the run's phase signal), and where the plots are
 *  zoomed. A click picks a stretch (and every stretch with the same value); Ctrl+click adds one -
 *  "or" in the same row, "and" in another - and the selection can be saved as a condition. A
 *  double-click zooms to a stretch; a flag click goes to it. */
export default function OverviewStrip() {
  const t = useT();
  const lang = useApp((s) => s.lang);
  const runs = useApp((s) => s.runs);
  const ws = useApp((s) => s.ws);
  const ranges = useApp((s) => s.ranges);
  const dataVersion = useApp((s) => s.dataVersion);
  const condResults = useApp((s) => s.condResults);
  const sel = useApp((s) => s.stripSel);
  const theme = useApp((s) => s.theme);
  // the strip's time axis under the plots' own: its tracks start and end where the plotting area of
  // the first time plot does (when that plot is about as wide as the strip; else its own layout)
  const rowsRef = useRef<HTMLDivElement>(null);
  const [align, setAlign] = useState<{ lab: number; end: number } | null>(null);
  useEffect(() => {
    const measure = () => {
      const rows = rowsRef.current;
      const over = document.querySelector(".plot-canvas .u-over");
      if (!rows || !over) { setAlign((a) => (a ? null : a)); return; }
      const r = rows.getBoundingClientRect(), o = over.getBoundingClientRect();
      const lab = Math.round(o.left - r.left - 8), end = Math.round(r.right - o.right);
      const ok = o.width > r.width * 0.6 && lab >= 28 && end >= 0;
      setAlign((a) => (!ok ? (a ? null : a) : a && a.lab === lab && a.end === end ? a : { lab, end }));
    };
    measure();
    const id = window.setInterval(measure, 500);
    window.addEventListener("resize", measure);
    return () => { window.clearInterval(id); window.removeEventListener("resize", measure); };
  }, []);
  const [hidden, setHidden] = useState(!!getPrefValue<boolean>("overviewOff"));
  const files = runs.filter((r) => r.format !== "derived");
  const tab = activeTab(ws);
  const plot = tab.plots[tab.active];
  const fromPlot = plot?.signals.map((s) => s.sig.slice(0, s.sig.indexOf("/"))).find((rid) => files.some((f) => f.id === rid));
  const [chosen, setChosen] = useState<string | null>(null);
  const rid = (chosen && files.some((f) => f.id === chosen) ? chosen : null) ?? fromPlot ?? files[0]?.id;
  const run = files.find((f) => f.id === rid);
  const [ov, setOv] = useState<RunOverview | null>(null);
  const conds = ws.conditions ?? [];
  const rows: StripRow[] = ws.overviewRows ?? (ov?.phaseSignal ? [{ kind: "state", name: ov.phaseSignal }] : []);
  const stateNames = rows.filter((r): r is { kind: "state"; name: string } => r.kind === "state").map((r) => r.name);

  useEffect(() => {
    if (!rid || hidden) { setOv(null); return; }
    let gone = false;
    api.overview(rid, ws.overviewRows ? stateNames : []).then((r) => { if (!gone) setOv(r); }).catch(() => { if (!gone) setOv(null); });
    return () => { gone = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rid, dataVersion, hidden, stateNames.join("|")]);

  const segsOf = (r: StripRow): Seg[] => {
    if (r.kind === "cond") return (condResults[r.id]?.[rid ?? ""]?.intervals ?? []).map(([a, b]) => ({ a, b, label: "in" }));
    return ov?.rows?.[r.name] ?? (ov?.phaseSignal === r.name ? ov.phases : []);
  };
  // flags close together are one marker (the list on hover)
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

  // the selection's stretches: "or" within a row, "and" across rows
  const computeIv = (picks: Record<string, string[]>): [number, number][] => {
    let acc: [number, number][] | null = null;
    for (const r of rows) {
      const vals = picks[keyOf(r)];
      if (!vals?.length) continue;
      const iv = segsOf(r).filter((s) => vals.includes(s.label)).map((s) => [s.a, s.b] as [number, number])
        .reduce<[number, number][]>((u, x) => union(u, [x]), []);
      acc = acc === null ? iv : intersect(acc, iv);
    }
    return acc ?? [];
  };
  const pick = (r: StripRow, label: string, add: boolean) => {
    const k = keyOf(r);
    let picks: Record<string, string[]> = add && sel?.rid === rid ? { ...sel.picks } : {};
    const cur = picks[k] ?? [];
    picks[k] = add ? (cur.includes(label) ? cur.filter((x) => x !== label) : [...cur, label]) : [label];
    if (!picks[k].length) delete picks[k];
    if (!add && sel?.rid === rid && Object.keys(sel.picks).length === 1 && sel.picks[k]?.length === 1 && sel.picks[k][0] === label) picks = {};
    useApp.setState({ stripSel: Object.keys(picks).length ? { rid: rid!, picks, iv: computeIv(picks) } : null });
  };
  // a row's stretches changed (data, a condition edited): the selection follows
  useEffect(() => {
    if (sel && sel.rid === rid) useApp.setState({ stripSel: { ...sel, iv: computeIv(sel.picks) } });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ov, condResults]);
  useEffect(() => {
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape" && useApp.getState().stripSel) useApp.setState({ stripSel: null }); };
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, []);

  if (!files.length) return null;
  if (hidden) return <button className="ov-show linklike" onClick={() => { setPref("overviewOff", false); setHidden(false); }}>▸ {t("ovShow")}</button>;

  const setRows = (next: StripRow[]) => useApp.getState().commit((w) => { w.overviewRows = next; return w; });
  // what can be a row: the run's state signals (texts or a few whole numbers) and the named conditions
  const stateChoices = (run?.signals ?? []).filter((s) => s.labels || s.discrete).map((s) => s.name);
  const choices: { row: StripRow; label: string }[] = [
    ...stateChoices.map((n) => ({ row: { kind: "state", name: n } as StripRow, label: n })),
    ...conds.map((c) => ({ row: { kind: "cond", id: c.id } as StripRow, label: `⧉ ${c.name}` })),
  ].filter((c) => !rows.some((r) => keyOf(r) === keyOf(c.row)));
  const addMenu = (e: React.MouseEvent) => openMenu(e, choices.length ? choices.map((c) => ({ label: c.label, run: () => setRows([...rows, c.row]) }))
    : [{ label: t("ovNoChoice"), run: () => {}, disabled: true }]);
  const rowMenu = (e: React.MouseEvent, i: number) => {
    e.preventDefault();
    const items: MenuItem[] = [
      ...choices.map((c) => ({ label: t("ovReplace", { name: c.label }), run: () => setRows(rows.map((r, k) => (k === i ? c.row : r))) })),
      ...(choices.length ? [{ label: "", run: () => {}, sep: true }] : []),
      ...(i > 0 ? [{ label: t("ovUp"), run: () => { const n = [...rows]; [n[i - 1], n[i]] = [n[i], n[i - 1]]; setRows(n); } }] : []),
      ...(i < rows.length - 1 ? [{ label: t("ovDown"), run: () => { const n = [...rows]; [n[i + 1], n[i]] = [n[i], n[i + 1]]; setRows(n); } }] : []),
      { label: t("ovRemove"), run: () => setRows(rows.filter((_, k) => k !== i)) },
    ];
    openMenu(e, items);
  };
  const rowName = (r: StripRow) => (r.kind === "state" ? r.name : conds.find((c) => c.id === r.id)?.name ?? "?");

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
  const picked = (r: StripRow, label: string) => sel?.rid === rid && !!sel.picks[keyOf(r)]?.includes(label);
  const selText = sel && sel.rid === rid ? rows.filter((r) => sel.picks[keyOf(r)]?.length).map((r) => {
    const vals = sel.picks[keyOf(r)];
    return r.kind === "cond" ? rowName(r) : `${r.name} = ${vals.join(" ∨ ")}`;
  }).join(" ∧ ") : "";

  // the selection as a named condition: state rows as {Name} == "TEXT" (or the number), conditions
  // inlined when they are plain (no exit / length options), else combined with the rest
  const saveSel = () => {
    if (!sel) return;
    const parts: string[] = [];
    const combineWith: string[] = [];
    for (const r of rows) {
      const vals = sel.picks[keyOf(r)];
      if (!vals?.length) continue;
      if (r.kind === "state") {
        const sig = run?.signals.find((s) => s.name === r.name);
        const ref = /^[A-Za-z_][\w.]*$/.test(r.name) ? r.name : `{${r.name}}`;
        const one = (v: string) => (sig?.labels ? `${ref} == "${v}"` : `${ref} == ${v}`);
        parts.push(vals.length > 1 ? `(${vals.map(one).join(" or ")})` : one(vals[0]));
      } else {
        const c = conds.find((x) => x.id === r.id);
        if (c && !c.combine && !c.exit && !c.minDur && !c.mergeGap) parts.push(`(${c.text})`); else if (c) combineWith.push(c.id);
      }
    }
    const name = selText.length > 60 ? selText.slice(0, 57) + "…" : selText;
    if (!combineWith.length) { saveCondition({ name, text: parts.join(" and ") }); }
    else if (!parts.length && combineWith.length === 1) { /* already a condition */ }
    else {
      // the plain part as its own condition, then all of them combined ("and")
      if (parts.length) saveCondition({ name: `${name} (1)`, text: parts.join(" and ") });
      const st = useApp.getState();
      const plainId = parts.length ? st.ws.conditions?.[st.ws.conditions.length - 1]?.id : undefined;
      saveCondition({ name, text: "", combine: { op: "and", ids: [...(plainId ? [plainId] : []), ...combineWith] } });
    }
    useApp.setState({ stripSel: null, panel: "investigate" });
  };

  return (
    <div className="ov-strip" role="region" aria-label={t("ovTitle")}>
      <div className="ov-head">
        {files.length > 1 ? (
          <select className="ov-file" value={rid} onChange={(e) => { setChosen(e.target.value); useApp.setState({ stripSel: null }); }} aria-label={t("ovFile")}>
            {files.map((f) => <option key={f.id} value={f.id}>{fileLabel(runs, f.id)}</option>)}
          </select>
        ) : <span className="ov-name">{fileLabel(runs, rid!)}</span>}
        {ov && <span className="muted">{t("ovSummary2", { d: fmtNum(ov.end - ov.start, lang, 4), f: ov.flags.length })}
          {ov.partial ? ` ${t("ovPartial", { n: ov.scanned })}` : ""}</span>}
        <span className="ov-hint muted">{t("ovPickHint")}</span>
        <button className="iconbtn sm ov-add" aria-label={t("ovAdd")} title={t("ovAdd")} onClick={addMenu}>+</button>
        <button className="iconbtn sm ov-hide" aria-label={t("ovHide")} title={t("ovHide")} onClick={() => { setPref("overviewOff", true); setHidden(true); }}>×</button>
      </div>
      <div className="ov-rows" ref={rowsRef}
        style={align ? { gridTemplateColumns: `${align.lab}px 1fr`, paddingRight: align.end } : undefined}>
        <span className="ov-label muted">{t("ovFlags")}</span>
        <div className="ov-track ov-flags">
          {view && ov && <div className="ov-view" style={{ left: pct(view[0]), width: width(view[0], view[1]) }} title={t("ovView")} />}
          {clusters.map((c, i) => (
            <button key={i} className={`ov-flag${c.items.some((f) => bad(f.kind)) ? " bad" : ""}`} style={{ left: pct(c.a) }}
              title={c.items.map(flagText).join("\n")} aria-label={c.items.map(flagText).join("; ")} onClick={() => go(c.a, c.b)}>
              {c.items.length > 1 ? c.items.length : ""}
            </button>
          ))}
        </div>
        {rows.map((r, i) => {
          const cond = r.kind === "cond" ? conds.find((c) => c.id === r.id) : undefined;
          return [
            <button key={`l${i}`} className="ov-label linklike" dir="auto" title={`${rowName(r)} · ${t("ovRowMenu")}`} onContextMenu={(e) => rowMenu(e, i)} onClick={(e) => rowMenu(e, i)}>
              {r.kind === "cond" ? "⧉ " : ""}{rowName(r)}</button>,
            <div key={`t${i}`} className="ov-track ov-row" data-row={keyOf(r)}>
              {ov && segsOf(r).map((p, k) => {
                // the same colour as the state's lane on the plots (by its code)
                const bg = cond?.color ?? (p.v !== undefined ? stateColor(p.v, theme) : hue(p.label));
                const rowPicked = sel?.rid === rid && !!sel.picks[keyOf(r)]?.length;
                return (
                  <button key={k} className={`ov-phase${picked(r, p.label) ? " picked" : rowPicked ? " dim" : ""}`}
                    style={{ left: pct(p.a), width: width(p.a, p.b), background: bg, color: inkOn(bg) }}
                    title={`${rowName(r)}${r.kind === "state" ? `: ${p.label}` : ""} · ${fmtNum(p.a, lang, 5)} – ${fmtNum(p.b, lang, 5)} s`}
                    onClick={(e) => pick(r, p.label, e.ctrlKey || e.metaKey || e.shiftKey)} onDoubleClick={() => go(p.a, p.b)}>
                    <span>{r.kind === "state" ? p.label : ""}</span>
                  </button>
                );
              })}
            </div>,
          ];
        })}
        {sel && sel.rid === rid && <>
          <span className="ov-label ov-sel-label">{t("ovSelection")}</span>
          <div className="ov-track ov-sel">
            {sel.iv.map(([a, b], k) => (
              <button key={k} className="ov-phase picked" style={{ left: pct(a), width: width(a, b), background: SEL_COLOR }}
                title={`${fmtNum(a, lang, 5)} – ${fmtNum(b, lang, 5)} s`} onClick={() => go(a, b)} />
            ))}
          </div>
        </>}
      </div>
      {sel && sel.rid === rid && (
        <div className="ov-selbar">
          <span className="ov-seltext">{selText} · {t(sel.iv.length === 1 ? "condCountOne" : "condCount", { n: sel.iv.length })}</span>
          <button className="btn outline sm ov-save" disabled={!sel.iv.length} onClick={saveSel}>{t("ovSave")}</button>
          <button className="iconbtn sm" aria-label={t("close")} onClick={() => useApp.setState({ stripSel: null })}>×</button>
        </div>
      )}
    </div>
  );
}
