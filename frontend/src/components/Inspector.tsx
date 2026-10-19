import type { RunInfo } from "../api";
import { useEffect, useState } from "react";
import { api, type LimitResult, type Stats } from "../api";
import { fileMark, showFileTags, actions, activeTab, rangeKey, signalName, TRACE_COLORS, useApp, type PlotSignal } from "../store";
import { fmtInt, fmtNum, useT } from "../i18n";
import { inkOn, labelsOf, labelText, stateColor } from "../values";
import { Icon } from "../icons";
import { unitOf } from "../units";

/** 10 significant digits: hides floating-point noise such as 4.596540300000117 */
const clean = (v: number) => String(Number(v.toPrecision(10)));

/** T10: a state signal (flight mode, gear...) as its segments. A row zooms to its segment and
 *  puts the two cursors on its edges - the "Between cursors" statistics above then show that
 *  segment (no second statistics mechanism). Times include the signal's time offset in the plot. */
function Segments({ sig, tOffset }: { sig: string; tOffset: number }) {
  const t = useT();
  const lang = useApp((s) => s.lang);
  const theme = useApp((s) => s.theme);
  const dataVersion = useApp((s) => s.dataVersion);
  const [data, setData] = useState<Awaited<ReturnType<typeof api.segments>> | null>(null);
  const [open, setOpen] = useState(false);
  useEffect(() => {
    let cancel = false;
    api.segments(sig).then((r) => { if (!cancel) setData(r); }).catch(() => { if (!cancel) setData(null); });
    return () => { cancel = true; };
  }, [sig, dataVersion]);
  if (!data || !data.segments.length) return null;
  const name = (x: { value: number; label: string | null }) => x.label ?? fmtNum(x.value, lang, 6);
  const dur = (d: number) => `${fmtNum(d, lang, 4)} s`;
  return (
    <div className="segments">
      <button className="linkbtn seg-toggle" aria-expanded={open} onClick={() => setOpen(!open)}>
        {t("segments", { n: data.total })}</button>
      <div className="seg-totals">
        {data.byValue.map((v) => (
          <span key={v.value} className="seg-total" title={t("segTotalHint", { n: v.count })}>
            <i style={{ background: stateColor(v.value, theme) }} />{name(v)} <b>{dur(v.duration)}</b></span>
        ))}
      </div>
      {open && (
        <ol className="seg-list">
          {data.segments.map((g, i) => (
            <li key={i}>
              <button onClick={() => actions.showSpan(g.t0 + tOffset, g.t1 + tOffset)} title={t("segShow")}>
                <i style={{ background: stateColor(g.value, theme) }} /><span className="seg-name">{name(g)}</span>
                <span className="seg-time">{fmtNum(g.t0 + tOffset, lang, 6)}</span><span className="seg-dur">{dur(g.t1 - g.t0)}</span>
              </button>
            </li>
          ))}
          {data.total > data.segments.length && <li className="hint">{t("segMore", { n: data.total - data.segments.length })}</li>}
        </ol>
      )}
    </div>
  );
}

/** An optional number: empty = none (a limit that is not set). Committed on Enter / leaving. */
function OptNum({ value, onCommit, label }: { value: number | null | undefined; onCommit: (v: number | null) => void; label: string }) {
  const [text, setText] = useState(value == null ? "" : String(value));
  useEffect(() => setText(value == null ? "" : String(value)), [value]);
  const commit = () => {
    const v = text.trim() === "" ? null : Number(text.replace(",", "."));
    if (v === null || Number.isFinite(v)) onCommit(v); else setText(value == null ? "" : String(value));
  };
  return <input aria-label={label} placeholder="—" value={text} onChange={(e) => setText(e.target.value)} onBlur={commit}
    onKeyDown={(e) => { if (e.key === "Enter") (e.target as HTMLInputElement).blur(); }} inputMode="decimal" />;
}

/** T13: limits of the selected signal and their result. Checked over the same range as the
 *  statistics (between the cursors when both are on, else the whole signal). A violation row
 *  zooms to it (showSpan). */
