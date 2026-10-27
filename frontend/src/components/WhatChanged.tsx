import { useEffect, useMemo, useState } from "react";
import { api, type FirstChange, type LagResult } from "../api";
import { actions, activeTab, signalName, uid, useApp, type Plot, type Tab } from "../store";
import { fmtNum, useT } from "../i18n";
import { Icon } from "../icons";

/** Investigation step 4: around the selected span, which signals left their usual range first -
 *  ranked CANDIDATES with a small picture each, grouped when the sample rates cannot tell them apart,
 *  a warning that earlier is not cause, and the lag between two of them. */
export default function WhatChanged() {
  const t = useT();
  const lang = useApp((s) => s.lang);
  const runs = useApp((s) => s.runs);
  const span = useApp((s) => s.whatChanged)!;
  const ws = useApp((s) => s.ws);
  const [scope, setScope] = useState<"tab" | "all">("tab");
  const [items, setItems] = useState<FirstChange[] | null>(null);
  const [base, setBase] = useState<[number, number] | null>(null);
  const [err, setErr] = useState("");
  const [picked, setPicked] = useState<string[]>([]);
  const [showSame, setShowSame] = useState(false);
  const [lag, setLag] = useState<(LagResult & { a: string; b: string }) | null>(null);

  const tabSigs = useMemo(() => {
    const tb = activeTab(ws);
    return [...new Set(tb.plots.filter((p) => (p.mode ?? "time") === "time").flatMap((p) => p.signals.map((s) => s.sig)))]
      .filter((id) => !id.startsWith("derived/") || runs.some((r) => r.signals.some((s) => s.id === id)));
  }, [ws, runs]);
  const files = useMemo(() => [...new Set(tabSigs.map((id) => id.slice(0, id.indexOf("/"))).filter((r) => r !== "derived"))], [tabSigs]);
  const allFiles = files.length ? files : runs.filter((r) => r.format !== "derived").map((r) => r.id);
  const total = runs.filter((r) => allFiles.includes(r.id)).reduce((s, r) => s + r.signals.length, 0);

  useEffect(() => {
    let gone = false;
    setItems(null); setErr(""); setPicked([]); setLag(null);
    api.firstChange(span.a, span.b, scope === "tab" ? tabSigs : [], scope === "all" ? allFiles : [])
      .then((r) => {
        if (gone) return;
        setItems(r.items); setBase(r.base);
        useApp.setState({ changeMarks: Object.fromEntries(r.items.filter((x) => x.status === "changed").map((x) => [x.id, x.t!])) });
      })
      .catch((e) => { if (!gone) setErr(String((e as Error).message)); });
    return () => { gone = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [span.a, span.b, scope]);
  useEffect(() => () => useApp.setState({ changeMarks: null }), []);      // the dashed lines go with the section

  const close = () => useApp.setState({ whatChanged: null, changeMarks: null });
  const changed = (items ?? []).filter((x) => x.status === "changed");
  const same = (items ?? []).filter((x) => x.status === "same");
  const nodata = (items ?? []).filter((x) => x.status === "nodata");
  // rows that the sample rates cannot order: "together", not one before the other
  const groups: FirstChange[][] = [];
  for (const x of changed) {
    const last = groups[groups.length - 1];
    const prev = last?.[last.length - 1];
    const res = prev ? Math.max(1 / (prev.rate || 1e9), 1 / (x.rate || 1e9)) : 0;
    if (prev && x.t! - prev.t! <= res) last.push(x); else groups.push([x]);
  }
  const rates = changed.map((x) => x.rate ?? 0).filter((r) => r > 0);
  const coarse = rates.length ? 1 / Math.min(...rates) : 0;
  const togglePick = (id: string) => setPicked((p) => (p.includes(id) ? p.filter((x) => x !== id) : [...p, id].slice(-6)));
  const stacked = () => {
    const ids = picked.length ? picked : changed.slice(0, 4).map((x) => x.id);
    if (!ids.length) return;
    useApp.getState().commit((w) => {
      const plots: Plot[] = ids.map((id, i) => ({ id: uid("p"), title: signalName(runs, id), signals: [{ sig: id, color: ["#3D8BFD", "#E8590C", "#2F9E44", "#AE3EC9", "#F08C00", "#0CA678"][i % 6], width: 1.5, scale: 1, offset: 0 }] }));
      const tab: Tab = { id: uid("t"), name: t("wcTabName"), rows: plots.length, cols: 1, plots, active: 0, linkX: true };
      w.tabs.push(tab); w.activeTab = tab.id;
      return w;
    });
    const L = span.b - span.a;
    actions.showSpan(span.a - L, span.b + L / 2);
  };
  const runLag = async () => {
    if (picked.length !== 2) return;
    const [a, b] = [...picked].sort((p, q) => (items!.find((x) => x.id === p)?.t ?? 0) - (items!.find((x) => x.id === q)?.t ?? 0));
    const L = span.b - span.a;
    try { setLag({ ...(await api.lag(a, b, span.a - 2 * L, span.b + 2 * L)), a, b }); }
    catch (e) { setErr(String((e as Error).message)); }
  };
  const showAligned = () => {
    if (!lag || lag.status !== "ok") return;
    const tb = activeTab(useApp.getState().ws);
    const p = tb.plots[tb.active];
    if (!p) return;
    useApp.getState().commit((w) => {
      const plot = w.tabs.find((x) => x.id === tb.id)?.plots.find((x) => x.id === p.id);
      if (!plot) return w;
      const own = plot.signals.find((s) => s.sig === lag.b);
      if (own) own.tOffset = -lag.lag!;
      else plot.signals.push({ sig: lag.b, color: "#888888", width: 1.5, scale: 1, offset: 0, tOffset: -lag.lag! });
      if (!plot.signals.some((s) => s.sig === lag.a)) plot.signals.push({ sig: lag.a, color: "#3D8BFD", width: 1.5, scale: 1, offset: 0 });
      return w;
    });
  };

  return (
    <section className="wc-section">
      <div className="wc-head">
        <h3>{t("wcTitle")}</h3>
        <button className="iconbtn" aria-label={t("close")} onClick={close}><Icon.X /></button>
      </div>
      <p className="hint">{t("wcSpan", { a: fmtNum(span.a, lang, 6), b: fmtNum(span.b, lang, 6) })}
        {base ? ` ${t("wcBase", { a: fmtNum(base[0], lang, 6), b: fmtNum(base[1], lang, 6) })}` : ""}</p>
      <select className="wc-scope" value={scope} onChange={(e) => setScope(e.target.value as "tab" | "all")} aria-label={t("wcScope")}>
        <option value="tab">{t("wcScopeTab", { n: tabSigs.length })}</option>
        <option value="all">{t("wcScopeAll", { n: total })}</option>
      </select>
      {err && <p className="hint err">{err}</p>}
      {!items && !err && <p className="hint">{t("loading")}</p>}
      {items && (
        <>
          <p className="wc-warn">{t("wcNotCause")}{coarse > 0.02 ? ` ${t("wcResolution", { ms: fmtNum(coarse * 1000, lang, 3) })}` : ""}</p>
          {!changed.length && <p className="hint">{t("wcNone")}</p>}
          <ol className="wc-list">
            {groups.map((g, gi) => (
              <li key={gi} className={g.length > 1 ? "wc-group" : ""}>
                {g.length > 1 && <div className="wc-together">{t("wcTogether", { ms: fmtNum(Math.max(...g.map((x) => 1000 / (x.rate || 1e9))), lang, 3) })}</div>}
                {g.map((x) => (
                  <div key={x.id} className={`wc-row${picked.includes(x.id) ? " picked" : ""}`}>
                    <input type="checkbox" checked={picked.includes(x.id)} onChange={() => togglePick(x.id)} aria-label={signalName(runs, x.id)} />
                    <Spark v={x.spark ?? []} up={!!x.up} />
                    <button className="linklike wc-name" title={t("occDifferAdd")} onClick={() => actions.addSignals([x.id])}>{signalName(runs, x.id)}</button>
                    <span className={x.up ? "up" : "down"}>{x.up ? "↑" : "↓"} {t("occTimes", { x: fmtNum(Math.min(x.strength ?? 0, 999), lang, 2) })}</span>
                    <span className="wc-rel">{(x.rel! >= 0 ? "+" : "") + fmtNum(x.rel!, lang, 3)} s</span>
                    <span className="muted wc-rate">{x.rate ? `${fmtNum(x.rate, lang, 3)} Hz` : ""}</span>
                  </div>
                ))}
              </li>
            ))}
          </ol>
          {same.length > 0 && (
            <button className="linklike wc-same" onClick={() => setShowSame(!showSame)}>{showSame ? "▾" : "▸"} {t("wcSame", { n: same.length })}</button>
          )}
          {showSame && <p className="hint">{same.map((x) => signalName(runs, x.id)).join(", ")}</p>}
          {nodata.length > 0 && <p className="hint">{t("wcNoData", { names: nodata.map((x) => signalName(runs, x.id)).join(", ") })}</p>}
          <div className="occ-actions">
            <button className="btn outline sm wc-stack" disabled={!changed.length} onClick={stacked}>
              {picked.length ? t("wcStackPicked", { n: picked.length }) : t("wcStackTop")}</button>
            <button className="btn outline sm wc-lag" disabled={picked.length !== 2} onClick={runLag}>{t("wcLag")}</button>
          </div>
          {lag && <LagBox r={lag} names={[signalName(runs, lag.a), signalName(runs, lag.b)]} onAlign={showAligned} />}
        </>
      )}
    </section>
  );
}

function Spark({ v, up }: { v: (number | null)[]; up: boolean }) {
  const ok = v.filter((x): x is number => x !== null);
  if (ok.length < 2) return <svg className="wc-spark" width={56} height={16} aria-hidden="true" />;
  const lo = Math.min(...ok), hi = Math.max(...ok), sp = hi - lo || 1;
  const pts = v.map((x, i) => (x === null ? null : `${(i / (v.length - 1)) * 56},${15 - ((x - lo) / sp) * 14}`)).filter(Boolean).join(" ");
  return <svg className="wc-spark" width={56} height={16} aria-hidden="true"><polyline points={pts} fill="none" stroke={up ? "var(--danger)" : "var(--focus)"} strokeWidth={1.2} /></svg>;
}

/** The lag between two signals, said as a sentence - or why there is no one number. */
function LagBox({ r, names, onAlign }: { r: LagResult; names: [string, string]; onAlign: () => void }) {
  const t = useT();
  const lang = useApp((s) => s.lang);
  if (r.status !== "ok") return <p className="hint wc-lag-out">{t("wcLagNone")}</p>;
  const ms = fmtNum(Math.abs(r.lag!) * 1000, lang, 3);
  const text = r.weak ? t("wcLagWeak", { a: names[0], b: names[1], r: fmtNum(r.r!, lang, 2) })
    : r.lag! >= 0 ? t("wcLagFollows", { a: names[0], b: names[1], ms, r: fmtNum(r.r!, lang, 2) })
      : t("wcLagLeads", { a: names[0], b: names[1], ms, r: fmtNum(r.r!, lang, 2) });
  const c = r.curve!;
  const w = 220, h = 40, lo = c.lags[0], hi = c.lags[c.lags.length - 1] || 1;
  const pts = c.lags.map((L, i) => `${((L - lo) / (hi - lo || 1)) * w},${h / 2 - c.r[i] * (h / 2 - 2)}`).join(" ");
  return (
    <div className="wc-lag-out">
      <p>{text}{!r.weak && r.r! < 0 ? ` ${t("wcLagInverse")}` : ""}{r.ambiguous ? ` ${t("wcLagAmbiguous")}` : ""}
        {r.resolution ? ` ${t("wcLagRes", { ms: fmtNum(r.resolution * 1000, lang, 3) })}` : ""}</p>
      <svg width={w} height={h} className="wc-lag-curve" aria-hidden="true">
        <line x1={0} x2={w} y1={h / 2} y2={h / 2} stroke="var(--line)" />
        <line x1={((0 - lo) / (hi - lo || 1)) * w} x2={((0 - lo) / (hi - lo || 1)) * w} y1={0} y2={h} stroke="var(--line)" />
        <polyline points={pts} fill="none" stroke="var(--amber)" strokeWidth={1.5} />
      </svg>
      {!r.weak && <button className="btn outline sm wc-align" onClick={onAlign}>{t("wcShowAligned")}</button>}
    </div>
  );
}
