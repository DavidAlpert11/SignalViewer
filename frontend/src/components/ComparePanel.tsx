import { useEffect, useMemo, useRef, useState } from "react";
import { api, type CompareAllRow, type CompareRow } from "../api";
import { activeTab, fileLabel, pickPath, placePlot, tabFullMessage, TRACE_COLORS, uid, useApp } from "../store";
import { fmtNum, translate, useT } from "../i18n";
import { startJob } from "../files";
import { Icon } from "../icons";
import { exactMatch } from "../fuzzy";

/* ---------------------------------------------------------------------------
   Compare panel. Choosing two or more files immediately lists every shared
   signal ranked by similarity. The list is computed in the background:
   debounced, cancelled on the server when the choice changes, cached per choice.
--------------------------------------------------------------------------- */
type Bucket = "all" | "diff" | "close" | "same";
const bucketOf = (m: number | null | undefined): Exclude<Bucket, "all"> =>
  m === null || m === undefined ? "diff" : m >= 99 ? "same" : m >= 90 ? "close" : "diff";
const LIST_POINTS = 20_000;          // per signal for the list (the detail view uses full detail)
const PAGE = 120;
const cache = new Map<string, CompareAllRow[]>();      // per file choice / settings / data version

/** Where in time the difference is: the SHAPE of the difference profile. A uniform
 *  difference is a flat line (not a full block that would look like a large error). */
