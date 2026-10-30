import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { actions, fileLabel, pickPath, useApp, type Condition } from "../store";
import { fmtNum, useT } from "../i18n";
import { Icon } from "../icons";
import { useEscape } from "./Overlays";
import { openPaths } from "../files";

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
  const close = () => useApp.setState({ matrixOpen: false });
  useEscape(close);
  const files = runs.filter((r) => r.format !== "derived");
  const [measure, setMeasure] = useState<"count" | "total">("count");
  const [params, setParams] = useState<Record<string, Record<string, number>>>({});
  const [sort, setSort] = useState<{ col: string; up: boolean } | null>(null);
  const [xCol, setXCol] = useState("");
  const [yCol, setYCol] = useState("");
  const [busy, setBusy] = useState("");

  useEffect(() => { api.runParams().then((r) => setParams(r.params)).catch(() => setParams({})); }, [runs.length]);

  // parameters that differ between the runs (one value everywhere tells nothing)
  const paramCols = useMemo(() => {
    const names = [...new Set(Object.values(params).flatMap((p) => Object.keys(p)))];
    return names.filter((n) => new Set(files.map((f) => params[f.id]?.[n])).size > 1).sort();
  }, [params, files]);
  const condCols = conds.map((c) => ({ key: `c:${c.id}`, c }));
  const value = (rid: string, key: string): number | null => {
    if (key.startsWith("p:")) return params[rid]?.[key.slice(2)] ?? null;
    const r = results[key.slice(2)]?.[rid];
    if (!r || r.missing?.length || r.error) return null;
    return measure === "count" ? r.count ?? 0 : r.total ?? 0;
  };
  const allKeys = [...paramCols.map((n) => `p:${n}`), ...condCols.map((x) => x.key)];
  const label = (key: string) => (key.startsWith("p:") ? key.slice(2) : conds.find((c) => `c:${c.id}` === key)?.name ?? key);

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
    void navigator.clipboard.writeText(lines.join("\n")).then(() => useApp.getState().toast({ kind: "info", text: t("occCopied") }));
  };

  // the same table in the Sweeps area: a row per run - its file, parameters and the conditions'
  // measures - where a goal, conditions over scenarios and the parallel plot apply
  const toSweeps = async () => {
    const columns = ["recording", ...paramCols, ...condCols.map((x) => x.c.name)];
    const rows = files.map((f) => [f.path, ...paramCols.map((n) => params[f.id]?.[n] ?? null), ...condCols.map((x) => value(f.id, x.key))]);
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
        <p className="hint">{t("mxHint")}</p>
        <div className="dialog-body mx-body">
          <table className="occ-table mx-table">
            <thead><tr>
              {head("file", t("occFile"))}
              {paramCols.map((n) => head(`p:${n}`, n))}
              {condCols.map(({ key, c }) => head(key, c.name, c.color))}
            </tr></thead>
            <tbody>
              {rows.map((f) => (
                <tr key={f.id}>
                  <td className="mx-file">{fileLabel(runs, f.id)}</td>
                  {paramCols.map((n) => <td key={n} className="mx-param">{params[f.id]?.[n] !== undefined ? fmtNum(params[f.id][n], lang, 6) : "–"}</td>)}
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