function Limits({ plotId, ps, region }: { plotId: string; ps: PlotSignal; region: [number, number] | null }) {
  const t = useT();
  const lang = useApp((s) => s.lang);
  const dataVersion = useApp((s) => s.dataVersion);
  const lo = ps.limits?.lo ?? null, hi = ps.limits?.hi ?? null;
  const [res, setRes] = useState<LimitResult | null>(null);
  useEffect(() => {
    if (lo === null && hi === null) { setRes(null); return; }
    let cancel = false;
    api.limits([{ id: ps.sig, lo, hi, scale: ps.scale, offset: ps.offset, tOffset: ps.tOffset ?? 0 }], region?.[0] ?? null, region?.[1] ?? null)
      .then((r) => { if (!cancel) setRes(r.results[ps.sig] ?? null); }).catch(() => { if (!cancel) setRes(null); });
    return () => { cancel = true; };
  }, [ps.sig, lo, hi, ps.scale, ps.offset, ps.tOffset, region?.[0], region?.[1], dataVersion]);
  const set = (k: "lo" | "hi", v: number | null) => {
    const next = { lo, hi, [k]: v };
    actions.updateSignal(plotId, ps.sig, { limits: next.lo === null && next.hi === null ? undefined : next });
  };
  return (
    <div className="limits">
      <div className="field"><label>{t("limits")}</label>
        <span className="lim-inputs">
          <OptNum label={t("limitLo")} value={lo} onCommit={(v) => set("lo", v)} /><span aria-hidden="true">…</span>
          <OptNum label={t("limitHi")} value={hi} onCommit={(v) => set("hi", v)} />
        </span></div>
      {res && (res.pass
        ? <p className="lim-result pass">✓ {t("limitPass")}</p>
        : <>
            <p className="lim-result fail">✗ {t("limitFail", { n: res.violations, s: fmtNum(res.timeOutside, lang, 3) })}
              {res.worst !== null && <> · {t("limitWorst", { v: fmtNum(res.worst, lang, 4), t: fmtNum(res.worstT, lang, 6) })}</>}</p>
            <ol className="seg-list">
              {res.spans.slice(0, 50).map(([a, b], i) => (
                <li key={i}><button onClick={() => actions.showSpan(a, b)} title={t("segShow")}>
                  <span className="seg-name">{fmtNum(a, lang, 6)}</span><span className="seg-dur">{fmtNum(b - a, lang, 3)} s</span></button></li>
              ))}
            </ol>
          </>)}
    </div>
  );
}

function NumInput({ value, onCommit, label }: { value: number; onCommit: (v: number) => void; label: string }) {
  const [txt, setTxt] = useState(clean(value));
  useEffect(() => setTxt(clean(value)), [value]);
  return (
    <input className="num" aria-label={label} value={txt} inputMode="decimal"
      onChange={(e) => setTxt(e.target.value)}
      onBlur={() => { const v = Number(txt); if (Number.isFinite(v) && txt !== clean(value)) onCommit(v); else setTxt(clean(value)); }}
      onKeyDown={(e) => { if (e.key === "Enter") (e.target as HTMLInputElement).blur(); }} />
  );
}

/** Number field for batch editing: shows the shared value, or "mixed" when values differ. */
function BatchInput({ value, onCommit, label }: { value: number | null; onCommit: (v: number) => void; label: string }) {
  const t = useT();
  const [txt, setTxt] = useState(value === null ? "" : String(value));
  useEffect(() => setTxt(value === null ? "" : String(value)), [value]);
  return (
    <input className="num" aria-label={label} value={txt} inputMode="decimal" placeholder={value === null ? t("mixed") : ""}
      onChange={(e) => setTxt(e.target.value)}
      onBlur={() => { const v = Number(txt); if (txt.trim() !== "" && Number.isFinite(v) && v !== value) onCommit(v); else setTxt(value === null ? "" : String(value)); }}
      onKeyDown={(e) => { if (e.key === "Enter") (e.target as HTMLInputElement).blur(); }} />
  );
}