function Spark({ values, bucket }: { values?: (number | null)[] | null; bucket: string }) {
  const vs = (values ?? []).map((v) => v ?? 0);
  if (vs.length < 2) return <svg className="spark" viewBox="0 0 64 14" aria-hidden="true" />;
  const lo = Math.min(...vs), hi = Math.max(...vs);
  const varied = hi > 0 && (hi - lo) / hi > 0.3;
  const y = (v: number) => (varied ? 13 - ((v - lo) / (hi - lo)) * 11 : 9);
  const pts = vs.map((v, i) => `${((i / (vs.length - 1)) * 64).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  return (
    <svg className={`spark ${bucket}`} viewBox="0 0 64 14" preserveAspectRatio="none" aria-hidden="true">
      <polyline points={pts} />
    </svg>
  );
}

export default function ComparePanel() {
  const t = useT();
  const lang = useApp((s) => s.lang);
  const allRuns = useApp((s) => s.runs);
  const dataVersion = useApp((s) => s.dataVersion);
  const runs = useMemo(() => allRuns.filter((r) => r.format !== "derived"), [allRuns]);
  // defaults computed on the FIRST render (no flash of "mean" while effects catch up)
  const [chosen, setChosen] = useState<string[]>(() => runs.map((r) => r.id));
  // default baseline: the first chosen file. Against the mean, two files would each show
  // only half of their real difference, which understates exactly what the user asks about.
  const [baseline, setBaseline] = useState(() => runs[0]?.id ?? "");
  const [alignment, setAlignment] = useState("linear");
  const [tolAbs, setTolAbs] = useState("");
  const [tolPct, setTolPct] = useState("");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [sim, setSim] = useState<CompareAllRow[] | null>(null);
  const [progress, setProgress] = useState<number | null>(null);
  const [simError, setSimError] = useState("");
  const [sort, setSort] = useState<"worst" | "best">("worst");
  const [bucket, setBucket] = useState<Bucket>("all");
  const [q, setQ] = useState("");
  const [limit, setLimit] = useState(PAGE);
  const [signal, setSignal] = useState("");
  const [rows, setRows] = useState<CompareRow[] | null>(null);
  const [busy, setBusy] = useState(false);
  const jobRef = useRef<{ cancel: () => void } | null>(null);

  useEffect(() => {   // keep the selection valid as files open and close
    setChosen((cur) => {
      const ids = runs.map((r) => r.id);
      const kept = cur.filter((c) => ids.includes(c));
      return kept.length >= 2 || ids.length < 2 ? (kept.length ? kept : ids) : ids;
    });
  }, [runs]);
  useEffect(() => { if (baseline !== "mean" && !chosen.includes(baseline)) setBaseline(chosen[0] ?? ""); }, [chosen, baseline]);

  const num = (v: string) => (v.trim() === "" || !Number.isFinite(+v) ? null : +v);
  const tolSet = num(tolAbs) !== null || num(tolPct) !== null;
  const runName = (rid: string) => fileLabel(allRuns, rid);
  const runColor = (rid: string) => TRACE_COLORS[Math.max(0, chosen.indexOf(rid)) % TRACE_COLORS.length];

  /* ------------- similarity list: debounced, cancellable, cached ------------- */
  const key = `${[...chosen].sort().join(",")}|${baseline}|${alignment}|${tolAbs}|${tolPct}|${dataVersion}`;
  useEffect(() => {
    jobRef.current?.cancel();                // a newer choice replaces any running computation
    jobRef.current = null;
    setSimError("");
    if (chosen.length < 2 || !baseline) { setSim(null); setProgress(null); return; }
    const hit = cache.get(key);
    if (hit) { setSim(hit); setProgress(null); return; }
    setProgress(0);
    const h = window.setTimeout(() => {
      const job = startJob<{ signals: CompareAllRow[] }>("compareAll",
        { runs: chosen, baselineRun: baseline, alignment, tolAbs: num(tolAbs), tolPct: num(tolPct), points: LIST_POINTS },
        (p) => setProgress(p));
      jobRef.current = job;
      job.result.then((r) => {
        if (!r || jobRef.current !== job) return;            // cancelled or superseded
        cache.set(key, r.signals);
        if (cache.size > 8) cache.delete(cache.keys().next().value!);
        setSim(r.signals); setProgress(null); setLimit(PAGE);
      }).catch((e) => { if (jobRef.current === job) { setSimError(String((e as Error).message)); setProgress(null); } });
    }, 350);                                  // wait until the user stops changing the choice
    return () => window.clearTimeout(h);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  useEffect(() => () => jobRef.current?.cancel(), []);       // leaving the panel stops the work

  const counts = useMemo(() => {
    const c = { all: 0, diff: 0, close: 0, same: 0 };
    (sim ?? []).forEach((x) => { if (!x.error) { c.all++; c[bucketOf(x.matchPct)]++; } });
    return c;
  }, [sim]);
  const list = useMemo(() => {
    const xs = (sim ?? []).filter((x) => !x.error && (bucket === "all" || bucketOf(x.matchPct) === bucket) && (!q.trim() || exactMatch(x.name, q)));
    return xs.sort((a, b) => (sort === "worst" ? 1 : -1) * ((a.matchPct ?? 0) - (b.matchPct ?? 0)));
  }, [sim, bucket, q, sort]);

  /* ------------------------------ detail ------------------------------ */
  const detail = async (name: string, runsOf: string[]) => {
    setSignal(name);
    setBusy(true);
    try {
      const base = baseline !== "mean" && runsOf.includes(baseline) ? `${baseline}/${name}` : "mean";
      const r = await api.compare(runsOf.map((c) => `${c}/${name}`), base, alignment, num(tolAbs), num(tolPct));
      setRows(r.rows);
    } catch (e) { useApp.getState().toast({ kind: "error", text: String((e as Error).message) }); setRows(null); }
    finally { setBusy(false); }
  };
  const showInPlot = (name: string, runsOf: string[], newPlot: boolean) => {
    let full = false;
    useApp.getState().commit((ws) => {
      const tab = activeTab(ws);
      const signals = runsOf.map((rid) => ({ sig: `${rid}/${name}`, color: runColor(rid), width: 1.5, scale: 1, offset: 0 }));
      if (newPlot) {
        const at = placePlot(tab, { id: uid("p"), title: name, signals });
        if (at < 0) { full = true; return ws; }
        tab.active = at;
      } else {
        const p = tab.plots[tab.active];
        if (p) { p.signals = signals; p.title = p.title || ""; }     // flip through signals in the same plot
      }
      return ws;
    });
    if (full) tabFullMessage();
  };
  const pick = (x: CompareAllRow, e: React.MouseEvent) => {
    const rs = x.runs ?? chosen;
    showInPlot(x.name, rs, e.shiftKey);
    detail(x.name, rs);
  };
  const current = sim?.find((x) => x.name === signal);
  const detailRuns = current?.runs ?? chosen;

  const align = async (sid: string) => {
    if (baseline === "mean") return;
    const rid = sid.split("/")[0];
    const info = runs.find((r) => r.id === rid);
    if (!info) return;
    const { shift } = await api.shift(`${baseline}/${signal}`, sid);
    const before = info.timeOffset;
    await api.patchRun(rid, { timeOffset: before + shift });
    const bump = async () => useApp.setState({ runs: await api.listRuns(), dataVersion: useApp.getState().dataVersion + 1 });
    await bump();
    useApp.getState().toast({
      kind: "info", text: translate(lang, "shiftedBy", { name: info.name, s: fmtNum(shift, lang, 4) }),
      action: { label: t("undo"), run: async () => { await api.patchRun(rid, { timeOffset: before }); await bump(); detail(signal, detailRuns); } },
    });
    detail(signal, detailRuns);
  };
  const plotDiffs = async () => {
    setBusy(true);
    try {
      const ids = detailRuns.map((r) => `${r}/${signal}`);
      let base = baseline !== "mean" && detailRuns.includes(baseline) ? `${baseline}/${signal}` : "mean";
      if (base === "mean") base = (await api.createDerived("mean", ids, { alignment }, `mean(${signal})`)).id;
      const made: string[] = [];
      for (const id of ids) {
        if (id === base) continue;
        const r = await api.createDerived("sub", [id, base], { alignment }, `Δ ${signal} ${runName(id.split("/")[0])}`);
        made.push(r.id);
        useApp.setState({ runs: r.runs });
      }
      let full = false;
      useApp.getState().commit((ws) => {
        const tab = activeTab(ws);
        const at = placePlot(tab, { id: uid("p"), title: `Δ ${signal}`, signals: made.map((sig, i) => ({ sig, color: TRACE_COLORS[(i + 1) % TRACE_COLORS.length], width: 1.5, scale: 1, offset: 0 })) });
        if (at < 0) { full = true; return ws; }
        tab.active = at;
        return ws;
      });
      if (full) tabFullMessage();
    } catch (e) { useApp.getState().toast({ kind: "error", text: String((e as Error).message) }); }
    finally { setBusy(false); }
  };
  const exportList = async () => {
    const path = await pickPath({ mode: "save", title: t("exportResults"), exts: [".csv"], defaultName: "similarity.csv" });
    if (!path) return;
    const lines = ["signal,files,match_pct,error_pct,rms_diff,max_abs_diff,min_correlation,pass"]
      .concat(list.map((x) => [`"${x.name}"`, x.runs?.length ?? "", x.matchPct, x.worstRmsPct, x.worstRmsDiff, x.worstMaxAbs, x.minCorrelation, x.pass ?? ""].join(",")));
    const r = await api.saveText(path, lines.join("\n"));
    useApp.getState().toast({ kind: "info", text: translate(lang, "savedTo", { path: r.path }) });
  };

  if (runs.length < 2) return (
    <aside className="side"><div className="side-head"><h2>{t("compare")}</h2></div><p className="empty-note">{t("compareNeedsTwo")}</p></aside>
  );

  return (
    <aside className="side" aria-label={t("compare")}>
      <div className="side-head"><h2>{t("compare")}</h2></div>
      <div className="tree analysis cmp-panel">
        <div className="afield"><span>{t("runsToCompare")}</span>
          {runs.map((r) => (
            <label key={r.id} className="acheck">
              <input type="checkbox" checked={chosen.includes(r.id)}
                onChange={(e) => setChosen((c) => (e.target.checked ? [...c, r.id] : c.filter((x) => x !== r.id)))} />
              <span className="run-dot" style={{ background: chosen.includes(r.id) ? runColor(r.id) : "transparent" }} />
              <span className="nm">{runName(r.id)}</span>
            </label>
          ))}
        </div>
        <label className="afield"><span>{t("baseline")}</span>
          <select value={baseline} onChange={(e) => setBaseline(e.target.value)}>
            <option value="mean">{t("meanOfRuns")}</option>
            {runs.filter((r) => chosen.includes(r.id)).map((r) => <option key={r.id} value={r.id}>{runName(r.id)}</option>)}
          </select></label>

        {/* ---------------- similarity list ---------------- */}
        <div className="sim-head">
          <h3>{t("similarity")}</h3>
          <button className="linklike" onClick={() => setSort(sort === "worst" ? "best" : "worst")} title={t("sortToggle")}>
            {sort === "worst" ? t("leastSimilarFirst") : t("mostSimilarFirst")} ⇅</button>
        </div>
        {chosen.length < 2 && <p className="hint">{t("pickTwo")}</p>}
        {progress !== null && (
          <div className="sim-progress" role="progressbar" aria-valuenow={Math.round(progress * 100)} aria-label={t("similarity")}>
            <span style={{ width: `${Math.max(3, progress * 100)}%` }} />
          </div>
        )}
        {simError && <p className="hint err">{simError}</p>}
        {sim && (
          <>
            <div className="sim-pills" role="group">
              {(["all", "diff", "close", "same"] as Bucket[]).map((b) => (
                <button key={b} className={`pill ${b}${bucket === b ? " on" : ""}`} onClick={() => { setBucket(b); setLimit(PAGE); }}
                  title={t(`bucketHint_${b}` as never)}>{t(`bucket_${b}` as never)} <b>{counts[b]}</b></button>
              ))}
            </div>
            {counts.all > 12 && (
              <label className="filter sim-filter"><Icon.Search />
                <input value={q} onChange={(e) => { setQ(e.target.value); setLimit(PAGE); }} placeholder={t("searchSignals")} aria-label={t("searchSignals")} /></label>
            )}
            <div className="sim-list" role="list">
              {list.slice(0, limit).map((x) => {
                const b = bucketOf(x.matchPct);
                return (
                  <button key={x.name} role="listitem" className={`sim-row${signal === x.name ? " on" : ""}`} onClick={(e) => pick(x, e)}
                    title={`${x.name}\n${t("errorPct")}: ${fmtNum(x.worstRmsPct ?? null, lang, 3)}% · RMS Δ ${fmtNum(x.worstRmsDiff ?? null, lang, 4)} · max |Δ| ${fmtNum(x.worstMaxAbs ?? null, lang, 4)} · ${t("corr")} ${fmtNum(x.minCorrelation ?? null, lang, 4)}\n${t("simRowHint")}`}>
                    <span className="sim-name">{x.name}{x.pass === false && <span className="sim-fail" aria-label={t("fail")}>!</span>}</span>
                    <span className={`sim-pct ${b}`}>{fmtNum(x.matchPct ?? 0, lang, 3)}%</span>
                    <span className="sim-bar"><span className={b} style={{ width: `${Math.max(2, x.matchPct ?? 0)}%` }} /></span>
                    <Spark values={x.profile} bucket={b} />
                    <span className="sim-err">{t("errShort")} {fmtNum(x.worstRmsPct ?? null, lang, 2)}%</span>
                  </button>
                );
              })}
              {!list.length && <p className="hint">{t("noMatches", { q })}</p>}
              {list.length > limit && <button className="btn outline sm" onClick={() => setLimit(limit + PAGE)}>{t("showMore", { n: list.length - limit })}</button>}
            </div>
            <div className="arow wrap">
              <button className="btn outline" onClick={() => sim && useApp.setState({ compareTable: { rows: sim, baseline, fileCount: chosen.length, tol: tolSet } })}>{t("compareTableBtn")}</button>
              <button className="btn outline" onClick={exportList}>{t("exportResults")}</button>
            </div>
          </>
        )}

        {/* ---------------- selected signal ---------------- */}
        {signal && rows && (
          <div className="cmp-block">
            <h3 className="alist-head">{signal} <span className="muted">· {baseline === "mean" ? t("meanOfRuns") : runName(baseline)}</span></h3>
            <table className="vals cmp2">
              <thead><tr><th>{t("rmsDiff")}</th><th>{t("maxDiff")}</th><th>{t("corr")}</th>{tolSet && <th>{t("inTol")}</th>}</tr></thead>
              {rows.map((r) => (
                <tbody key={r.id}>
                  <tr className="name-row"><td colSpan={tolSet ? 4 : 3}>
                    <span className="run-dot" style={{ background: runColor(r.id.split("/")[0]) }} />
                    <span className="nm">{runName(r.id.split("/")[0])}</span>
                    {baseline !== "mean" && <button className="iconbtn sm act" title={t("alignInTime")} aria-label={t("alignInTime")} onClick={() => align(r.id)}><Icon.Link /></button>}
                  </td></tr>
                  <tr>
                    <td title={r.rmsPct !== undefined ? `${fmtNum(r.rmsPct, lang, 3)} %` : ""}>{fmtNum(r.rmsDiff, lang, 3)}</td>
                    <td>{fmtNum(r.maxAbsDiff, lang, 3)}</td>
                    <td>{fmtNum(r.correlation, lang, 4)}</td>
                    {tolSet && <td><span className={`pf ${r.pass ? "ok" : "bad"}`}>{fmtNum(r.withinPct, lang, 3)}%</span></td>}
                  </tr>
                </tbody>
              ))}
            </table>
            <div className="arow wrap">
              <button className="btn outline" disabled={busy} onClick={plotDiffs}>{t("plotDiffs")}</button>
            </div>
          </div>
        )}

        {/* ---------------- settings ---------------- */}
        <button className="sim-settings-toggle" aria-expanded={settingsOpen} onClick={() => setSettingsOpen(!settingsOpen)}>
          <Icon.Chevron className="chev" /> {t("compareSettings")}
          {(tolSet || alignment !== "linear") && <span className="tag">•</span>}
        </button>
        {settingsOpen && <>
          <div className="arow">
            <label className="afield"><span>{t("tolAbs")}</span><input inputMode="decimal" value={tolAbs} onChange={(e) => setTolAbs(e.target.value)} placeholder="—" /></label>
            <label className="afield"><span>{t("tolPct")}</span><input inputMode="decimal" value={tolPct} onChange={(e) => setTolPct(e.target.value)} placeholder="—" /></label>
          </div>
          <label className="afield"><span>{t("alignment")}</span>
            <select value={alignment} onChange={(e) => setAlignment(e.target.value)}>
              <option value="linear">{t("alignLinear")}</option><option value="nearest">{t("alignNearest")}</option>
            </select></label>
        </>}
      </div>
    </aside>
  );
}
