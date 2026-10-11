import { useEscape } from "./Overlays";
import { useMemo, useState } from "react";
import { api, type CompareAllRow } from "../api";
import { activeTab, fileLabel, pickPath, placePlot, tabFullMessage, TRACE_COLORS, uid, useApp } from "../store";
import { fmtNum, translate, useT } from "../i18n";
import { Icon } from "../icons";
import { exactMatch } from "../fuzzy";

type Key = "name" | "files" | "meanSpread" | "stdSpread" | "worstRmsDiff" | "worstMaxAbs" | "minCorrelation";
const PAGE = 200;

/** All signals that share a name across the chosen files, side by side (P-04). */
export default function CompareTable() {
  const t = useT();
  const lang = useApp((s) => s.lang);
  const runs = useApp((s) => s.runs);
  const data = useApp((s) => s.compareTable);
  const [q, setQ] = useState("");
  const [sort, setSort] = useState<{ key: Key; desc: boolean }>({ key: "worstRmsDiff", desc: true });
  const [open, setOpen] = useState<string | null>(null);
  const [limit, setLimit] = useState(PAGE);

  const rows = useMemo(() => {
    if (!data) return [];
    const r = data.rows.filter((x) => !q.trim() || exactMatch(x.name, q));
    const val = (x: CompareAllRow) => (sort.key === "name" ? x.name : sort.key === "files" ? x.runs?.length ?? 0 : (x as any)[sort.key] ?? -Infinity);
    return r.slice().sort((a, b) => {
      const va = val(a), vb = val(b);
      const c = typeof va === "string" ? va.localeCompare(vb as string) : (va as number) - (vb as number);
      return sort.desc ? -c : c;
    });
  }, [data, q, sort]);
  useEscape(() => useApp.setState({ compareTable: null }), !!data);
  if (!data) return null;
  // heat: how bad each row is relative to the worst row (quick visual scanning)
  const maxPct = Math.max(1e-12, ...data.rows.map((x) => x.worstRmsPct ?? 0));
  const heat = (ratio: number) => ({ background: `color-mix(in srgb, var(--danger) ${Math.round(Math.max(0, Math.min(1, ratio)) * 32)}%, transparent)` });

  const close = () => useApp.setState({ compareTable: null });
  const file = (rid: string) => fileLabel(runs, rid);
  const n = (v: number | null | undefined, d = 4) => fmtNum(v ?? null, lang, d);
  const head = (key: Key, label: string, title?: string) => (
    <th aria-sort={sort.key === key ? (sort.desc ? "descending" : "ascending") : "none"} title={title}>
      <button className="th-btn" onClick={() => setSort({ key, desc: sort.key === key ? !sort.desc : key !== "name" })}>
        {label}{sort.key === key ? (sort.desc ? " ↓" : " ↑") : ""}</button>
    </th>
  );
  const plotRow = (x: CompareAllRow) => {
    let full = false;
    useApp.getState().commit((ws) => {
      const tab = activeTab(ws);
      const p = { id: uid("p"), title: x.name, signals: (x.runs ?? []).map((rid, i) => ({ sig: `${rid}/${x.name}`, color: TRACE_COLORS[i % TRACE_COLORS.length], width: 1.5, scale: 1, offset: 0 })) };
      const at = placePlot(tab, p);
      if (at < 0) { full = true; return ws; }
      tab.active = at;
      return ws;
    });
    if (full) tabFullMessage(); else close();
  };
  const exportCsv = async () => {
    const path = await pickPath({ mode: "save", title: t("exportResults"), exts: [".csv"], defaultName: "comparison.csv" });
    if (!path) return;
    const lines = ["signal,file,is_baseline,mean,std,min,max,mean_diff,std_diff,rms_diff,max_abs_diff,correlation,within_tol_pct,pass"];
    for (const x of rows) for (const f of x.files ?? []) {
      const d = x.diffs?.find((y) => y.run === f.run);
      const base = x.baseline === f.run;
      lines.push([`"${x.name}"`, `"${file(f.run)}"`, base, f.mean, f.std, f.min, f.max, d?.meanDiff ?? "", d?.stdDiff ?? "", d?.rmsDiff ?? "",
        d?.maxAbsDiff ?? "", d?.correlation ?? "", d?.withinPct ?? "", d?.pass ?? ""].join(","));
    }
    const r = await api.saveText(path, lines.join("\n"));
    useApp.getState().toast({ kind: "info", text: translate(lang, "savedTo", { path: r.path }) });
  };

  return (
    <div className="scrim" style={{ paddingTop: "4vh" }} onMouseDown={close}>
      <div className="dialog cmp-dialog" role="dialog" aria-label={t("compareTable")} onMouseDown={(e) => e.stopPropagation()}
        onKeyDown={(e) => { if (e.key === "Escape") close(); }}>
        <div className="dialog-head">
          <h2>{t("compareTable")} <span className="muted">· {t("filesOpen", { n: data.fileCount })} · {data.baseline === "mean" ? t("meanOfRuns") : `${t("baseline")}: ${file(data.baseline)}`}</span></h2>
          <label className="filter cmp-filter"><Icon.Search /><input autoFocus value={q} onChange={(e) => { setQ(e.target.value); setLimit(PAGE); }} placeholder={t("searchSignals")} aria-label={t("searchSignals")} /></label>
          <button className="btn outline" onClick={exportCsv}>{t("exportResults")}</button>
          <button className="iconbtn" onClick={close} aria-label={t("close")}><Icon.X /></button>
        </div>
        <p className="hint cmp-explain">{t("compareTableHint")}</p>
        <div className="dialog-body cmp-scroll">
          <table className="cmp-table">
            <thead><tr>
              {head("name", t("signal"))}{head("files", t("filesCol"))}
              {head("meanSpread", t("meanSpread"), t("meanSpreadHint"))}{head("stdSpread", t("stdSpread"), t("stdSpreadHint"))}
              {head("worstRmsDiff", t("rmsDiff"), t("worstHint"))}{head("worstMaxAbs", t("maxDiff"), t("worstHint"))}
              {head("minCorrelation", t("corr"), t("minCorrHint"))}{data.tol && <th>{t("inTol")}</th>}<th></th>
            </tr></thead>
            <tbody>
              {rows.slice(0, limit).map((x) => {
                const isOpen = open === x.name;
                return [
                  <tr key={x.name} className={`cmp-row${isOpen ? " open" : ""}`} onClick={() => setOpen(isOpen ? null : x.name)}>
                    <td className="nm"><Icon.Chevron className="chev" />{x.name}</td>
                    <td>{x.runs?.length ?? "—"}</td>
                    {x.error ? <td colSpan={5} className="muted">{x.error}</td> : <>
                      <td>{n(x.meanSpread)}</td><td>{n(x.stdSpread)}</td>
                      <td style={heat((x.worstRmsPct ?? 0) / maxPct)} title={`${n(x.worstRmsPct, 3)} %`}>{n(x.worstRmsDiff)}</td>
                      <td>{n(x.worstMaxAbs)}</td>
                      <td style={heat(x.minCorrelation === null || x.minCorrelation === undefined ? 0 : (1 - x.minCorrelation) * 2)}>{n(x.minCorrelation, 4)}</td>
                    </>}
                    {data.tol && <td>{x.pass === null || x.pass === undefined ? "" : <span className={`pf ${x.pass ? "ok" : "bad"}`}>{x.pass ? t("pass") : t("fail")}</span>}</td>}
                    <td><button className="btn outline sm" onClick={(e) => { e.stopPropagation(); plotRow(x); }}>{t("plotIt")}</button></td>
                  </tr>,
                  isOpen && (
                    <tr key={x.name + "-d"} className="cmp-detail"><td colSpan={data.tol ? 9 : 8}>
                      <table className="cmp-sub">
                        <thead><tr><th>{t("file")}</th><th>{t("mean")}</th><th>{t("std")}</th><th>{t("minimal")}</th><th>{t("maximal")}</th>
                          <th>{t("meanDiff")}</th><th>{t("stdDiffCol")}</th><th>{t("rmsDiff")}</th><th>{t("maxDiff")}</th><th>{t("corr")}</th>{data.tol && <th>{t("inTol")}</th>}</tr></thead>
                        <tbody>
                          {(x.files ?? []).map((f) => {
                            const d = x.diffs?.find((y) => y.run === f.run);
                            const base = x.baseline === f.run;
                            return (
                              <tr key={f.run} className={base ? "base" : ""}>
                                <td className="nm">{file(f.run)}{base && <span className="tag">{t("baseTag")}</span>}</td>
                                <td>{n(f.mean)}</td><td>{n(f.std)}</td><td>{n(f.min)}</td><td>{n(f.max)}</td>
                                <td>{d ? n(d.meanDiff) : "—"}</td><td>{d ? n(d.stdDiff) : "—"}</td><td>{d ? n(d.rmsDiff) : "—"}</td>
                                <td>{d ? n(d.maxAbsDiff) : "—"}</td><td>{d ? n(d.correlation, 4) : "—"}</td>
                                {data.tol && <td>{d && d.withinPct !== undefined && d.withinPct !== null ? <span className={`pf ${d.pass ? "ok" : "bad"}`}>{n(d.withinPct, 3)}%</span> : ""}</td>}
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </td></tr>
                  ),
                ];
              })}
            </tbody>
          </table>
          {!rows.length && <p className="empty-note">{t("noCommonSignals")}</p>}
          {rows.length > limit && <button className="btn outline more-btn" onClick={() => setLimit(limit + PAGE)}>{t("showMore", { n: rows.length - limit })}</button>}
        </div>
      </div>
    </div>
  );
}
