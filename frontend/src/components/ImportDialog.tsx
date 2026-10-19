import { useEffect, useState } from "react";
import { api } from "../api";
import { useApp } from "../store";
import { useT } from "../i18n";
import { Icon } from "../icons";
import { openPaths } from "../files";

/** Import options with a LIVE preview: every change re-reads the first rows. */
export default function ImportDialog() {
  const t = useT();
  const paths = useApp((s) => s.importPaths);
  const [s, setS] = useState({ has_header: true, header_row: 0, skip_rows: 0, delimiter: "", time_column: "", time_pairs: true });
  const [pv, setPv] = useState<any>(null);
  const [err, setErr] = useState("");
  const path = paths?.[0];
  const isBin = !!path && /\.(bin|tlog|ulg)$/i.test(path);
  const isMat = (!!path && path.toLowerCase().endsWith(".mat")) || isBin;

  const settings = () => ({ ...s, delimiter: s.delimiter || null, time_column: s.time_column || (isMat ? null : "Time") });

  useEffect(() => {
    if (!path) return;
    let cancel = false;
    const h = window.setTimeout(() => {
      api.preview(path, settings()).then((r) => { if (!cancel) { setPv(r); setErr(""); } })
        .catch((e) => { if (!cancel) setErr(String(e.message)); });
    }, 120);
    return () => { cancel = true; window.clearTimeout(h); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, JSON.stringify(s)]);

  if (!paths || !path) return null;
  const close = () => { useApp.setState({ importPaths: null }); setPv(null); };
  const header: string[] = pv?.header ?? [];
  const timeIdx = (() => {
    if (!header.length) return -1;
    const want = s.time_column;
    if (want && header.includes(want)) return header.indexOf(want);
    if (want && /^\d+$/.test(want)) return Number(want);
    const i = header.findIndex((h) => ["time", "t", "timestamp", "time_s"].includes(h.toLowerCase().trim()));
    return i >= 0 ? i : 0;
  })();
  const set = (p: Partial<typeof s>) => setS((cur) => ({ ...cur, ...p }));

  return (
    <div className="scrim" onMouseDown={close}>
      <div className="dialog" style={{ width: "min(820px, 94vw)" }} role="dialog" aria-label={t("importOptions")}
        onMouseDown={(e) => e.stopPropagation()} onKeyDown={(e) => { if (e.key === "Escape") close(); }}>
        <div className="dialog-head"><h2>{t("importOptions")} · {path.split(/[\\/]/).pop()}{paths.length > 1 ? ` (+${paths.length - 1})` : ""}</h2>
          <button className="iconbtn" onClick={close} aria-label={t("close")}><Icon.X /></button></div>
        {isMat ? (
          <div className="dialog-body">
            {isBin ? <p className="hint">{t("binImportNote")}</p> : <div className="import-grid">
              <label style={{ gridColumn: "span 2" }}>{t("timeColumn")}
                <select value={s.time_column || pv?.timeColumn || ""} onChange={(e) => set({ time_column: e.target.value })}>
                  <option value="">{t("auto")}</option>
                  {(pv?.variables ?? []).map((v: any) => <option key={v.name} value={v.name}>{v.name} ({v.length})</option>)}
                </select></label>
            </div>}
            <div className="preview-wrap"><table className="preview"><tbody>
              {(pv?.variables ?? []).map((v: any) => <tr key={v.name}><td>{v.name}</td>{!isBin && <td>{v.length}</td>}</tr>)}
            </tbody></table></div>
          </div>
        ) : (
          <div className="dialog-body">
            <div className="import-grid">
              <label>{t("delimiter")}
                <select value={s.delimiter} onChange={(e) => set({ delimiter: e.target.value })}>
                  <option value="">{t("auto")}{pv?.detectedDelimiter ? ` (${pv.detectedDelimiter === "\t" ? "Tab" : pv.detectedDelimiter})` : ""}</option>
                  <option value=",">,</option><option value=";">;</option><option value={"\t"}>Tab</option><option value="|">|</option>
                </select></label>
              <label>{t("skipRows")}<input type="number" min={0} value={s.skip_rows} onChange={(e) => set({ skip_rows: Math.max(0, +e.target.value) })} /></label>
              <label>{t("header")}<input type="number" min={0} disabled={!s.has_header} value={s.header_row} onChange={(e) => set({ header_row: Math.max(0, +e.target.value) })} /></label>
              <label>{t("timeColumn")}
                <select value={s.time_column} onChange={(e) => set({ time_column: e.target.value })}>
                  <option value="">{t("auto")}</option>
                  {header.map((h, i) => <option key={i} value={s.has_header ? h : String(i)}>{h}</option>)}
                </select></label>
              <label style={{ flexDirection: "row", alignItems: "center", gridColumn: "span 4" }}>
                <input type="checkbox" checked={s.has_header} onChange={(e) => set({ has_header: e.target.checked })} /> {t("hasHeader")}</label>
              <label style={{ flexDirection: "row", alignItems: "center", gridColumn: "span 4" }} title={t("timePairsHint")}>
                <input type="checkbox" checked={s.time_pairs} onChange={(e) => set({ time_pairs: e.target.checked })} /> {t("timePairsOpt")}</label>
            </div>
            {err && <p className="empty-note">{err}</p>}
            <div className="preview-wrap">
              <table className="preview">
                <thead><tr>{header.map((h, i) => <th key={i} className={i === timeIdx ? "time" : ""}>{h}</th>)}</tr></thead>
                <tbody>{(pv?.rows ?? []).map((r: string[], i: number) => <tr key={i}>{r.map((c, j) => <td key={j}>{c}</td>)}</tr>)}</tbody>
              </table>
            </div>
          </div>
        )}
        <div className="dialog-foot">
          <span className="spacer" />
          <button className="btn outline" onClick={close}>{t("cancel")}</button>
          <button className="btn primary" onClick={() => { const p = paths; close(); openPaths(p, settings()); }}>{t("open")}</button>
        </div>
      </div>
    </div>
  );
}
