import { useEffect, useMemo, useState } from "react";
import { api, type FirstChange, type LagResult } from "../api";
import { actions, activeTab, fileLabel, signalName, uid, useApp, type Plot, type Tab } from "../store";
import { fmtNum, useT } from "../i18n";
import { Icon } from "../icons";
import { record } from "../investigation";
import { translate } from "../i18n";

/** Investigation step 4: around the selected span, which signals left their usual range first -
 *  ranked CANDIDATES with a small picture each, grouped when the sample rates cannot tell them apart,
 *  a warning that earlier is not cause, and the lag between two of them.
 *  By default: every signal of the file the event is in (the one whose signal is most unusual in the
 *  span) - what leads to it is often not on the plots - and, under each, the same signal in the other
 *  open files at the same time: a change that the run without the event also has is not its cause. */
export default function WhatChanged() {
  const t = useT();
  const lang = useApp((s) => s.lang);
  const runs = useApp((s) => s.runs);
  const span = useApp((s) => s.whatChanged)!;
  const ws = useApp((s) => s.ws);
  const [scope, setScope] = useState<"file" | "tab" | "all">("file");
  const [fileRid, setFileRid] = useState<string | null>(null);
  const [others, setOthers] = useState<Record<string, FirstChange[]>>({});
  // a long list (a flight log has hundreds of signals): a filter, rows and groups hidden, groups closed
  const [filter, setFilter] = useState("");
  const [hidden, setHidden] = useState<string[]>([]);
  const [closed, setClosed] = useState<string[]>([]);
  const [opened, setOpened] = useState<string[]>([]);
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

  // the file the event is in: the one whose signal is most unusual inside the span
  useEffect(() => {
    let gone = false;
    const first = allFiles[0] ?? null;
    if (allFiles.length < 2) { setFileRid(first); return; }
    api.suggestCondition(span.a, span.b, tabSigs)
      .then((s) => { if (!gone) setFileRid(s.id && s.id.includes("/") ? s.id.slice(0, s.id.indexOf("/")) : first); })
      .catch(() => { if (!gone) setFileRid(first); });
    return () => { gone = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [span.a, span.b]);
  const otherFiles = scope === "file" && fileRid ? allFiles.filter((r) => r !== fileRid) : [];
  // the same signals in the other open files, at the same time
  useEffect(() => {
    let gone = false;
    setOthers({});
    if (!otherFiles.length) return;
    api.firstChange(span.a, span.b, [], otherFiles).then((r) => {
      if (gone) return;
      const by: Record<string, FirstChange[]> = {};
      for (const x of r.items) (by[x.name] ??= []).push(x);
      setOthers(by);
    }).catch(() => { /* the comparison is extra */ });
    return () => { gone = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [span.a, span.b, scope, fileRid, otherFiles.join("|")]);

  useEffect(() => {
    if (scope === "file" && !fileRid) return;
    let gone = false;
    setItems(null); setErr(""); setPicked([]); setLag(null);
    api.firstChange(span.a, span.b, scope === "tab" ? tabSigs : [], scope === "all" ? allFiles : scope === "file" ? [fileRid!] : [])
      .then((r) => {
        if (gone) return;
        setItems(r.items); setBase(r.base);
        const top = r.items.filter((x) => x.status === "changed").slice(0, 4).map((x) => `${x.name} (${(x.rel! >= 0 ? "+" : "") + x.rel!.toFixed(2)} s)`);
        record(translate(useApp.getState().lang, "jChanged", { a: span.a.toPrecision(6), b: span.b.toPrecision(6), list: top.join(", ") || "–" }), true, "changed");
      })
      .catch((e) => { if (!gone) setErr(String((e as Error).message)); });
    return () => { gone = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [span.a, span.b, scope, fileRid]);
  useEffect(() => () => useApp.setState({ changeMarks: null }), []);      // the dashed lines go with the section

  const close = () => useApp.setState({ whatChanged: null, changeMarks: null });
  const changed = (items ?? []).filter((x) => x.status === "changed");
  const same = (items ?? []).filter((x) => x.status === "same");
  const nodata = (items ?? []).filter((x) => x.status === "nodata");
  // the filter: every word in the name (or the file's), in any case
  const words = filter.toLowerCase().split(/\s+/).filter(Boolean);
  const shown = changed.filter((x) => !hidden.includes(x.id)
    && words.every((w) => signalName(runs, x.id).toLowerCase().includes(w)));
  // the dashed lines on the plots: the rows in the list
  useEffect(() => {
    if (items) useApp.setState({ changeMarks: Object.fromEntries(shown.map((x) => [x.id, x.t!])) });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [items, shown.map((x) => x.id).join("|")]);
  // rows that the sample rates cannot order: "together", not one before the other. Measured from
  // the group's first row - one slow signal must not chain a whole log into one group.
  const groups: FirstChange[][] = [];
  for (const x of shown) {
    const last = groups[groups.length - 1];
    const first = last?.[0];
    const res = first ? Math.max(1 / (first.rate || 1e9), 1 / (x.rate || 1e9)) : 0;
    if (first && x.t! - first.t! <= res) last.push(x); else groups.push([x]);
  }
  const hide = (ids: string[]) => { setHidden((h) => [...h, ...ids]); setPicked((p) => p.filter((x) => !ids.includes(x))); };
  const toggleGroup = (k: string) => setClosed((c) => (c.includes(k) ? c.filter((x) => x !== k) : [...c, k]));
  const LIMIT = 5;
  const rates = changed.map((x) => x.rate ?? 0).filter((r) => r > 0);
  const coarse = rates.length ? 1 / Math.min(...rates) : 0;
  const togglePick = (id: string) => setPicked((p) => (p.includes(id) ? p.filter((x) => x !== id) : [...p, id].slice(-6)));
  const stacked = () => {
    const ids = picked.length ? picked : shown.slice(0, 4).map((x) => x.id);
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
    try {
      const res = await api.lag(a, b, span.a - 2 * L, span.b + 2 * L);
      setLag({ ...res, a, b });
      if (res.status === "ok" && !res.weak) record(translate(useApp.getState().lang, "jLag", { a: signalName(runs, a), b: signalName(runs, b), ms: Math.round(res.lag! * 1000), r: res.r!.toFixed(2) }), true, "lag");
    }
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
      <select className="wc-scope" value={scope} onChange={(e) => setScope(e.target.value as "file" | "tab" | "all")} aria-label={t("wcScope")}>
        {fileRid && <option value="file">{t("wcScopeFile", { file: fileLabel(runs, fileRid), n: runs.find((r) => r.id === fileRid)?.signals.length ?? 0 })}</option>}
        <option value="tab">{t("wcScopeTab", { n: tabSigs.length })}</option>
        <option value="all">{t("wcScopeAll", { n: total })}</option>
      </select>
      {err && <p className="hint err">{err}</p>}
      {!items && !err && <p className="hint">{t("loading")}</p>}
      {items && (
        <>
          <p className="wc-warn">{t("wcNotCause")}{coarse > 0.02 ? ` ${t("wcResolution", { ms: fmtNum(coarse * 1000, lang, 3) })}` : ""}</p>
          {otherFiles.length > 0 && <p className="hint wc-other-hint">{t("wcOtherHint")}</p>}
          {!changed.length && <p className="hint">{t("wcNone")}</p>}
          {changed.length > 0 && (
            <div className="wc-tools">
              <input className="wc-filter" type="search" value={filter} placeholder={t("wcFilter")} aria-label={t("wcFilter")}
                onChange={(e) => setFilter(e.target.value)} onKeyDown={(e) => { if (e.key === "Escape" && filter) { e.stopPropagation(); setFilter(""); } }} />
              <span className="muted wc-count">{t("wcShown", { n: shown.length, m: changed.length })}</span>
            </div>
          )}
          {hidden.length > 0 && <button className="linklike wc-unhide" onClick={() => setHidden([])}>{t("wcHidden", { n: hidden.length })}</button>}
          <ol className="wc-list">
            {groups.map((g) => {
              const k = g[0].id, open = !closed.includes(k);
              const rows = opened.includes(k) ? g : g.slice(0, LIMIT);
              const rel = (x: FirstChange) => (x.rel! >= 0 ? "+" : "") + fmtNum(x.rel!, lang, 3);
              return (
              <li key={k} className={g.length > 1 ? "wc-group" : ""}>
                {g.length > 1 && (
                  <div className="wc-ghead" title={t("wcTogether", { ms: fmtNum(Math.max(...g.map((x) => 1000 / (x.rate || 1e9))), lang, 3) })}>
                    <button className="linklike wc-gtoggle" aria-expanded={open} onClick={() => toggleGroup(k)}>
                      {open ? "▾" : "▸"} {t("wcGroup", { n: g.length })} <span dir="ltr">{rel(g[0])} … {rel(g[g.length - 1])} s</span>
                    </button>
                    <button className="iconbtn sm wc-ghide" aria-label={t("wcHideGroup")} title={t("wcHideGroup")} onClick={() => hide(g.map((x) => x.id))}><Icon.X /></button>
                  </div>
                )}
                {open && rows.map((x) => (
                  <div key={x.id} className={`wc-row${picked.includes(x.id) ? " picked" : ""}`}>
                    <input type="checkbox" checked={picked.includes(x.id)} onChange={() => togglePick(x.id)} aria-label={signalName(runs, x.id)} />
                    <Spark v={x.spark ?? []} up={!!x.up} />
                    <button className="linklike wc-name" dir="ltr" title={`${signalName(runs, x.id)} - ${t("occDifferAdd")}`}
                      onClick={(e) => (e.ctrlKey || e.metaKey ? actions.addSignals([x.id]) : actions.addSignalsToOneNewPlot([x.id]))}>{x.name}</button>
                    <span className={x.up ? "up" : "down"} dir="ltr">{x.up ? "↑" : "↓"} {t("occTimes", { x: fmtNum(Math.min(x.strength ?? 0, 999), lang, 2) })}</span>
                    <span className="wc-rel" dir="ltr">{(x.rel! >= 0 ? "+" : "") + fmtNum(x.rel!, lang, 3)} s</span>
                    <span className="muted wc-rate"><bdi>{scope === "file" ? "" : `${fileLabel(runs, x.id.slice(0, x.id.indexOf("/")))} · `}</bdi>{x.rate ? <bdi dir="ltr">{fmtNum(x.rate, lang, 3)} Hz</bdi> : ""}</span>
                    {(others[x.name] ?? []).map((o) => {
                      const f = fileLabel(runs, o.id.slice(0, o.id.indexOf("/")));
                      return (
                        <span key={o.id} dir="ltr" className={`wc-other${o.status === "changed" ? "" : " same"}`}>
                          <bdi>{f}</bdi>: {o.status === "changed"
                            ? <span dir="ltr">{o.up ? "↑" : "↓"} {t("occTimes", { x: fmtNum(Math.min(o.strength ?? 0, 999), lang, 2) })} · {(o.rel! >= 0 ? "+" : "") + fmtNum(o.rel!, lang, 3)} s</span>
                            : t("wcOtherSame")}
                        </span>
                      );
                    })}
                    <button className="iconbtn sm wc-hide" aria-label={t("wcHide")} title={t("wcHide")} onClick={() => hide([x.id])}><Icon.X /></button>
                  </div>
                ))}
                {open && rows.length < g.length && (
                  <button className="linklike wc-more" onClick={() => setOpened((o) => [...o, k])}>{t("wcMore", { n: g.length - rows.length })}</button>
                )}
              </li>
              );
            })}
          </ol>
          {changed.length > 0 && !shown.length && <p className="hint">{t("wcNoMatch")}</p>}
          {same.length > 0 && (
            <button className="linklike wc-same" onClick={() => setShowSame(!showSame)}>{showSame ? "▾" : "▸"} {t("wcSame", { n: same.length })}</button>
          )}
          {showSame && <p className="hint">{same.map((x) => signalName(runs, x.id)).join(", ")}</p>}
          {nodata.length > 0 && <p className="hint">{t("wcNoData", { names: nodata.map((x) => signalName(runs, x.id)).join(", ") })}</p>}
          <div className="occ-actions">
            <button className="btn outline sm wc-stack" disabled={!shown.length} onClick={stacked}>
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
