import { DATA_EXTS } from "../values";
import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { pickPath, useApp } from "../store";
import { translate, useT } from "../i18n";
import { Icon } from "../icons";
import { useEscape } from "./Overlays";
import { applyState } from "../files";

interface Cand { path: string; name: string; mtime: number; similar: boolean }
interface Row { id: string; oldPath: string; oldName: string; settings: any; newPath: string; cands: Cand[];
  check: "idle" | "checking" | "ok" | "missing" | "error"; missing: string[]; needed: number; error?: string }

const base = (p: string) => p.split(/[\\\\/]/).pop() || p;
const folder = (p: string) => p.slice(0, Math.max(0, p.length - base(p).length - 1));

/** Which signal names of each file the saved work uses (plots, X axes, formulas, edits). */
function neededNames(state: any): Record<string, Set<string>> {
  const out: Record<string, Set<string>> = {};
  const add = (sid?: string | null) => {
    if (!sid || sid.startsWith("derived/")) return;
    const i = sid.indexOf("/");
    (out[sid.slice(0, i)] ??= new Set()).add(sid.slice(i + 1));
  };
  for (const tab of state.ws?.tabs ?? []) for (const p of tab.plots ?? []) { (p.signals ?? []).forEach((s: any) => add(s.sig)); add(p.xSignal); }
  for (const d of state.derived ?? []) (d.sources ?? []).forEach(add);
  Object.keys(state.transforms ?? {}).forEach(add);
  return out;
}

/** Re-open a saved workspace (or the current one) with NEW input files: same layout,
 *  formulas, edits, axes and cursors - only the files change. */