export default function Inspector() {
  const t = useT();
  const lang = useApp((s) => s.lang);
  const ws = useApp((s) => s.ws);
  const runs = useApp((s) => s.runs);
  const cursor = useApp((s) => s.cursor);
  const cvals = useApp((s) => s.cvals);
  const themeName = useApp((s) => s.theme);
  const stylePill = (code: number | null): React.CSSProperties => {
    if (code === null || !Number.isFinite(code)) return {};
    const bg = stateColor(code, themeName);
    return { background: bg, color: inkOn(bg) };
  };
  const scope = useApp((s) => s.inspectorScope);
  const selected = useApp((s) => s.selected);
  const multi = useApp((s) => s.multi);
  const valuesOnPlot = useApp((s) => s.valuesOnPlot);
  const ranges = useApp((s) => s.ranges);
  const dataVersion = useApp((s) => s.dataVersion);
  const [stats, setStats] = useState<Record<string, Stats>>({});
  const [statsLoading, setStatsLoading] = useState(false);
  const [lazyDiscrete, setLazyDiscrete] = useState<Record<string, boolean>>({});

  const tab = activeTab(ws);
  const plots = scope === "all" ? tab.plots : tab.plots.slice(tab.active, tab.active + 1);
  const rows: { plotTitle: string; s: PlotSignal }[] = plots.flatMap((p) =>
    p.signals.map((s) => ({ plotTitle: p.title || t("plotTitle", { n: tab.plots.indexOf(p) + 1 }), s })));

  const activePlot = tab.plots[tab.active];
  const visible = activePlot ? ranges[rangeKey(tab, activePlot)] ?? null : null;
  const region: [number, number] | null = cursor.on && cursor.dual && cursor.t1 !== null && cursor.t2 !== null
    ? [Math.min(cursor.t1, cursor.t2), Math.max(cursor.t1, cursor.t2)] : visible;
  const statSigs = activePlot?.signals.map((s) => s.sig) ?? [];
  const statKey = statSigs.join("|");
  /* statistics only while a state signal of this plot has a chosen value ("while MODE = LOITER") */
  const [where, setWhere] = useState<{ sig: string; value: number } | null>(null);
  const stateSigs = (activePlot?.signals ?? []).filter((ps) => ps.state || labelsOf(runs, ps.sig));
  const [stateVals, setStateVals] = useState<Record<string, number[]>>({});
  const stateKey = stateSigs.map((x) => x.sig).join("|");
  useEffect(() => {
    if (where && !stateSigs.some((x) => x.sig === where.sig)) setWhere(null);
    for (const ps of stateSigs) {
      const lab = labelsOf(runs, ps.sig);
      if (lab || stateVals[ps.sig]) continue;
      api.states([ps.sig], null, null, 400).then((r) => {
        const pts = r.states[ps.sig]?.points ?? [];
        const vs = Array.from(new Set(pts.map((p) => p[1]).filter((v): v is number => v !== null))).sort((a, b) => a - b).slice(0, 60);
        setStateVals((m) => ({ ...m, [ps.sig]: vs }));
      }).catch(() => {});
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stateKey, dataVersion]);
  const whereOptions = stateSigs.flatMap((ps) => {
    const lab = labelsOf(runs, ps.sig);
    const vals = lab ? Object.keys(lab).map(Number) : stateVals[ps.sig] ?? [];
    return vals.map((v) => ({ sig: ps.sig, value: v, label: `${ps.label || signalName(runs, ps.sig, false)} = ${labelText(lab, v) ?? fmtNum(v, lang)}` }));
  });

  useEffect(() => {
    if (!statSigs.length) { setStats({}); return; }
    let cancel = false;
    setStatsLoading(true);
    const h = window.setTimeout(() => {
      const groups = new Map<number, string[]>();
      (activePlot?.signals ?? []).forEach((ps) => { const o = ps.tOffset ?? 0; groups.set(o, [...(groups.get(o) ?? []), ps.sig]); });
      const stOff = where ? (activePlot?.signals.find((p) => p.sig === where.sig)?.tOffset ?? 0) : 0;
      Promise.all(Array.from(groups, ([off, sigs]) => api.stats(sigs, region ? region[0] - off : null, region ? region[1] - off : null,
        where ? { state: where.sig, values: [where.value], offset: stOff - off } : null)))
        .then((rs) => { if (!cancel) setStats(Object.assign({}, ...rs.map((r) => r.stats))); })
        .catch(() => {}).finally(() => { if (!cancel) setStatsLoading(false); });
    }, 150);
    return () => { cancel = true; window.clearTimeout(h); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statKey, region?.[0], region?.[1], dataVersion, (activePlot?.signals ?? []).map((p) => p.tOffset ?? 0).join("|"), where?.sig, where?.value]);

  // wide files skip discrete detection at load; ask for the selected signal only
  useEffect(() => {
    const sig = selected?.sig;
    if (!sig || sig in lazyDiscrete) return;
    const info = runs.flatMap((r) => r.signals).find((x) => x.id === sig);
    if (info && (info.discrete === null || info.discrete === undefined) && !sig.startsWith("derived/")) {
      api.discrete(sig).then((r) => setLazyDiscrete((m) => ({ ...m, [sig]: r.discrete }))).catch(() => {});
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected?.sig]);

  const sel = selected ? tab.plots.find((p) => p.id === selected.plotId)?.signals.find((s) => s.sig === selected.sig) : undefined;
  const dual = cursor.on && cursor.dual && cursor.t2 !== null;

  const copyStats = async () => {
    if (!activePlot) return;
    const head = ["signal", "min", "max", "mean", "rms", "std", "p2p", "samples"];
    const lines = [head.join("\t")].concat(activePlot.signals.map((s) => {
      const st = stats[s.sig];
      const k = Math.abs(s.scale), tr = (v: number) => v * s.scale + s.offset;
      return [s.label || signalName(runs, s.sig, false), st ? Math.min(tr(st.min), tr(st.max)) : "", st ? Math.max(tr(st.min), tr(st.max)) : "",
        st ? tr(st.mean) : "", st ? st.rms * k : "", st ? st.std * k : "", st ? st.peak_to_peak * k : "", st?.samples ?? ""].join("\t");
    }));
    try { await navigator.clipboard.writeText(lines.join("\n")); useApp.getState().toast({ kind: "info", text: t("copiedTable") }); }
    catch { useApp.getState().toast({ kind: "error", text: t("copyFailed") }); }
  };
  const setT = (k: "t1" | "t2", v: number) => useApp.setState({ cursor: { ...useApp.getState().cursor, [k]: v } });

  return (
    <aside className="inspector" aria-label="Inspector">
      <div className="section">
        <h3>
          {t("cursorValues")}
          <span className="seg" role="group">
            <button className={scope === "active" ? "on" : ""} onClick={() => useApp.setState({ inspectorScope: "active" })}>{t("activePlotOnly")}</button>
            <button className={scope === "all" ? "on" : ""} onClick={() => useApp.setState({ inspectorScope: "all" })}>{t("allPlots")}</button>
          </span>
        </h3>
        {!cursor.on ? <p className="hint">{t("cursorOff")}</p> : (
          <>
            <label className="acheck" style={{ marginBottom: 6 }}>
              <input type="checkbox" checked={valuesOnPlot} onChange={(e) => useApp.setState({ valuesOnPlot: e.target.checked })} />{t("valuesOnPlot")}</label>
            <div className="ctime"><span className="lbl">T1</span>
              <NumInput label="T1" value={cursor.t1 ?? 0} onCommit={(v) => setT("t1", v)} /></div>
            {dual && <>
              <div className="ctime"><span className="lbl">T2</span>
                <NumInput label="T2" value={cursor.t2 ?? 0} onCommit={(v) => setT("t2", v)} /></div>
              <div className="ctime"><span className="lbl">ΔT</span>
                <span className="num">{fmtNum((cursor.t2 ?? 0) - (cursor.t1 ?? 0), lang, 7)}</span></div>
            </>}
            {rows.length > 0 && (
              <table className={`vals${dual ? " dualtbl" : ""}`}>
                <thead><tr><th></th><th>T1</th>{dual && <><th>T2</th><th>Δ</th><th>{t("slope")}</th></>}</tr></thead>
                <tbody>
                  {rows.map(({ s }) => {
                    const [a, b] = cvals[s.sig] ?? [null, null];
                    const v1 = a === null ? null : a * s.scale + s.offset;
                    const v2 = b === null ? null : b * s.scale + s.offset;
                    const labels = labelsOf(runs, s.sig);
                    const name = <td title={signalName(runs, s.sig) + (unitOf(signalName(runs, s.sig, false)) ? ` [${unitOf(signalName(runs, s.sig, false))}]` : "")}><span className="sw" style={{ background: s.color }} /><FileTag runs={runs} sig={s.sig} />{s.label || signalName(runs, s.sig, false)}</td>;
                    if (labels) {        // text values: the text at each cursor; a difference means nothing here
                      const l1 = labelText(labels, a) ?? fmtNum(a, lang), l2 = labelText(labels, b) ?? fmtNum(b, lang);
                      return (
                        <tr key={s.sig + s.color} className="text-row">
                          {name}
                          <td title={l1}><span className="state-pill" style={stylePill(a)}>{l1}</span></td>
                          {dual && <><td title={l2}><span className="state-pill" style={stylePill(b)}>{l2}</span></td>
                            <td colSpan={2}>{a !== null && b !== null ? (a === b ? "=" : "≠") : "—"}</td></>}
                        </tr>
                      );
                    }
                    return (
                      <tr key={s.sig + s.color}>
                        {name}
                        <td title={fmtNum(v1, lang, 10)}>{fmtNum(v1, lang, dual ? 4 : 6)}</td>
                        {dual && <><td title={fmtNum(v2, lang, 10)}>{fmtNum(v2, lang, 4)}</td><td>{v1 !== null && v2 !== null ? fmtNum(v2 - v1, lang, 4) : "—"}</td>
                          <td>{v1 !== null && v2 !== null && cursor.t2 !== cursor.t1 ? fmtNum((v2 - v1) / ((cursor.t2 ?? 0) - (cursor.t1 ?? 0)), lang, 4) : "—"}</td></>}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </>
        )}
      </div>

      <div className="section">
        <h3>{t("statistics")}<span style={{ marginInlineStart: "auto", color: "var(--faint)", fontWeight: 400 }}>
          {dual ? t("statsRegion") : t("statsVisible")}</span>
          <button className="iconbtn sm" title={t("copyStats")} aria-label={t("copyStats")} disabled={!statSigs.length} onClick={copyStats}><Icon.Copy /></button></h3>
        {whereOptions.length > 0 && (
          <label className="afield stats-where"><span>{t("statsWhere")}</span>
            <select value={where ? `${where.sig}|${where.value}` : ""} onChange={(e) => {
              const v = e.target.value;
              if (!v) { setWhere(null); return; }
              const i = v.lastIndexOf("|");
              setWhere({ sig: v.slice(0, i), value: Number(v.slice(i + 1)) });
            }}>
              <option value="">{t("statsWhereAll")}</option>
              {whereOptions.map((o) => <option key={`${o.sig}|${o.value}`} value={`${o.sig}|${o.value}`}>{o.label}</option>)}
            </select></label>
        )}
        {where && Object.values(stats)[0]?.segments !== undefined && (
          <p className="hint stats-where-note">{t("statsWhereNote", { n: Object.values(stats)[0]!.segments!, s: fmtNum(Object.values(stats)[0]!.duration, lang, 4) })}</p>
        )}
        {!statSigs.length ? <p className="hint">{t("emptyPlot")}</p> : (
          <table className="vals stats">
            <thead><tr><th>{t("minimal")}</th><th>{t("maximal")}</th><th>{t("mean")}</th><th>{t("rms")}</th></tr></thead>
            {activePlot.signals.map((s) => {
              const st = stats[s.sig];
              const tr = (v?: number) => (v === undefined ? null : v * s.scale + s.offset);
              const vals = [st && Math.min(tr(st.min)!, tr(st.max)!), st && Math.max(tr(st.min)!, tr(st.max)!),
                tr(st?.mean), st ? st.rms * Math.abs(s.scale) : null];
              return (
                <tbody key={s.sig} title={st ? `${t("std")}: ${fmtNum(st.std * Math.abs(s.scale), lang)} · ${t("p2p")}: ${fmtNum(st.peak_to_peak * Math.abs(s.scale), lang)} · ${t("count")}: ${fmtInt(st.samples, lang)}` : ""}>
                  <tr className="name-row"><td colSpan={4}><span className="sw" style={{ background: s.color }} /><FileTag runs={runs} sig={s.sig} />{s.label || signalName(runs, s.sig, false)}</td></tr>
                  {labelsOf(runs, s.sig)
                    ? <tr><td colSpan={4} className="hint">{t("textStatsNote", { n: Object.keys(labelsOf(runs, s.sig)!).length })}</td></tr>
                    : <tr>{vals.map((v, i) => <td key={i} title={fmtNum(v ?? null, lang, 10)}>{!st && statsLoading ? "…" : fmtNum(v ?? null, lang, 4)}</td>)}</tr>}
                </tbody>
              );
            })}
          </table>
        )}
      </div>

      {multi.length > 1 && (
        <div className="section">
          <h3>{t("nSelected", { n: multi.length })}
            <button className="linklike" style={{ marginInlineStart: "auto", fontWeight: 400 }} onClick={() => useApp.setState({ multi: [] })}>{t("clearSelection")}</button></h3>
          <p className="hint" style={{ fontSize: "0.923rem", margin: "0 0 8px" }}>{t("batchHint")}</p>
          {(() => {
            const items = multi.map((m) => ({ m, s: tab.plots.find((p) => p.id === m.plotId)?.signals.find((x) => x.sig === m.sig) })).filter((x) => x.s);
            const same = (k: "scale" | "offset" | "width" | "tOffset") => {
              const vals = items.map((x) => (x.s as any)[k] ?? 0);
              return vals.every((v) => v === vals[0]) ? vals[0] : null;
            };
            const field = (k: "scale" | "offset" | "width" | "tOffset", label: string) => (
              <div className="field" key={k}><label>{label}</label>
                <BatchInput label={label} value={same(k)} onCommit={(v) => actions.updateSignals(multi, { [k]: k === "width" ? Math.max(0.5, Math.min(6, v)) : v })} /></div>
            );
            return <>
              {field("scale", t("scale"))}{field("offset", t("offset"))}{field("tOffset", t("signalTimeOffset"))}{field("width", t("width"))}
              <div className="field"><label>{t("display")}</label>
                <span className="seg">
                  <button onClick={() => actions.updateSignals(multi, { state: false })}>{t("asLine")}</button>
                  <button onClick={() => actions.updateSignals(multi, { state: true })}>{t("asStates")}</button>
                </span></div>
              <div className="arow">
                <button className="btn outline" onClick={() => useApp.setState({ panel: "analysis" })}>{t("batchDerived")}</button>
                <button className="btn outline" onClick={() => actions.removeSignals(multi)}>{t("remove")}</button>
              </div>
            </>;
          })()}
        </div>
      )}

      <div className="section">
        <h3>{t("properties")}</h3>
        {!sel || !selected ? <p className="hint">{t("selectSignalHint")}</p> : (
          <div key={selected.plotId + selected.sig}>
            <div className="field"><label>{t("label")}</label>
              <input defaultValue={sel.label ?? ""} placeholder={signalName(runs, sel.sig, false)}
                onBlur={(e) => actions.updateSignal(selected.plotId, sel.sig, { label: e.target.value.trim() || undefined })}
                onKeyDown={(e) => { if (e.key === "Enter") (e.target as HTMLInputElement).blur(); }} /></div>
            <div className="field"><label>{t("color")}</label>
              <div className="swatches">
                {TRACE_COLORS.map((c) => (
                  <button key={c} className={c === sel.color ? "on" : ""} style={{ background: c }} aria-label={c}
                    onClick={() => actions.updateSignal(selected.plotId, sel.sig, { color: c })} />
                ))}
              </div></div>
            <div className="field"><label>{t("display")}</label>
              <span className="seg">
                <button className={!sel.state ? "on" : ""} onClick={() => actions.updateSignal(selected.plotId, sel.sig, { state: false })}>{t("asLine")}</button>
                <button className={sel.state ? "on" : ""} onClick={() => actions.updateSignal(selected.plotId, sel.sig, { state: true })}>{t("asStates")}</button>
              </span></div>
            {!sel.state && (lazyDiscrete[sel.sig] || runs.some((r) => r.signals.some((x) => x.id === sel.sig && x.discrete))) &&
              <p className="hint" style={{ margin: "-2px 0 10px", fontSize: 12 }}>{t("looksDiscrete")}</p>}
            {sel.state && <Segments sig={sel.sig} tOffset={sel.tOffset ?? 0} />}
            <div className="field"><label>{t("width")}</label>
              <NumInput label={t("width")} value={sel.width} onCommit={(v) => actions.updateSignal(selected.plotId, sel.sig, { width: Math.max(0.5, Math.min(6, v)) })} /></div>
            <div className="field"><label>{t("scale")}</label>
              <NumInput label={t("scale")} value={sel.scale} onCommit={(v) => actions.updateSignal(selected.plotId, sel.sig, { scale: v })} /></div>
            <div className="field"><label>{t("offset")}</label>
              <NumInput label={t("offset")} value={sel.offset} onCommit={(v) => actions.updateSignal(selected.plotId, sel.sig, { offset: v })} /></div>
            {!sel.state && <Limits plotId={selected.plotId} ps={sel} region={region} />}
            <div className="field"><label>{t("signalTimeOffset")}</label>
              <NumInput label={t("signalTimeOffset")} value={sel.tOffset ?? 0} onCommit={(v) => actions.updateSignal(selected.plotId, sel.sig, { tOffset: v })} /></div>
            <button className="btn outline" onClick={() => actions.removeSignal(selected.plotId, sel.sig)}>{t("remove")}</button>
          </div>
        )}
      </div>
      <div className="section notes-section">
        <h3>{t("notes")}
          <button className="iconbtn sm" style={{ marginInlineStart: "auto" }} onClick={() => actions.addNoteAtCursor()}
            title={`${t("noteAdd")} (N)`} aria-label={t("noteAdd")}><Icon.Plus /></button></h3>
        {!(ws.notes ?? []).length ? <p className="hint">{t("notesEmpty")}</p> : (
          <ol className="notes-list">
            {[...(ws.notes ?? [])].sort((a, b) => a.t - b.t).map((n) => (
              <li key={n.id}>
                <button className="pchange" onClick={() => actions.goToTime(n.t)} title={t("logGoTo")}>{fmtNum(n.t, lang, 6)}</button>
                <span className="note-text" onDoubleClick={() => actions.editNote(n.id)}>{n.text}</span>
                <button className="iconbtn sm" onClick={() => actions.editNote(n.id)} aria-label={t("noteEdit")} title={t("noteEdit")}><Icon.Edit /></button>
                <button className="iconbtn sm" onClick={() => actions.removeNote(n.id)} aria-label={t("remove")} title={t("remove")}><Icon.Trash /></button>
              </li>
            ))}
          </ol>
        )}
      </div>
    </aside>
  );
}

/** T46: the file's tag before a signal name when several files are open. */
function FileTag({ runs, sig }: { runs: RunInfo[]; sig: string }) {
  const m = showFileTags(runs) ? fileMark(runs, sig) : null;
  return m ? <span className="file-tag" style={{ ["--tag" as string]: m.color, marginInlineEnd: 4 }}>{m.tag}</span> : null;
}
