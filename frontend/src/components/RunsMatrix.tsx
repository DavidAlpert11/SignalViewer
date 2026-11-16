import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { actions, fileLabel, MEASURE_OPS, pickPath, uid, useApp, type Condition, type Measure, type MeasureOp } from "../store";
import { fmtNum, useT } from "../i18n";
import { Icon } from "../icons";
import { useEscape } from "./Overlays";
import { openPaths } from "../files";
import { summarizeFolder as summarizeInSweeps } from "../folderSummary";
import { copyText } from "../errorReport";

const DATA_EXTS = [".csv", ".txt", ".mat", ".parquet", ".h5", ".hdf5"];
const MAX_FOLDER = 200;

/** Investigation step 5: every open run against every condition - a row per run, its parameters
 *  (what tells the runs apart) and, per condition, how often (or how long) it held. Cells far from
 *  their column are marked; a click opens that run at the condition's first stretch. Two columns
 *  can be drawn against each other (a point per run, with a fitted line). */
export default function RunsMatrix() {
  const t = useT();
  const lang = useApp((s) => s.lang);
  const runs = useApp((s) => s.runs);
  const conds = useApp((s) => s.ws.conditions) ?? [];
  const results = useApp((s) => s.condResults);
  const close = () => useApp.setState({ matrixOpen: false, matrixFolder: null });
  useEscape(close);
  const files = runs.filter((r) => r.format !== "derived");
  const [measure, setMeasure] = useState<"count" | "total">("count");
  const [params, setParams] = useState<Record<string, Record<string, number>>>({});
  const [sort, setSort] = useState<{ col: string; up: boolean } | null>(null);
  const [xCol, setXCol] = useState("");
  const [yCol, setYCol] = useState("");
  const [busy, setBusy] = useState("");

  useEffect(() => { api.runParams().then((r) => setParams(r.params)).catch(() => setParams({})); }, [runs.length]);
  // M1: the measures (one number per run) and the parameters read from the file names - defined while
  // looking at the open runs, so a wrong signal or condition shows at once as "–"
  const measures = useApp((s) => s.ws.measures) ?? [];
  const pattern = useApp((s) => s.ws.namePattern) ?? "";
  const [summary, setSummary] = useState<Record<string, { params: Record<string, number | string>; values: Record<string, number | null> }>>({});
  const [sumErr, setSumErr] = useState("");
  const sumKey = JSON.stringify([measures, pattern, files.map((f) => f.version ?? f.id)]);
  useEffect(() => {
    if (!measures.length && !pattern.trim()) { setSummary({}); return; }
    let live = true;
    api.runSummary(measures, pattern).then((r) => { if (live) { setSummary(r.rows); setSumErr(""); } })
      .catch((e) => { if (live) setSumErr(String((e as Error).message)); });
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sumKey]);
  const nameCols = useMemo(() => [...new Set(Object.values(summary).flatMap((r) => Object.keys(r.params)))], [summary]);
  const setMeasures = (next: Measure[]) => useApp.getState().commit((ws) => { ws.measures = next; return ws; });
  const setPattern = (v: string) => useApp.getState().commit((ws) => { ws.namePattern = v || undefined; return ws; });
  const [draft, setDraft] = useState<{ signal: string; op: MeasureOp; where: string; t: string } | null>(null);
  const addMeasure = () => {
    if (!draft?.signal.trim()) return;
    const name = `${draft.op} ${draft.signal.trim()}${draft.op === "at" ? ` @${draft.t}` : ""}`;
    setMeasures([...measures, { id: uid("m"), name, signal: draft.signal.trim(), op: draft.op,
      ...(draft.where.trim() ? { where: draft.where.trim() } : {}), ...(draft.op === "at" ? { t: Number(draft.t) || 0 } : {}) }]);
    setDraft(null);
  };
  const signalNames = useMemo(() => [...new Set(files.flatMap((f) => f.signals.map((s) => s.name)))].slice(0, 2000), [files]);
  // FL1: the folder being defined on (Sweeps > Data > From a folder) keeps its measures beside its recordings
  const folder = useApp((s) => s.matrixFolder);
  const folderLabel = folder?.split(/[\\/]/).filter(Boolean).pop() ?? "";
  const saveMeasures = async () => {
    const path = folder ? `${folder}${folder.includes("\\") ? "\\" : "/"}measures.json`
      : await pickPath({ mode: "save", title: t("mxSaveMeasures"), exts: [".json"], defaultName: "measures.json" });
    if (!path) return;
    const body = JSON.stringify({ measures: measures.map(({ id: _id, ...m }) => m), pattern }, null, 1);
    try { await api.saveText(path, body, ".json", false); useApp.getState().toast({ kind: "info", text: t("mxSavedMeasures", { path }) }); }
    catch (e) { useApp.getState().toast({ kind: "error", text: String((e as Error).message) }); }
  };

  // parameters that differ between the runs (one value everywhere tells nothing)
  const paramCols = useMemo(() => {
    const names = [...new Set(Object.values(params).flatMap((p) => Object.keys(p)))];
    // a parameter the name pattern reads is shown once, from the pattern
    return names.filter((n) => !nameCols.includes(n) && new Set(files.map((f) => params[f.id]?.[n])).size > 1).sort();
  }, [params, files, nameCols]);
  const condCols = conds.map((c) => ({ key: `c:${c.id}`, c }));
  const value = (rid: string, key: string): number | null => {
    if (key.startsWith("p:")) return params[rid]?.[key.slice(2)] ?? null;
    if (key.startsWith("m:")) return summary[rid]?.values[measures.find((m) => `m:${m.id}` === key)?.name ?? ""] ?? null;
    if (key.startsWith("n:")) { const v = summary[rid]?.params[key.slice(2)]; return typeof v === "number" ? v : null; }
    const r = results[key.slice(2)]?.[rid];
    if (!r || r.missing?.length || r.error) return null;
    return measure === "count" ? r.count ?? 0 : r.total ?? 0;
  };
  const allKeys = [...nameCols.map((n) => `n:${n}`), ...paramCols.map((n) => `p:${n}`), ...measures.map((m) => `m:${m.id}`), ...condCols.map((x) => x.key)];
  const label = (key: string) => (key.startsWith("p:") || key.startsWith("n:") ? key.slice(2)
    : key.startsWith("m:") ? measures.find((m) => `m:${m.id}` === key)?.name ?? key : conds.find((c) => `c:${c.id}` === key)?.name ?? key);

  // a cell far from the rest of its column: beyond 3 robust spreads, or the odd one out when the rest agree
  const odd = useMemo(() => {
    const out = new Set<string>();
    for (const { key } of condCols) {
      const vs = files.map((f) => ({ rid: f.id, v: value(f.id, key) })).filter((x): x is { rid: string; v: number } => x.v !== null);
      if (vs.length < 3) continue;
      const sorted = vs.map((x) => x.v).sort((a, b) => a - b);
      const med = sorted[Math.floor(sorted.length / 2)];
      const mad = [...sorted.map((v) => Math.abs(v - med))].sort((a, b) => a - b)[Math.floor(sorted.length / 2)] * 1.4826;
      for (const x of vs) if (mad > 0 ? Math.abs(x.v - med) / mad > 3 : x.v !== med) out.add(`${x.rid}|${key}`);
    }
    return out;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [results, measure, files.length, conds]);

  const rows = [...files].sort((a, b) => {
    if (!sort) return 0;
    if (sort.col === "file") return fileLabel(runs, a.id).localeCompare(fileLabel(runs, b.id)) * (sort.up ? 1 : -1);
    const va = value(a.id, sort.col) ?? -Infinity, vb = value(b.id, sort.col) ?? -Infinity;
    return (va - vb) * (sort.up ? 1 : -1);
  });
  const head = (key: string, text: string, color?: string) => (
    <th key={key}><button className="linklike" onClick={() => setSort({ col: key, up: sort?.col === key ? !sort.up : true })}>
      {color && <span className="cond-swatch" style={{ background: color }} />} {text}{sort?.col === key ? (sort.up ? " ▴" : " ▾") : ""}</button></th>
  );
  const goTo = (rid: string, c: Condition) => {
    const iv = results[c.id]?.[rid]?.intervals?.[0];
    if (!iv) return;
    const pad = Math.max((iv[1] - iv[0]) * 0.5, 0.5);
    actions.showSpan(iv[0] - pad, iv[1] + pad);
    useApp.setState({ condFocus: c.id, matrixOpen: false, cursor: { ...useApp.getState().cursor, on: true, dual: true, t1: iv[0], t2: iv[1], active: 1 } });
  };
  const addFolder = async () => {
    const dir = await pickPath({ mode: "folder", title: t("mxFolderTitle") });
    if (!dir) return;
    setBusy(t("mxFolderReading"));
    try {
      const ls = await api.listDir(dir, DATA_EXTS);
      const open = new Set(files.map((f) => f.path));
      const paths = ls.entries.filter((e) => !e.dir && DATA_EXTS.some((x) => e.name.toLowerCase().endsWith(x))).map((e) => e.path)
        .filter((p) => !open.has(p)).slice(0, MAX_FOLDER);
      if (paths.length) await openPaths(paths);
      setBusy(paths.length ? "" : t("mxFolderNone"));
    } catch (e) { setBusy(String((e as Error).message)); }
  };
  const copy = () => {
    const lines = [["file", ...allKeys.map(label)].join("\t"),
      ...rows.map((f) => [fileLabel(runs, f.id), ...allKeys.map((k) => value(f.id, k) ?? "")].join("\t"))];
    void copyText(lines.join("\n")).then((ok) => useApp.getState().toast(ok ? { kind: "info", text: t("occCopied") } : { kind: "error", text: t("copyTextFailed") }));
  };

  // M2: the measures over a folder of recordings that are NOT opened (the backend reads one at a time - the
  // memory of one file), straight into Sweeps
  const summarizeFolder = async () => {
    const dir = folder ?? await pickPath({ mode: "folder", title: t("mxSumFolderTitle") });
    if (dir) await summarizeInSweeps(dir, measures.map(({ id: _id, ...m }) => m), pattern);
  };
  // the same table in the Sweeps area: a row per run - its file, parameters and the conditions'
  // measures - where a goal, conditions over scenarios and the parallel plot apply
  const toSweeps = async () => {
    const columns = ["recording", ...nameCols, ...paramCols, ...measures.map((m) => m.name), ...condCols.map((x) => x.c.name)];
    const rows = files.map((f) => [f.path, ...nameCols.map((n) => summary[f.id]?.params[n] ?? null), ...paramCols.map((n) => params[f.id]?.[n] ?? null),
      ...measures.map((m) => summary[f.id]?.values[m.name] ?? null), ...condCols.map((x) => value(f.id, x.key))]);
    const { useSweeps } = await import("../sweeps/state");
    useApp.setState({ matrixOpen: false, area: "sweeps" });
    await useSweeps.getState().openRows(t("mxTitle"), columns, rows);
  };
  return (
    <div className="scrim" onMouseDown={close}>
      <div className="dialog mx-dialog" role="dialog" aria-label={t("mxTitle")} onMouseDown={(e) => e.stopPropagation()}>
        <div className="dialog-head">
          <h2>{t("mxTitle")}</h2>
          <button className="iconbtn" onClick={close} aria-label={t("close")}><Icon.X /></button>
        </div>
        <div className="mx-tools">
          <select className="mx-measure" value={measure} onChange={(e) => setMeasure(e.target.value as "count" | "total")} aria-label={t("mxMeasure")}>
            <option value="count">{t("mxCount")}</option><option value="total">{t("mxTotal")}</option>
          </select>
          <button className="btn outline sm mx-folder" onClick={addFolder}>{t("mxFolder")}</button>
          <button className="btn outline sm" onClick={copy}>{t("copyTable")}</button>
          <button className="btn outline sm" onClick={toSweeps} title={t("mxToSweepsHint")}>{t("mxToSweeps")}</button>
          {busy && <span className="hint">{busy}</span>}
        </div>
        {folder ? <p className="mx-folder-step">{t("mxDefineOn", { folder: folderLabel })}</p> : <p className="hint">{t("mxHint")}</p>}
        <div className="mx-tools mx-measures">
          <span>{t("mxMeasures")}</span>
          {measures.map((m) => (
            <span key={m.id} className="chip mx-measure-chip" title={m.where ? `${m.name} · ${m.where}` : m.name}>{m.name}
              <button className="linklike" aria-label={t("remove")} onClick={() => setMeasures(measures.filter((x) => x.id !== m.id))}>×</button></span>
          ))}
          {!draft && <button className="btn outline sm mx-add-measure" onClick={() => setDraft({ signal: "", op: "max", where: "", t: "0" })}>+ {t("mxAddMeasure")}</button>}
          {measures.length > 0 && <button className="btn outline sm mx-sum-folder" onClick={summarizeFolder} title={t("mxSumFolderHint")}>{folder ? t("mxSumThisFolder", { folder: folderLabel }) : t("mxSumFolder")}</button>}
          {measures.length > 0 && <button className="btn outline sm" onClick={saveMeasures} title={t("mxSaveMeasuresHint")}>{t("mxSaveMeasures")}</button>}
          <label className="mx-pattern">{t("mxPattern")}{" "}
            <input dir="ltr" defaultValue={pattern} placeholder="kp_{kp}_wind_{wind}" onBlur={(e) => e.target.value !== pattern && setPattern(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()} aria-label={t("mxPattern")} /></label>
        </div>
        {draft && (
          <div className="mx-tools mx-draft">
            <select className="mx-op" value={draft.op} onChange={(e) => setDraft({ ...draft, op: e.target.value as MeasureOp })} aria-label={t("mxWhat")}>
              {MEASURE_OPS.map((o) => <option key={o} value={o}>{t(`mxOp_${o}` as "mxOp_max")}</option>)}
            </select>
            <input className="mx-sig" dir="ltr" list="mx-sig-names" value={draft.signal} placeholder={t("mxSignal")} autoFocus
              onChange={(e) => setDraft({ ...draft, signal: e.target.value })} onKeyDown={(e) => e.key === "Enter" && addMeasure()} aria-label={t("mxSignal")} />
            <datalist id="mx-sig-names">{signalNames.map((n) => <option key={n} value={n} />)}</datalist>
            {draft.op === "at" && <input className="mx-at" type="number" value={draft.t} onChange={(e) => setDraft({ ...draft, t: e.target.value })} aria-label="t" />}
            <input className="mx-where" dir="ltr" value={draft.where} placeholder={t("mxWhere")} onChange={(e) => setDraft({ ...draft, where: e.target.value })}
              onKeyDown={(e) => e.key === "Enter" && addMeasure()} aria-label={t("mxWhere")} />
            <button className="btn primary sm mx-add" disabled={!draft.signal.trim()} onClick={addMeasure}>{t("mxAdd")}</button>
            <button className="btn outline sm" onClick={() => setDraft(null)}>{t("cancel")}</button>
          </div>
        )}
        {sumErr && <p className="hint err">{sumErr}</p>}
        <div className="dialog-body mx-body">
          <table className="occ-table mx-table">
            <thead><tr>
              {head("file", t("occFile"))}
              {nameCols.map((n) => head(`n:${n}`, n))}
              {paramCols.map((n) => head(`p:${n}`, n))}
              {measures.map((m) => head(`m:${m.id}`, m.name))}
              {condCols.map(({ key, c }) => head(key, c.name, c.color))}
            </tr></thead>
            <tbody>
              {rows.map((f) => (
                <tr key={f.id}>
                  <td className="mx-file">{fileLabel(runs, f.id)}</td>
                  {nameCols.map((n) => { const v = summary[f.id]?.params[n]; return <td key={`n:${n}`} className="mx-param">{v === undefined ? "–" : typeof v === "number" ? fmtNum(v, lang, 6) : v}</td>; })}
                  {paramCols.map((n) => <td key={n} className="mx-param">{params[f.id]?.[n] !== undefined ? fmtNum(params[f.id][n], lang, 6) : "–"}</td>)}
                  {measures.map((m) => { const v = summary[f.id]?.values[m.name]; return <td key={m.id} className="mx-cell mx-mval">{v === null || v === undefined ? "–" : fmtNum(v, lang, 5)}</td>; })}
                  {condCols.map(({ key, c }) => {
                    const v = value(f.id, key);
                    const r = results[c.id]?.[f.id];
                    return (
                      <td key={key} className={`mx-cell${odd.has(`${f.id}|${key}`) ? " odd" : ""}${v ? " has" : ""}`}
                        title={r?.missing?.length ? t("condMissing", { names: r.missing.join(", ") }) : r?.error ?? t("mxCellHint")}
                        onClick={() => v && goTo(f.id, c)}>
                        {v === null ? "–" : measure === "count" ? fmtNum(v, lang, 6) : fmtNum(v, lang, 4)}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
          {files.length >= 3 && allKeys.length >= 2 && (
            <div className="mx-scatter">
              <div className="mx-tools">
                <span>{t("mxScatter")}</span>
                <select className="mx-x" value={xCol || allKeys[0]} onChange={(e) => setXCol(e.target.value)} aria-label="X">
                  {allKeys.map((k) => <option key={k} value={k}>{label(k)}</option>)}</select>
                <span>↔</span>
                <select className="mx-y" value={yCol || allKeys[allKeys.length - 1]} onChange={(e) => setYCol(e.target.value)} aria-label="Y">
                  {allKeys.map((k) => <option key={k} value={k}>{label(k)}</option>)}</select>
              </div>
              <Scatter pts={files.map((f) => ({ name: fileLabel(runs, f.id), x: value(f.id, xCol || allKeys[0]), y: value(f.id, yCol || allKeys[allKeys.length - 1]) }))} />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/** A point per run and the straight line that fits them, with how well (r). */
function Scatter({ pts }: { pts: { name: string; x: number | null; y: number | null }[] }) {
  const t = useT();
  const lang = useApp((s) => s.lang);
  const ok = pts.filter((p): p is { name: string; x: number; y: number } => p.x !== null && p.y !== null);
  if (ok.length < 3) return <p className="hint">{t("mxScatterFew")}</p>;
  const W = 420, H = 220, P = 36;
  const xs = ok.map((p) => p.x), ys = ok.map((p) => p.y);
  const [x0, x1] = [Math.min(...xs), Math.max(...xs)], [y0, y1] = [Math.min(...ys), Math.max(...ys)];
  const sx = (x: number) => P + ((x - x0) / (x1 - x0 || 1)) * (W - 2 * P);
  const sy = (y: number) => H - P + -((y - y0) / (y1 - y0 || 1)) * (H - 2 * P);
  const n = ok.length, mx = xs.reduce((a, b) => a + b, 0) / n, my = ys.reduce((a, b) => a + b, 0) / n;
  const sxy = ok.reduce((s, p) => s + (p.x - mx) * (p.y - my), 0), sxx = xs.reduce((s, x) => s + (x - mx) ** 2, 0), syy = ys.reduce((s, y) => s + (y - my) ** 2, 0);
  const slope = sxx ? sxy / sxx : 0, r = sxx && syy ? sxy / Math.sqrt(sxx * syy) : 0;
  return (
    <figure className="mx-fig">
      <svg width={W} height={H} role="img" aria-label={t("mxScatter")}>
        <line x1={P} y1={H - P} x2={W - P} y2={H - P} stroke="var(--line)" />
        <line x1={P} y1={P} x2={P} y2={H - P} stroke="var(--line)" />
        {sxx > 0 && <line x1={sx(x0)} y1={sy(my + slope * (x0 - mx))} x2={sx(x1)} y2={sy(my + slope * (x1 - mx))} stroke="var(--amber)" strokeDasharray="4 3" />}
        {ok.map((p, i) => <circle key={i} cx={sx(p.x)} cy={sy(p.y)} r={4} fill="var(--focus)"><title>{`${p.name}: ${p.x}, ${p.y}`}</title></circle>)}
        <text x={P} y={H - 8} fontSize={11} fill="var(--muted)">{fmtNum(x0, lang, 4)}</text>
        <text x={W - P} y={H - 8} fontSize={11} fill="var(--muted)" textAnchor="end">{fmtNum(x1, lang, 4)}</text>
        <text x={4} y={P} fontSize={11} fill="var(--muted)">{fmtNum(y1, lang, 4)}</text>
        <text x={4} y={H - P} fontSize={11} fill="var(--muted)">{fmtNum(y0, lang, 4)}</text>
      </svg>
      <figcaption className="hint mx-r">{t("mxFit", { r: fmtNum(r, lang, 2), n })}</figcaption>
    </figure>
  );
}