export default function RetargetDialog() {
  const t = useT();
  const lang = useApp((s) => s.lang);
  const job = useApp((s) => s.retarget)!;
  const needed = useMemo(() => neededNames(job.state), [job.state]);
  const [rows, setRows] = useState<Row[]>(() => (job.state.runs ?? []).map((r: any) => ({
    id: r.id, oldPath: r.path, oldName: r.name || base(r.path), settings: r.importSettings, newPath: "", cands: [],
    check: "idle", missing: [], needed: needed[r.id]?.size ?? 0 })));
  const [busy, setBusy] = useState(false);
  const close = () => useApp.setState({ retarget: null });
  useEscape(close);

  const patch = (id: string, p: Partial<Row>) => setRows((rs) => rs.map((r) => (r.id === id ? { ...r, ...p } : r)));
  const check = async (id: string, path: string, settings: any) => {
    patch(id, { newPath: path, check: "checking", missing: [] });
    try {
      const { signals } = await api.fileSignals(path, settings);
      const have = new Set(signals);
      const missing = Array.from(needed[id] ?? []).filter((n) => !have.has(n));
      patch(id, { check: missing.length ? "missing" : "ok", missing });
    } catch (e) { patch(id, { check: "error", error: String((e as Error).message) }); }
  };
  // suggestions: the newest file with the same name pattern in the same folder
  useEffect(() => {
    rows.forEach(async (r) => {
      try {
        const s = await api.suggestFiles(r.oldPath);
        patch(r.id, { cands: s.candidates });
        check(r.id, s.best ?? r.oldPath, r.settings);
      } catch { check(r.id, r.oldPath, r.settings); }
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const other = async (r: Row) => {
    const p = await pickPath({ mode: "open", title: t("chooseNewFile", { name: r.oldName }), exts: DATA_EXTS });
    if (p) check(r.id, p, r.settings);
  };
  const tabs = job.state.ws?.tabs?.length ?? 0;
  const formulas = job.state.derived?.length ?? 0;
  const edits = Object.keys(job.state.transforms ?? {}).length;
  const ready = rows.length > 0 && rows.every((r) => r.newPath && r.check !== "checking" && r.check !== "error");
  const changed = rows.filter((r) => r.newPath && r.newPath !== r.oldPath).length;

  const apply = async () => {
    setBusy(true);
    const before = job.fromCurrent ? job.state : null;
    const next = JSON.parse(JSON.stringify(job.state));
    for (const r of next.runs ?? []) {
      const row = rows.find((x) => x.id === r.id);
      if (row && row.newPath !== r.path) { r.path = row.newPath; r.name = base(row.newPath); }
    }
    try {
      close();
      await applyState(next, { announce: false });
      const st = useApp.getState();
      st.toast({ kind: "info", text: translate(lang, "retargetDone", { n: changed }),
        action: before ? { label: translate(lang, "backToPrevious"), run: () => { applyState(before, { announce: false }); } } : undefined });
    } finally { setBusy(false); }
  };

  const dateOf = (m: number) => new Date(m * 1000).toLocaleString(lang === "he" ? "he-IL" : "en-GB", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
  return (
    <div className="scrim" onMouseDown={close}>
      <div className="dialog rt-dialog" role="dialog" aria-label={t("retargetTitle")} onMouseDown={(e) => e.stopPropagation()}>
        <div className="dialog-head">
          <h2>{t("retargetTitle")} {job.title && <span className="muted">· {job.title}</span>}</h2>
          <button className="iconbtn" onClick={close} aria-label={t("close")}><Icon.X /></button>
        </div>
        <p className="hint rt-lead">{t("retargetLead")}</p>
        <div className="dialog-body rt-rows">
          {rows.map((r) => (
            <div key={r.id} className="rt-row">
              <div className="rt-old">
                <span className="rt-label">{t("wasFile")}</span>
                <span className="rt-name" title={r.oldPath}>{r.oldName}</span>
                <span className="rt-folder" title={r.oldPath}>{folder(r.oldPath)}</span>
              </div>
              <span className="rt-arrow" aria-hidden="true">→</span>
              <div className="rt-new">
                <div className="rt-pick">
                  <select value={r.newPath} onChange={(e) => check(r.id, e.target.value, r.settings)} aria-label={t("newFile")}>
                    <option value={r.oldPath}>{base(r.oldPath)} — {t("keepSameFile")}</option>
                    {r.cands.map((c) => <option key={c.path} value={c.path}>{c.name} · {dateOf(c.mtime)}{c.similar ? "" : " ·  ≠"}</option>)}
                    {r.newPath && r.newPath !== r.oldPath && !r.cands.some((c) => c.path === r.newPath) && <option value={r.newPath}>{base(r.newPath)}</option>}
                  </select>
                  <button className="btn outline sm" onClick={() => other(r)}>{t("otherFile")}</button>
                </div>
                <p className={`rt-status ${r.check}`}>
                  {r.check === "checking" && t("checkingSignals")}
                  {r.check === "ok" && (r.needed ? t("allSignalsFound", { n: r.needed }) : t("noSignalsNeeded"))}
                  {r.check === "missing" && (r.missing.length === 1 ? t("signalMissingOne", { names: r.missing[0] })
                    : t("signalsMissing", { n: r.missing.length, names: r.missing.slice(0, 4).join(", ") + (r.missing.length > 4 ? "…" : "") }))}
                  {r.check === "error" && r.error}
                </p>
              </div>
            </div>
          ))}
        </div>
        <div className="rt-summary">
          <div><span>{t("layoutWord")}</span><b>{tabs === 1 ? t("oneTab") : t("nTabs", { n: tabs })}</b></div>
          <div><span>{t("formulasWord")}</span><b>{formulas}</b></div>
          <div><span>{t("editsWord")}</span><b>{edits}</b></div>
          <div><span>{t("axesCursors")}</span><b>{t("keptWord")}</b></div>
        </div>
        <div className="dialog-foot">
          <span className="hint">{t("retargetFoot")}</span>
          <span className="spacer" />
          <button className="btn outline" onClick={close}>{t("cancel")}</button>
          <button className="btn primary" disabled={!ready || busy} onClick={apply}>{t("openWithNewFiles")}</button>
        </div>
      </div>
    </div>
  );
}
