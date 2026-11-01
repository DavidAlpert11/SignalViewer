import { useEffect, useMemo, useRef, useState } from "react";
import { api, type ChangeCluster, type FirstChange, type LagResult } from "../api";
import { actions, activeTab, fileLabel, rangeKey, signalName, uid, useApp, type Plot, type Tab } from "../store";
import { fmtNum, useT } from "../i18n";
import { Icon } from "../icons";
import { record } from "../investigation";
import { translate, type Lang } from "../i18n";

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
  const [opened, setOpened] = useState<string[]>([]);
  const [items, setItems] = useState<FirstChange[] | null>(null);
  const [base, setBase] = useState<[number, number] | null>(null);
  const [noRoom, setNoRoom] = useState(false);       // nothing before the span to learn the usual level
  const [err, setErr] = useState("");
  const [picked, setPicked] = useState<string[]>([]);
  const [showSame, setShowSame] = useState(false);
  const [lag, setLag] = useState<(LagResult & { a: string; b: string }) | null>(null);
  // Q130-Q133: clusters of changes, the likeliest first, what cannot tell anything left out
  const [clusters, setClusters] = useState<ChangeCluster[]>([]);
  const [eventId, setEventId] = useState<string | null>(null);
  const [skipped, setSkipped] = useState<Record<string, number>>({});
  const [showSkipped, setShowSkipped] = useState(false);
  const [order, setOrder] = useState<"likely" | "time">("likely");
  const [openC, setOpenC] = useState<string[]>([]);            // opened clusters (by their first id)
  const [openP, setOpenP] = useState<string[]>([]);            // opened name groups (cluster|prefix)
  const listRef = useRef<HTMLOListElement>(null);

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
    if (allFiles.length < 2) {
      setFileRid(first);
      // the event's signal: the plotted one most unusual inside the span (Q131's shape part)
      if (tabSigs.length) api.suggestCondition(span.a, span.b, tabSigs).then((s) => { if (!gone) setEventId(s.id ?? null); }).catch(() => {});
      return;
    }
    api.suggestCondition(span.a, span.b, tabSigs)
      .then((s) => { if (!gone) { setFileRid(s.id && s.id.includes("/") ? s.id.slice(0, s.id.indexOf("/")) : first); setEventId(s.id ?? null); } })
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
    api.firstChange(span.a, span.b, scope === "tab" ? tabSigs : [], scope === "all" ? allFiles : scope === "file" ? [fileRid!] : [],
      scope === "file" ? otherFiles : [], eventId)
      .then((r) => {
        if (gone) return;
        setItems(r.items); setBase(r.base); setNoRoom(!!r.noRoom);
        setClusters(r.clusters ?? []); setSkipped(r.skipped ?? {});
        setOpenC((r.clusters ?? []).slice(0, 1).map((c) => c.first));     // the likeliest cluster open
        const top = r.items.filter((x) => x.status === "changed").slice(0, 4).map((x) => `${x.name} (${(x.rel! >= 0 ? "+" : "") + x.rel!.toFixed(2)} s)`);
        record(translate(useApp.getState().lang, "jChanged", { a: span.a.toPrecision(6), b: span.b.toPrecision(6), list: top.join(", ") || "–" }), true, "changed");
      })
      .catch((e) => { if (!gone) setErr(String((e as Error).message)); });
    return () => { gone = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [span.a, span.b, scope, fileRid, eventId]);
  useEffect(() => () => useApp.setState({ changeMarks: null }), []);      // the dashed lines go with the section

  const close = () => useApp.setState({ whatChanged: null, changeMarks: null });
  const changed = (items ?? []).filter((x) => x.status === "changed");
  const same = (items ?? []).filter((x) => x.status === "same");
  const nodata = (items ?? []).filter((x) => x.status === "nodata");
  // the filter: every word in the name (or the file's), in any case
  const words = filter.toLowerCase().split(/\s+/).filter(Boolean);
  const visible = (x: FirstChange) => !hidden.includes(x.id) && words.every((w) => signalName(runs, x.id).toLowerCase().includes(w));
  const byId = useMemo(() => new Map((items ?? []).map((x) => [x.id, x])), [items]);
  // Q133: what cannot tell anything (constant, a counter or clock, a heartbeat) - out unless asked
  const leftOut = (items ?? []).filter((x) => x.skip);
  const nSkipped = Object.values(skipped).reduce((a, b) => a + b, 0);
  // the clusters as shown: their members filtered; by likelihood (the server's order) or by time
  const shownClusters = useMemo(() => {
    const cs = clusters.map((c) => ({ ...c, ids: c.ids.filter((id) => { const x = byId.get(id); return !!x && visible(x); }) })).filter((c) => c.ids.length);
    if (order === "time") {
      cs.sort((p, q) => p.t0 - q.t0);
      for (const c of cs) c.ids = [...c.ids].sort((p, q) => byId.get(p)!.t! - byId.get(q)!.t!);
    }
    return cs;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clusters, byId, hidden.join("|"), filter, order]);
  const shown = shownClusters.flatMap((c) => c.ids.map((id) => byId.get(id)!));
  // the dashed lines on the plots: the rows in the list
  useEffect(() => {
    if (items) useApp.setState({ changeMarks: Object.fromEntries(shown.map((x) => [x.id, x.t!])) });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [items, shown.map((x) => x.id).join("|")]);
  const hide = (ids: string[]) => { setHidden((h) => [...h, ...ids]); setPicked((p) => p.filter((x) => !ids.includes(x))); };
  const toggleC = (k: string, on?: boolean) => setOpenC((c) => ((on ?? !c.includes(k)) ? [...c.filter((x) => x !== k), k] : c.filter((x) => x !== k)));
  const toggleP = (k: string) => setOpenP((c) => (c.includes(k) ? c.filter((x) => x !== k) : [...c, k]));
  const LIMIT = 5;
  const rates = changed.map((x) => x.rate ?? 0).filter((r) => r > 0);
  const coarse = rates.length ? 1 / Math.min(...rates) : 0;
  const togglePick = (id: string) => setPicked((p) => (p.includes(id) ? p.filter((x) => x !== id) : [...p, id].slice(-6)));
  const stacked = (only?: string[]) => {
    const ids = only ?? (picked.length ? picked : shown.slice(0, 4).map((x) => x.id));
    if (!ids.length) return;
    useApp.getState().commit((w) => {
      const plots: Plot[] = ids.map((id, i) => ({ id: uid("p"), title: signalName(runs, id), signals: [{ sig: id, color: ["#3D8BFD", "#E8590C", "#2F9E44", "#AE3EC9", "#F08C00", "#0CA678"][i % 6], width: 1.5, scale: 1, offset: 0 }] }));
      const tab: Tab = { id: uid("t"), name: t("wcTabName"), rows: plots.length, cols: 1, plots, active: 0, linkX: true };
      w.tabs.push(tab); w.activeTab = tab.id;
      return w;
    });
    // the span between the cursors, and in view from before the earliest change of these signals
    const L = span.b - span.a;
    const from = Math.min(span.a - L, ...ids.map((id) => byId.get(id)?.t ?? span.a));
    actions.showSpan(span.a, span.b);
    const st = useApp.getState(), tb = activeTab(st.ws), pad = Math.max(L / 4, 0.2);
    useApp.setState({ ranges: { ...st.ranges, ...Object.fromEntries(tb.plots.map((p) => [rangeKey(tb, p), [from - pad, span.b + L / 2] as [number, number]])) } });
  };
  const keepCluster = (c: ChangeCluster) => {
    const names = c.ids.slice(0, 6).map((id) => byId.get(id)?.name ?? id);
    record(translate(useApp.getState().lang, "jCluster", { t: (c.t0 - span.a >= 0 ? "+" : "") + (c.t0 - span.a).toFixed(2), n: c.ids.length,
      list: names.join(", ") + (c.ids.length > 6 ? ", …" : "") }), true, "changed");
    useApp.getState().toast({ kind: "info", text: t("wcKept") });
  };
  // ↑ ↓ through the clusters, → opens, ← closes, Enter plots it
  const onListKey = (e: React.KeyboardEvent) => {
    const heads = [...(listRef.current?.querySelectorAll<HTMLButtonElement>(".wc-chead") ?? [])];
    const i = heads.indexOf(document.activeElement as HTMLButtonElement);
    if (i < 0) return;
    const c = shownClusters[i];
    if (e.key === "ArrowDown" || e.key === "ArrowUp") { e.preventDefault(); heads[Math.max(0, Math.min(heads.length - 1, i + (e.key === "ArrowDown" ? 1 : -1)))]?.focus(); }
    else if (e.key === "ArrowRight" || e.key === "ArrowLeft") { e.preventDefault(); toggleC(c.first, (e.key === "ArrowRight") !== (lang === "he")); }
    else if (e.key === "Enter") { e.preventDefault(); stacked(c.ids); }
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

  const ROW = (x: FirstChange) => (
                  <div key={x.id} className={`wc-row${picked.includes(x.id) ? " picked" : ""}${x.inRef?.length ? " inref" : ""}`}>
                    <input type="checkbox" checked={picked.includes(x.id)} onChange={() => togglePick(x.id)} aria-label={signalName(runs, x.id)} />
                    <Spark v={x.spark ?? []} up={!!x.up} />
                    <button className="linklike wc-name" dir="ltr" title={`${signalName(runs, x.id)} - ${t("occDifferAdd")}`}
                      onClick={(e) => (e.ctrlKey || e.metaKey ? actions.addSignals([x.id]) : actions.addSignalsToOneNewPlot([x.id]))}>{x.name}</button>
                    <span className={x.up ? "up" : "down"} dir="ltr">{x.up ? "↑" : "↓"} {t("occTimes", { x: fmtNum(Math.min(x.strength ?? 0, 999), lang, 2) })}</span>
                    <span className="wc-rel"><bdi dir="ltr">{(x.rel! >= 0 ? "+" : "") + fmtNum(x.rel!, lang, 3)}</bdi> {t("seconds")}</span>
                    <span className="muted wc-rate"><bdi>{scope === "file" ? "" : `${fileLabel(runs, x.id.slice(0, x.id.indexOf("/")))} · `}</bdi>{x.rate ? <bdi dir="ltr">{fmtNum(x.rate, lang, 3)} Hz</bdi> : ""}</span>
                    <Why t={t} x={x} lang={lang} />
                    {(others[x.name] ?? []).map((o) => {
                      const f = fileLabel(runs, o.id.slice(0, o.id.indexOf("/")));
                      return (
                        // (no dir="ltr" on the row: in Hebrew it put "no change" before the file name)
                        <span key={o.id} className={`wc-other${o.status === "changed" ? "" : " same"}`}>
                          <bdi>{f}</bdi>: {o.status === "changed"
                            ? <><bdi dir="ltr">{o.up ? "↑" : "↓"} {t("occTimes", { x: fmtNum(Math.min(o.strength ?? 0, 999), lang, 2) })} · {(o.rel! >= 0 ? "+" : "") + fmtNum(o.rel!, lang, 3)}</bdi> {t("seconds")}</>
                            : t("wcOtherSame")}
                        </span>
                      );
                    })}
                    <button className="iconbtn sm wc-hide" aria-label={t("wcHide")} title={t("wcHide")} onClick={() => hide([x.id])}><Icon.X /></button>
                  </div>
                );
  return (
    <section className="wc-section">
      <div className="wc-head">
        <h3>{t("wcTitle")}</h3>
        <button className="iconbtn" aria-label={t("close")} onClick={close}><Icon.X /></button>
      </div>
      <p className="hint">{t("wcSpan", { a: fmtNum(span.a, lang, 6), b: fmtNum(span.b, lang, 6) })}
        {base && base[1] > base[0] ? ` ${t("wcBase", { a: fmtNum(base[0], lang, 6), b: fmtNum(base[1], lang, 6) })}` : ""}</p>
      <select className="wc-scope" value={scope} onChange={(e) => setScope(e.target.value as "file" | "tab" | "all")} aria-label={t("wcScope")}>
        {fileRid && <option value="file">{t("wcScopeFile", { file: `\u2068${fileLabel(runs, fileRid)}\u2069`, n: runs.find((r) => r.id === fileRid)?.signals.length ?? 0 })}</option>}
        <option value="tab">{t("wcScopeTab", { n: tabSigs.length })}</option>
        <option value="all">{t("wcScopeAll", { n: total })}</option>
      </select>
      {err && <p className="hint err">{err}</p>}
      {!items && !err && <p className="hint">{t("loading")}</p>}
      {items && (
        <>
          <p className="wc-warn">{t(order === "likely" ? "wcNotCauseLikely" : "wcNotCause")}{coarse > 0.02 ? ` ${t("wcResolution", { ms: fmtNum(coarse * 1000, lang, 3) })}` : ""}</p>
          {otherFiles.length > 0 && <p className="hint wc-other-hint">{t("wcOtherHint")}</p>}
          {noRoom ? <p className="hint wc-noroom">{t("wcNoRoom")}</p> : !changed.length && <p className="hint">{t("wcNone")}</p>}
          {changed.length > 0 && (
            <div className="wc-tools">
              <input className="wc-filter" type="search" value={filter} placeholder={t("wcFilter")} aria-label={t("wcFilter")}
                onChange={(e) => setFilter(e.target.value)} onKeyDown={(e) => { if (e.key === "Escape" && filter) { e.stopPropagation(); setFilter(""); } }} />
              <span className="muted wc-count">{t("wcShown", { n: shown.length, m: changed.length })}</span>
              <select className="wc-order" aria-label={t("wcOrder")} value={order} onChange={(e) => setOrder(e.target.value as "likely" | "time")}>
                <option value="likely">{t("wcOrderLikely")}</option><option value="time">{t("wcOrderTime")}</option>
              </select>
            </div>
          )}
          {hidden.length > 0 && <button className="linklike wc-unhide" onClick={() => setHidden([])}>{t("wcHidden", { n: hidden.length })}</button>}
          <ol className="wc-list wc-clusters" ref={listRef} onKeyDown={onListKey}>
            {shownClusters.map((c) => {
              const k = c.first, open = openC.includes(k);
              const xs = c.ids.map((id) => byId.get(id)!);
              const rel = (v: number) => (v - span.a >= 0 ? "+" : "") + fmtNum(v - span.a, lang, 3);
              const top = xs.filter((x) => !x.isEvent).slice(0, 3).map((x) => x.name);
              // Q133: names grouped by their message / prefix (ATT.Roll, ATT.Pitch...) when two or more share it
              const pre = (x: FirstChange) => (x.name.includes(".") ? x.name.slice(0, x.name.indexOf(".")) : "");
              const counts = new Map<string, number>();
              for (const x of xs) counts.set(pre(x), (counts.get(pre(x)) ?? 0) + 1);
              const parts: (FirstChange | { prefix: string; members: FirstChange[] })[] = [];
              for (const x of xs) {
                const p = pre(x);
                if (!p || counts.get(p)! < 2) { parts.push(x); continue; }
                const g = parts.find((q): q is { prefix: string; members: FirstChange[] } => "prefix" in q && q.prefix === p);
                if (g) g.members.push(x); else parts.push({ prefix: p, members: [x] });
              }
              const rows = opened.includes(k) ? parts : parts.slice(0, LIMIT);
              return (
              <li key={k} className={`wc-cluster${open ? " open" : ""}${k === "skipped" ? " skipped" : ""}`} data-n={xs.length}>
                <div className="wc-ghead">
                  <button className="linklike wc-chead" aria-expanded={open} onClick={() => toggleC(k)}
                    title={c.t1 > c.t0 ? t("wcClusterSpan", { a: rel(c.t0), b: rel(c.t1) }) : undefined}>
                    {open ? "▾" : "▸"} <bdi dir="ltr">{rel(c.t0)}</bdi> {t("seconds")} · {k === "skipped" ? t("wcLeftOutGroup", { n: xs.length }) : t("wcClusterN", { n: xs.length })}
                    {k !== "skipped" && <span className="wc-ctop" dir="ltr"> {top.join(", ")}{xs.length > top.length ? " …" : ""}</span>}
                  </button>
                  {k !== "skipped" && <span className="wc-score" title={t("wcScoreHint")}>{Math.round(c.best * 100)}</span>}
                  <button className="iconbtn sm wc-ghide" aria-label={t("wcHideGroup")} title={t("wcHideGroup")} onClick={() => hide(c.ids)}><Icon.X /></button>
                </div>
                {open && <>
                  <ClusterPlot xs={xs} base={base} span={span} lang={lang} t={t} />
                  <div className="wc-cactions">
                    <button className="btn outline sm wc-open-tab" onClick={() => stacked(c.ids)}>{t("wcOpenTab")}</button>
                    <button className="btn outline sm wc-keep" onClick={() => keepCluster(c)}>{t("wcKeep")}</button>
                  </div>
                  {rows.map((part) => "prefix" in part ? (
                    <div key={part.prefix} className="wc-prefix">
                      <button className="linklike wc-ptoggle" aria-expanded={openP.includes(`${k}|${part.prefix}`)} onClick={() => toggleP(`${k}|${part.prefix}`)}>
                        {openP.includes(`${k}|${part.prefix}`) ? "▾" : "▸"} <bdi dir="ltr">{part.prefix}.*</bdi> · {t("wcClusterN", { n: part.members.length })}
                        <span className="wc-score">{Math.round(Math.max(...part.members.map((m) => m.score ?? 0)) * 100)}</span>
                      </button>
                      {openP.includes(`${k}|${part.prefix}`) && part.members.map(ROW)}
                    </div>
                  ) : ROW(part))}
                  {rows.length < parts.length && (
                    <button className="linklike wc-more" onClick={() => setOpened((o) => [...o, k])}>{t("wcMore", { n: parts.length - rows.length })}</button>
                  )}
                </>}
              </li>
              );
            })}
          </ol>
          {nSkipped > 0 && (
            <button className="linklike wc-skipped" aria-expanded={showSkipped} onClick={() => setShowSkipped(!showSkipped)}>
              {showSkipped ? t("wcSkippedHide") : t("wcSkippedShow", { n: nSkipped, kinds: Object.entries(skipped).map(([kk, n]) => `${t(`wcSkip_${kk}` as "wcSkip_constant")} ${n}`).join(", ") })}
            </button>
          )}
          {showSkipped && <ul className="wc-skiplist">{leftOut.map((x) => (
            <li key={x.id}><button className="linklike wc-name" dir="ltr" onClick={() => actions.addSignalsToOneNewPlot([x.id])}>{x.name}</button>
              <span className="muted"> · {t(`wcSkip_${x.skip}` as "wcSkip_constant")}</span></li>))}</ul>}
          {changed.length > 0 && !shown.length && <p className="hint">{t("wcNoMatch")}</p>}
          {same.length > 0 && (
            <button className="linklike wc-same" onClick={() => setShowSame(!showSame)}>{showSame ? "▾" : "▸"} {t("wcSame", { n: same.length })}</button>
          )}
          {showSame && <p className="hint">{same.map((x) => signalName(runs, x.id)).join(", ")}</p>}
          {nodata.length > 0 && !noRoom && <p className="hint">{t("wcNoData", { names: nodata.map((x) => signalName(runs, x.id)).join(", ") })}</p>}
          <div className="occ-actions">
            <button className="btn outline sm wc-stack" disabled={!shown.length} onClick={() => stacked()}>
              {picked.length ? t("wcStackPicked", { n: picked.length }) : t("wcStackTop")}</button>
            <button className="btn outline sm wc-lag" disabled={picked.length !== 2} onClick={runLag}>{t("wcLag")}</button>
          </div>
          {lag && <LagBox r={lag} names={[signalName(runs, lag.a), signalName(runs, lag.b)]} onAlign={showAligned} />}
        </>
      )}
    </section>
  );
}

/** Q131: the score and, on hover, its parts - no black box. */
function Why({ t, x, lang }: { t: ReturnType<typeof useT>; x: FirstChange; lang: Lang }) {
  if (x.score === undefined || !x.parts) return null;
  const lines = Object.entries(x.parts).map(([k, v]) => `${t(`wcPart_${k}` as "wcPart_strength")}: ${Math.round(v * 100)}`);
  if (x.inRef?.length) lines.push(t("wcInRef"));
  if (x.leadsEvent !== undefined) lines.push(t("wcLeadsEvent", { ms: fmtNum(x.leadsEvent * 1000, lang, 3) }));
  if (x.isEvent) lines.push(t("wcIsEvent"));
  return <span className={`wc-why${x.inRef?.length ? " inref" : ""}`} title={lines.join("\n")} aria-label={lines.join("; ")}>
    {x.isEvent ? "◆" : x.inRef?.length ? "≈" : ""}{Math.round(x.score * 100)}</span>;
}

const LINE_COLORS = ["#3D8BFD", "#E8590C", "#2F9E44", "#AE3EC9", "#F08C00", "#0CA678", "#E64980", "#5C7CFA"];

/** Q132: a cluster's signals on one axis - each as (value - its usual level) / its usual noise - from
 *  the baseline to the end of the span; the span shaded, a tick at each one's change; the pointer
 *  shows the names and real values at that moment. */
function ClusterPlot({ xs, base, span, lang, t }: { xs: FirstChange[]; base: [number, number] | null; span: { a: number; b: number };
  lang: Lang; t: ReturnType<typeof useT> }) {
  const [hover, setHover] = useState<number | null>(null);
  const lo = base ? base[0] : span.a, hi = span.b;
  const n = Math.max(...xs.map((x) => x.spark?.length ?? 0), 2);
  const norm = xs.map((x) => (x.spark ?? []).map((v) => (v === null || !Number.isFinite(v) ? null
    : Math.max(-50, Math.min(50, (v - (x.level ?? 0)) / (x.noise || 1))))));
  const all = norm.flat().filter((v): v is number => v !== null);
  const ymin = Math.min(-5, ...all), ymax = Math.max(5, ...all);
  const W = 300, H = 120, P = 4;
  const X = (i: number) => P + (i / (n - 1)) * (W - 2 * P);
  const T = (tt: number) => P + ((tt - lo) / (hi - lo || 1)) * (W - 2 * P);
  const Y = (v: number) => H - P - ((v - ymin) / (ymax - ymin || 1)) * (H - 2 * P);
  const at = hover === null ? null : lo + (hover / (n - 1)) * (hi - lo);
  return (
    <figure className="wc-cplot">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={t("wcPlotOf", { n: xs.length })} data-lines={xs.length}
        onMouseMove={(e) => { const r = (e.currentTarget as SVGSVGElement).getBoundingClientRect(); setHover(Math.round(((e.clientX - r.left) / r.width * W - P) / (W - 2 * P) * (n - 1))); }}
        onMouseLeave={() => setHover(null)}>
        <rect x={T(span.a)} y={0} width={Math.max(1, T(span.b) - T(span.a))} height={H} className="wc-cspan" />
        <line x1={P} x2={W - P} y1={Y(0)} y2={Y(0)} className="wc-czero" />
        {norm.map((v, i) => (
          <polyline key={xs[i].id} className="wc-cline" fill="none" stroke={LINE_COLORS[i % LINE_COLORS.length]} strokeWidth={1.3}
            points={v.map((y, j) => (y === null ? "" : `${X(j)},${Y(y)}`)).filter(Boolean).join(" ")}><title>{xs[i].name}</title></polyline>
        ))}
        {xs.map((x, i) => x.t !== undefined && <line key={`t${x.id}`} x1={T(x.t)} x2={T(x.t)} y1={H - P - 8} y2={H - P} stroke={LINE_COLORS[i % LINE_COLORS.length]} strokeWidth={2} />)}
        {hover !== null && hover >= 0 && hover < n && <line x1={X(hover)} x2={X(hover)} y1={0} y2={H} className="wc-chover" />}
      </svg>
      <figcaption className="hint">{at === null ? t("wcPlotHint")
        : <><bdi dir="ltr">{fmtNum(at - span.a, lang, 3)}</bdi> {t("seconds")}: {xs.slice(0, 8).map((x, i) => {
          const v = x.spark?.[hover!];
          return <span key={x.id} style={{ color: LINE_COLORS[i % LINE_COLORS.length] }}> <bdi dir="ltr">{x.name} {v === null || v === undefined ? "–" : fmtNum(v, lang, 4)}</bdi></span>;
        })}</>}</figcaption>
    </figure>
  );
}

function Spark({ v: all, up }: { v: (number | null)[]; up: boolean }) {
  const v = all.length > 40 ? all.filter((_, i) => i % Math.ceil(all.length / 40) === 0) : all;
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
