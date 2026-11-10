import DiffChart from "./DiffChart";
import { useEffect, useMemo, useRef, useState } from "react";
import { api, type CompareAllRow, type CompareRow, type TolEntry, type Tolerances } from "../api";
import TolFields from "./TolFields";
import { activeTab, fileLabel, fileMark, styledSignal, fitLayout, pickPath, placePlot, tabFullMessage, TRACE_COLORS, uid, useApp } from "../store";
import { isGolden, proposeBaseline, rememberTolerances, reportVerdict, setGolden, verdicts } from "../judge";
import { fmtNum, translate, useT } from "../i18n";
import { startJob } from "../files";
import { Icon } from "../icons";
import { exactMatch } from "../fuzzy";
import { showSegmentPlot, type SegmentChoice, type SegWindow } from "../segments";

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
const hasLimit = (e: TolEntry) => e.abs !== undefined || e.pct !== undefined || !!e.time;

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
  // default baseline: a file, not the mean (two files would each show only half of their real
  // difference) - 26.U4: a golden run, else a file named as the reference, else the first
  const [baseline, setBaseline] = useState(() => proposeBaseline(runs));
  const [alignment, setAlignment] = useState("linear");
  // 26.U5: every signal's tolerance and each signal's own (abs / pct / time - 1.21, SDI - / outside_pct / skip)
  const tols = useApp((s) => s.compareTol);
  const setTols = (x: Tolerances) => useApp.setState({ compareTol: x });
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [sim, setSim] = useState<CompareAllRow[] | null>(null);
  const [simKey, setSimKey] = useState("");          // 26.U4: the choice `sim` was computed for
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
  // T10b: compare over one segment (e.g. the 2nd AUTO) of every run instead of their common time
  const [over, setOver] = useState<"whole" | "segment">("whole");
  const [segState, setSegState] = useState("");
  const [segValues, setSegValues] = useState<{ value: number; label: string | null }[]>([]);
  const [segValue, setSegValue] = useState<number | null>(null);
  const [segOcc, setSegOcc] = useState(1);
  const [segWin, setSegWin] = useState<SegWindow[] | null>(null);

  useEffect(() => {   // keep the selection valid as files open and close
    setChosen((cur) => {
      const ids = runs.map((r) => r.id);
      const kept = cur.filter((c) => ids.includes(c));
      return kept.length >= 2 || ids.length < 2 ? (kept.length ? kept : ids) : ids;
    });
  }, [runs]);
  useEffect(() => { if (baseline !== "mean" && !chosen.includes(baseline)) setBaseline(chosen[0] ?? ""); }, [chosen, baseline]);
  // 26.U4: "judge this run" (the start card, a golden run) - these files, this baseline
  const judge = useApp((s) => s.compareJudge);
  useEffect(() => {
    if (!judge) return;
    setChosen(judge.runs.filter((r) => runs.some((x) => x.id === r)));
    setBaseline(judge.baseline); setOver("whole"); setSignal(""); setRows(null);
    useApp.setState({ compareJudge: null });
  }, [judge, runs]);
  const [, setGoldenTick] = useState(0);
  const basePath = runs.find((r) => r.id === baseline)?.path;
  const golden = isGolden(basePath);

  /* ------------- T10b segment: state signals shared by the chosen files ------------- */
  const stateNames = useMemo(() => {
    const count = new Map<string, number>();
    runs.filter((r) => chosen.includes(r.id)).forEach((r) => r.signals.forEach((x) => {
      if (x.labels || x.discrete) count.set(x.name, (count.get(x.name) ?? 0) + 1);
    }));
    return Array.from(count).filter(([, n]) => n >= 2).map(([nm]) => nm).sort();
  }, [runs, chosen]);
  useEffect(() => { if (over === "segment" && !stateNames.includes(segState)) setSegState(stateNames[0] ?? ""); }, [over, stateNames, segState]);
  useEffect(() => {                         // the values the state takes in any chosen file (with their text)
    if (over !== "segment" || !segState) { setSegValues([]); return; }
    let off = false;
    Promise.all(chosen.filter((rid) => runs.find((r) => r.id === rid)?.signals.some((x) => x.name === segState))
      .map((rid) => api.segments(`${rid}/${segState}`).then((r) => r.byValue).catch(() => [])))
      .then((all) => {
        if (off) return;
        const m = new Map<number, string | null>();
        all.flat().forEach((v) => { if (!m.has(v.value) || (!m.get(v.value) && v.label)) m.set(v.value, v.label); });
        const vals = Array.from(m, ([value, label]) => ({ value, label })).sort((a, b) => a.value - b.value);
        setSegValues(vals);
        setSegValue((cur) => (cur !== null && vals.some((v) => v.value === cur) ? cur : vals[0]?.value ?? null));
      });
    return () => { off = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [over, segState, chosen.join(","), dataVersion]);
  useEffect(() => {
    if (over !== "segment" || !segState || segValue === null) { setSegWin(null); return; }
    let off = false;
    api.segmentsAcross(chosen, segState, segValue, segOcc).then((r) => { if (!off) setSegWin(r.windows); }).catch(() => { if (!off) setSegWin(null); });
    return () => { off = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [over, segState, segValue, segOcc, chosen.join(","), dataVersion]);
  const valueText = (v: number | null) => { const x = segValues.find((s) => s.value === v); return x?.label ?? (v === null ? "" : String(v)); };
  const occText = (k: number) => (k === -1 ? t("occLast") : t("occNth", { n: k }));
  const segment: SegmentChoice | null = over === "segment" && segWin
    ? { title: `${segState} = ${valueText(segValue)} · ${occText(segOcc)}`,
        windows: Object.fromEntries(segWin.filter((w) => w.t0 !== undefined).map((w) => [w.run, [w.t0!, w.t1!] as [number, number]])) }
    : null;
  // in segment mode only the files where the segment was found take part
  const active = segment ? chosen.filter((rid) => segment.windows[rid]) : chosen;
  const segWaiting = over === "segment" && !segment;
  const tolSet = hasLimit(tols.default) || Object.values(tols.signals).some(hasLimit);
  const tolKey = JSON.stringify(tols);
  // 26.U4: a golden run keeps the tolerances last used against it
  useEffect(() => { if (golden && basePath) rememberTolerances(basePath, tols); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [tolKey, golden, basePath]);
  const runName = (rid: string) => fileLabel(allRuns, rid);
  // T46: a file has ONE colour everywhere (it was by position among the checked runs - unchecking
  // one recoloured the others)
  const runColor = (rid: string) => fileMark(runs, rid)?.color ?? TRACE_COLORS[Math.max(0, chosen.indexOf(rid)) % TRACE_COLORS.length];

  /* ------------- similarity list: debounced, cancellable, cached ------------- */
  const key = `${[...active].sort().join(",")}|${baseline}|${alignment}|${tolKey}|${dataVersion}|${segment ? JSON.stringify(segment.windows) : ""}|${segWaiting}`;
  useEffect(() => {
    jobRef.current?.cancel();                // a newer choice replaces any running computation
    jobRef.current = null;
    setSimError("");
    if (active.length < 2 || !baseline || segWaiting) { setSim(null); setProgress(null); return; }
    const base = baseline === "mean" || active.includes(baseline) ? baseline : "mean";
    const hit = cache.get(key);
    if (hit) { setSim(hit); setSimKey(key); setProgress(null); return; }
    setProgress(0);
    const h = window.setTimeout(() => {
      const job = startJob<{ signals: CompareAllRow[] }>("compareAll",
        { runs: active, baselineRun: base, alignment, tolerances: tols, points: LIST_POINTS, windows: segment?.windows ?? null },
        (p) => setProgress(p));
      jobRef.current = job;
      job.result.then((r) => {
        if (!r || jobRef.current !== job) return;            // cancelled or superseded
        cache.set(key, r.signals);
        if (cache.size > 8) cache.delete(cache.keys().next().value!);
        setSim(r.signals); setSimKey(key); setProgress(null); setLimit(PAGE);
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
  // C13: the signal of file `rid` in the row `name` (a .mat's "ATT.Roll" is the log's "ATT.Roll [deg]")
  const sidIn = (rid: string, name: string) => `${rid}/${sim?.find((x) => x.name === name)?.sigs?.[rid] ?? name}`;
  const detail = async (name: string, runsOf: string[]) => {
    setSignal(name);
    setBusy(true);
    try {
      const base = baseline !== "mean" && runsOf.includes(baseline) ? sidIn(baseline, name) : "mean";
      const r = await api.compare(runsOf.map((c) => sidIn(c, name)), base, alignment, tols, segment?.windows, 600);
      setRows(r.rows);
    } catch (e) { useApp.getState().toast({ kind: "error", text: String((e as Error).message) }); setRows(null); }
    finally { setBusy(false); }
  };
  const showInPlot = (name: string, runsOf: string[], newPlot: boolean) => {
    if (segment) { showSegmentPlot(name, runsOf, segment, newPlot, runColor, sim?.find((x) => x.name === name)?.sigs); return; }
    let full = false;
    useApp.getState().commit((ws) => {
      const tab = activeTab(ws);
      const signals = runsOf.map((rid) => (styledSignal(sidIn(rid, name), runColor(rid))));
      if (newPlot) {
        const at = placePlot(tab, { id: uid("p"), title: name, signals });
        if (at < 0) { full = true; return ws; }
        tab.active = at;
      } else {
        const p = tab.plots[tab.active];
        if (p) { p.signals = signals; p.title = name; }     // flip through signals in the same plot (26.U4: its title follows)
      }
      return ws;
    });
    if (full) tabFullMessage();
  };
  const pick = (x: CompareAllRow, e: React.MouseEvent) => {
    const rs = x.runs ?? active;
    showInPlot(x.name, rs, e.shiftKey);
    detail(x.name, rs);
  };
  const current = sim?.find((x) => x.name === signal);
  const detailRuns = current?.runs ?? active;
  // 26.U5: a changed tolerance judges the signal on screen again (after typing stops)
  const firstTol = useRef(true);
  useEffect(() => {
    if (firstTol.current) { firstTol.current = false; return; }
    if (!signal) return;
    const h = window.setTimeout(() => detail(signal, detailRuns), 350);
    return () => window.clearTimeout(h);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tolKey]);
  // this signal's own entry: the key it was found by (a file's "ATT.Roll" for "ATT.Roll [deg]"), else its name
  const ownKey = current?.tolKey ?? signal;
  const own: TolEntry = tols.signals[ownKey] ?? {};
  const setOwn = (e: TolEntry | null) => {
    const signals = { ...tols.signals };
    if (!e || !Object.keys(e).length) delete signals[ownKey]; else signals[ownKey] = e;
    setTols({ ...tols, signals });
  };
  /* ------------------------- 26.U4: the verdict per file ------------------------- */
  // only on a list computed for the current choice (not the previous one while the new one is computed)
  const vs = useMemo(() => (sim && simKey === key && baseline !== "mean" && tolSet ? verdicts(sim, baseline, active) : null),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [sim, simKey, key, baseline, tolSet, active.join(",")]);
  const showWorst = () => {
    const worst = vs?.flatMap((v) => v.failed).sort((a, b) => (b.outsidePct ?? 0) - (a.outsidePct ?? 0))[0];
    const x = worst && sim?.find((r) => r.name === worst.name);
    if (!x) return;
    setBucket("all"); setQ("");
    const rs = x.runs ?? active;
    showInPlot(x.name, rs, false);
    scrollTo.current = true;
    detail(x.name, rs);
  };
  // the worst failure's comparison is below the list: bring it into view once it is there
  const scrollTo = useRef(false);
  const blockRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (scrollTo.current && rows && blockRef.current) { scrollTo.current = false; blockRef.current.scrollIntoView({ block: "start", behavior: "smooth" }); }
  }, [rows]);
  const makeReport = () => {
    if (!sim || !vs) return;
    const rl = useApp.getState().ws.report?.lang ?? lang;
    const verdict = reportVerdict(sim, baseline, active, rl);
    // the failing signals, worst first (or the most different when all pass), each a plot of every file
    const failing = Array.from(new Set(vs.flatMap((v) => v.failed.map((f) => f.name))));
    const names = (failing.length ? failing : list.map((x) => x.name)).slice(0, 6);
    const tabName = `${translate(rl, "judgeReportTab")} · ${active.filter((r) => r !== baseline).map(runName).join(", ")}`.slice(0, 60);
    useApp.getState().commit((ws) => {
      const tab = { id: uid("t"), name: tabName, rows: 1, cols: 1, active: 0, linkX: true,
        plots: names.map((nm) => {
          const rs = sim.find((x) => x.name === nm)?.runs ?? active;
          return { id: uid("p"), title: nm, signals: rs.map((rid) => (styledSignal(sidIn(rid, nm), runColor(rid)))) };
        }) };
      fitLayout(tab);
      ws.tabs.push(tab);
      ws.activeTab = tab.id;
      const r = { intro: "", summary: "", lang: rl, theme: "light" as const, ...(ws.report ?? {}) };
      ws.report = { ...r, title: r.title || verdict.title, scope: "tab", verdict, includeVerdict: true };
      return ws;
    });
    useApp.setState({ panel: "report" });
    useApp.getState().toast({ kind: "info", text: translate(lang, "judgeReportReady", { tab: tabName }) });
  };
  const openTols = async () => {
    const path = await pickPath({ mode: "open", title: t("tolOpen"), exts: [".json"] });
    if (!path) return;
    try {
      const r = await api.loadTolerances(path);
      setTols(r.tolerances);
      useApp.getState().toast({ kind: "info", text: translate(lang, "tolOpened", { n: Object.keys(r.tolerances.signals).length, path: r.path }) });
    } catch (e) { useApp.getState().toast({ kind: "error", text: String((e as Error).message) }); }
  };
  const saveTols = async () => {
    const path = await pickPath({ mode: "save", title: t("tolSave"), exts: [".json"], defaultName: "tolerances.json" });
    if (!path) return;
    try {
      const r = await api.saveTolerances(path, tols);
      useApp.getState().toast({ kind: "info", text: translate(lang, "tolSaved", { path: r.path }) });
    } catch (e) { useApp.getState().toast({ kind: "error", text: String((e as Error).message) }); }
  };

  const align = async (sid: string) => {
    if (baseline === "mean") return;
    const rid = sid.split("/")[0];
    const info = runs.find((r) => r.id === rid);
    if (!info) return;
    const { shift } = await api.shift(sidIn(baseline, signal), sid);
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
      const ids = detailRuns.map((r) => sidIn(r, signal));
      let base = baseline !== "mean" && detailRuns.includes(baseline) ? sidIn(baseline, signal) : "mean";
      if (base === "mean") base = (await api.createDerived("mean", ids, { alignment }, `mean(${signal})`)).id;
      const made: string[] = [];
      for (const id of ids) {
        if (id === base) continue;
        // Q91: the baseline is kept - this difference belongs to its run, and a new run gets its own
        const r = await api.createDerived("sub", [id, base], { alignment, pinned: [1] }, `Δ ${signal} ${runName(id.split("/")[0])}`);
        made.push(r.id);
        useApp.setState({ runs: r.runs });
      }
      let full = false;
      useApp.getState().commit((ws) => {
        const tab = activeTab(ws);
        const at = placePlot(tab, { id: uid("p"), title: `Δ ${signal}`, signals: made.map((sig, i) => (styledSignal(sig, TRACE_COLORS[(i + 1) % TRACE_COLORS.length]))) });
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
            {runs.filter((r) => chosen.includes(r.id)).map((r) => <option key={r.id} value={r.id}>{isGolden(r.path) ? "★ " : ""}{runName(r.id)}</option>)}
          </select></label>
        {/* 26.U4: a golden run is proposed for later recordings that have its signals, with its tolerances */}
        {baseline !== "mean" && basePath && (
          <label className="acheck golden-mark" title={t("goldenMarkHint")}>
            <input type="checkbox" checked={golden} onChange={(e) => {
              setGolden(basePath, e.target.checked, tols); setGoldenTick((n) => n + 1);
              useApp.getState().toast({ kind: "info", text: translate(lang, e.target.checked ? "goldenOn" : "goldenOff", { name: runName(baseline) }) });
            }} /> ★ {t("goldenMark")}</label>
        )}

        {/* ---------------- T10b: over the whole runs, or the same segment of each ---------------- */}
        <div className="afield"><span>{t("compareOver")}</span>
          <div className="seg wide small" role="group" aria-label={t("compareOver")}>
            <button className={over === "whole" ? "on" : ""} onClick={() => setOver("whole")}>{t("overWhole")}</button>
            <button className={over === "segment" ? "on" : ""} onClick={() => setOver("segment")} disabled={!stateNames.length}
              title={stateNames.length ? t("overSegmentHint") : t("overSegmentNone")}>{t("overSegment")}</button>
          </div></div>
        {over === "segment" && <div className="seg-pick">
          <label className="afield"><span>{t("segState")}</span>
            <select value={segState} onChange={(e) => setSegState(e.target.value)}>
              {stateNames.map((n) => <option key={n} value={n}>{n}</option>)}
            </select></label>
          <div className="arow">
            <label className="afield"><span>{t("segValue")}</span>
              <select value={segValue ?? ""} onChange={(e) => setSegValue(Number(e.target.value))}>
                {segValues.map((v) => <option key={v.value} value={v.value}>{v.label ?? fmtNum(v.value, lang, 6)}</option>)}
              </select></label>
            <label className="afield"><span>{t("segOccurrence")}</span>
              <select value={segOcc} onChange={(e) => setSegOcc(Number(e.target.value))}>
                {[1, 2, 3, 4, 5].map((k) => <option key={k} value={k}>{occText(k)}</option>)}
                <option value={-1}>{occText(-1)}</option>
              </select></label>
          </div>
          {segWin && <ul className="seg-wins">
            {segWin.map((w) => (
              <li key={w.run} className={w.t0 === undefined ? "missing" : ""}>
                <span className="run-dot" style={{ background: runColor(w.run) }} /><span className="nm">{runName(w.run)}</span>
                <span className="when">{w.t0 !== undefined
                  ? t("segAt", { t0: fmtNum(w.t0, lang, 4), d: fmtNum(w.t1! - w.t0, lang, 3) })
                  : w.missing === "signal" ? t("segNoSignal") : t("segNotFound", { n: w.count ?? 0 })}</span>
              </li>))}
          </ul>}
          <p className="hint">{t("segCompareHint")}</p>
        </div>}

        {/* ---------------- 26.U4: the verdict - per file, pass / fail against the baseline ---------------- */}
        {sim && baseline !== "mean" && active.length >= 2 && (simKey === key || !tolSet) && (
          <section className={`judge-verdict${vs ? (vs.some((v) => v.failed.length) ? " fail" : " pass") : ""}`} aria-label={t("judgeHead", { base: runName(baseline) })}>
            <h3>{t("judgeHead", { base: runName(baseline) })}</h3>
            {vs ? <>
              <ul>{vs.map((v) => (
                <li key={v.run} className={v.failed.length ? "fail" : "pass"}>
                  <span className={v.failed.length ? "sim-fail" : "sim-pass"} aria-hidden="true">{v.failed.length ? "✗" : "✓"}</span>
                  <span className="run-dot" style={{ background: runColor(v.run) }} />
                  <b className="nm">{runName(v.run)}</b>
                  <span className="jv-text">{v.failed.length ? t("judgeFailN", { n: v.failed.length, of: v.judged }) : t("judgePassAll", { of: v.judged })}</span>
                </li>))}
              </ul>
              <div className="arow wrap">
                {vs.some((v) => v.failed.length > 0) && <button className="btn primary" onClick={showWorst}>{t("judgeWorst")}</button>}
                <button className="btn outline" onClick={makeReport}>{t("judgeReport")}</button>
              </div>
            </> : <p className="hint">{t("judgeNoTol", { base: runName(baseline) })}{" "}
              <button className="linklike" onClick={() => setSettingsOpen(true)}>{t("judgeSetTol")}</button></p>}
          </section>
        )}

        {/* ---------------- similarity list ---------------- */}
        <div className="sim-head">
          <h3>{t("similarity")}</h3>
          <button className="linklike" onClick={() => setSort(sort === "worst" ? "best" : "worst")} title={t("sortToggle")}>
            {sort === "worst" ? t("leastSimilarFirst") : t("mostSimilarFirst")} ⇅</button>
        </div>
        {(chosen.length < 2 || (segment && active.length < 2)) && <p className="hint">{t(segment ? "segNeedTwo" : "pickTwo")}</p>}
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
                    <span className="sim-name">{x.name}
                      {/* U5: with a tolerance, every row says pass / fail */}
                      {x.pass === false && <span className="sim-fail" aria-label={t("fail")} title={t("fail")}>✗</span>}
                      {x.pass === true && <span className="sim-pass" aria-label={t("pass")} title={t("pass")}>✓</span>}
                      {x.skipped && <span className="sim-skip">{t("tolSkipped")}</span>}
                      {x.tolKey && !x.skipped && <span className="sim-own" title={t("tolOwn")} aria-label={t("tolOwn")}>±</span>}</span>
                    <span className={`sim-pct ${b}`}>{fmtNum(x.matchPct ?? 0, lang, 3)}%</span>
                    <span className="sim-bar"><span className={b} style={{ width: `${Math.max(2, x.matchPct ?? 0)}%` }} /></span>
                    <Spark values={x.profile} bucket={b} />
                  </button>
                );
              })}
              {!list.length && <p className="hint">{t("noMatches", { q })}</p>}
              {list.length > limit && <button className="btn outline sm" onClick={() => setLimit(limit + PAGE)}>{t("showMore", { n: list.length - limit })}</button>}
            </div>
            <div className="arow wrap">
              <button className="btn outline" onClick={() => sim && useApp.setState({ compareTable: { rows: sim, baseline, fileCount: active.length, tol: tolSet, segment: segment ?? undefined } })}>{t("compareTableBtn")}</button>
              <button className="btn outline" onClick={exportList}>{t("exportResults")}</button>
            </div>
          </>
        )}

        {/* ---------------- selected signal ---------------- */}
        {signal && rows && (
          <div className="cmp-block" ref={blockRef}>
            <h3 className="alist-head">{signal} <span className="muted">· {baseline === "mean" ? t("meanOfRuns") : runName(baseline)}</span></h3>
            <table className="vals cmp2">
              <thead><tr><th>{t("rmsDiff")}</th><th>{t("maxDiff")}</th><th>{t("corr")}</th>{tolSet && <th>{t("inTol")}</th>}</tr></thead>
              {rows.map((r) => (
                <tbody key={r.id}>
                  <tr className="name-row"><td colSpan={tolSet ? 4 : 3}>
                    <span className="run-dot" style={{ background: runColor(r.id.split("/")[0]) }} />
                    <span className="nm">{runName(r.id.split("/")[0])}</span>
                    {baseline !== "mean" && !segment && <button className="iconbtn sm act" title={t("alignInTime")} aria-label={t("alignInTime")} onClick={() => align(r.id)}><Icon.Link /></button>}
                  </td></tr>
                  <tr>
                    <td title={r.rmsPct !== undefined ? `${fmtNum(r.rmsPct, lang, 3)} %` : ""}>{fmtNum(r.rmsDiff, lang, 3)}</td>
                    <td>{fmtNum(r.maxAbsDiff, lang, 3)}</td>
                    <td>{fmtNum(r.correlation, lang, 4)}</td>
                    {tolSet && <td>{r.pass === undefined ? <span className="muted">—</span>
                      : <span className={`pf ${r.pass ? "ok" : "bad"}`} title={r.outsidePct ? t("outsideShare", { pct: fmtNum(r.outsidePct, lang, 3) }) : undefined}>{fmtNum(r.withinPct, lang, 3)}%</span>}</td>}
                  </tr>
                </tbody>
              ))}
            </table>
            {/* U5: where and why it fails - the difference over time with the tolerance band */}
            <DiffChart segment={!!segment} traces={rows.filter((r) => r.trace).map((r) => ({ id: r.id, color: runColor(r.id.split("/")[0]),
              name: runName(r.id.split("/")[0]), trace: r.trace! }))} />
            <div className="arow wrap">
              {!segment && <button className="btn outline" disabled={busy} onClick={plotDiffs}>{t("plotDiffs")}</button>}
            </div>
            {/* 26.U5: this signal's own tolerance (empty fields: every signal's, greyed) */}
            <div className="tol-signal">
              <h4 title={t("tolSignalHint")}>{t("tolSignalHead")}
                {tols.signals[ownKey] && <button className="linklike" onClick={() => setOwn(null)}>{t("tolUseDefault")}</button>}</h4>
              <TolFields entry={own} inherited={tols.default} onChange={(e) => setOwn(e)} />
              <label className="acheck"><input type="checkbox" checked={!!own.skip}
                onChange={(e) => { const x = { ...own }; if (e.target.checked) x.skip = true; else delete x.skip; setOwn(x); }} /> {t("tolSkip")}</label>
            </div>
          </div>
        )}

        {/* ---------------- settings ---------------- */}
        <button className="sim-settings-toggle" aria-expanded={settingsOpen} onClick={() => setSettingsOpen(!settingsOpen)}>
          <Icon.Chevron className="chev" /> {t("compareSettings")}
          {(tolSet || alignment !== "linear") && <span className="tag">•</span>}
        </button>
        {settingsOpen && <>
          <h4 className="tol-head">{t("tolDefaultHead")}</h4>
          <TolFields entry={tols.default} onChange={(e) => setTols({ ...tols, default: e })} />
          <div className="arow wrap">
            <button className="btn outline sm" onClick={openTols}>{t("tolOpen")}</button>
            <button className="btn outline sm" onClick={saveTols} disabled={!tolSet && !Object.keys(tols.signals).length}>{t("tolSave")}</button>
            {(tolSet || Object.keys(tols.signals).length > 0) && <button className="linklike" onClick={() => setTols({ default: {}, signals: {} })}>{t("tolClear")}</button>}
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
