import { DATA_EXTS } from "../values";
import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { pickPath, useApp } from "../store";
import { translate, useT } from "../i18n";
import { Icon } from "../icons";
import { useEscape } from "./Overlays";
import { DERIVED, homeRun } from "../peers";
import { copyWork, usedNames, type CopyTarget, type SameWorkMode } from "../sameWork";

interface Cand { path: string; name: string; mtime: number; similar: boolean }
const base = (p: string) => p.split(/[\\/]/).pop() || p;

/** Q87 / Q88: copy the work of one open file to another - one already open or one opened now -
 *  each part on its own: the changes (ƒ), the new signals, the plots (none / same plots / new tabs). */
export default function SameWorkDialog() {
  const t = useT();
  const lang = useApp((s) => s.lang);
  const from = useApp((s) => s.sameWorkFor)!;
  const runs = useApp((s) => s.runs);
  const run = runs.find((r) => r.id === from);
  const close = () => useApp.setState({ sameWorkFor: null });
  useEscape(close);
  // the target: "run:<id>" (a file already open) or "path:<file>" (opened now)
  const [path, setPath] = useState("");
  const [cands, setCands] = useState<Cand[]>([]);
  const [check, setCheck] = useState<"idle" | "checking" | "ok" | "missing" | "error">("idle");
  const [missing, setMissing] = useState<string[]>([]);
  const [error, setError] = useState("");
  const [mode, setMode] = useState<SameWorkMode>("overlay");
  const [copyEdits, setCopyEdits] = useState(true);
  const [copyDerived, setCopyDerived] = useState(true);
  const [linkPlots, setLinkPlots] = useState(false);
  const [linkOps, setLinkOps] = useState(false);
  const others = runs.filter((r) => r.format !== DERIVED && r.id !== from);
  const [busy, setBusy] = useState(false);
  const needed = useMemo(() => usedNames(from), [from]);
  const open = useMemo(() => new Set(runs.filter((r) => r.path).map((r) => r.path.replace(/\\/g, "/").toLowerCase())), [runs]);
  const edits = run?.signals.filter((s) => s.transform).length ?? 0;
  const derived = (runs.find((r) => r.format === DERIVED)?.signals ?? []).filter((d) => homeRun(runs, d.id) === from).length;

  const choose = async (v: string) => {
    setPath(v); setCheck("checking"); setMissing([]);
    if (v.startsWith("run:")) {                               // open already: its names are known
      const have = new Set(runs.find((r) => r.id === v.slice(4))?.signals.map((s) => s.name) ?? []);
      const miss = needed.filter((n) => !have.has(n));
      setMissing(miss); setCheck(miss.length ? "missing" : "ok");
      return;
    }
    try {
      const { signals } = await api.fileSignals(v.slice(5), run?.importSettings);
      const have = new Set(signals);
      const miss = needed.filter((n) => !have.has(n));
      setMissing(miss); setCheck(miss.length ? "missing" : "ok");
    } catch (e) { setError(String((e as Error).message)); setCheck("error"); }
  };
  // the suggestion: the newest file with the same name pattern in the same folder, not open already
  useEffect(() => {
    if (!run?.path) return;
    api.suggestFiles(run.path).then((s) => {
      const free = s.candidates.filter((c) => !open.has(c.path.replace(/\\/g, "/").toLowerCase()));
      setCands(free);
      if (!others.length && free.length) choose(`path:${(free.find((c) => c.similar) ?? free[0]).path}`);
    }).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [from]);
  useEffect(() => { if (others.length) choose(`run:${others[0].id}`); // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [from]);
  const other = async () => {
    const p = await pickPath({ mode: "open", title: t("sameWorkPick"), exts: DATA_EXTS });
    if (p) choose(`path:${p}`);
  };

  const apply = async () => {
    setBusy(true);
    try {
      const target: CopyTarget = path.startsWith("run:") ? { run: path.slice(4) } : { path: path.slice(5) };
      const r = await copyWork(from, target, { edits: copyEdits, derived: copyDerived, plots: mode });
      close();
      if (!r) return;
      if (linkPlots) useApp.setState({ linkRuns: true });
      if (linkOps) useApp.setState({ linkEdits: true });
      const st = useApp.getState();
      const name = st.runs.find((x) => x.id === r.to)?.name ?? base(path.slice(5));
      st.toast({ kind: "info", text: translate(lang, mode === "overlay" ? "sameWorkDoneOverlay" : mode === "beside" ? "sameWorkDoneBeside" : mode === "tabs" ? "sameWorkDoneTabs" : "sameWorkDoneNoPlots",
        { name, edits: r.edits, derived: r.derived, plots: r.plots, tabs: r.tabs })
        + (r.besideFull ? ` ${translate(lang, "sameWorkBesideFull", { n: r.besideFull })}` : "")
        + (r.missing.length ? ` ${translate(lang, "sameWorkMissing", { n: r.missing.length, names: r.missing.slice(0, 4).join(", ") + (r.missing.length > 4 ? "…" : "") })}` : "") });
    } catch (e) {
      useApp.getState().toast({ kind: "error", text: String((e as Error).message) });
    } finally { setBusy(false); }
  };
  if (!run) return null;
  const dateOf = (m: number) => new Date(m * 1000).toLocaleString(lang === "he" ? "he-IL" : "en-GB", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });

  return (
    <div className="scrim" onMouseDown={close}>
      <div className="dialog rt-dialog sw-dialog" role="dialog" aria-label={t("sameWorkTitle")} onMouseDown={(e) => e.stopPropagation()}>
        <div className="dialog-head">
          <h2>{t("sameWorkTitle")} <span className="muted">· {run.name}</span></h2>
          <button className="iconbtn" onClick={close} aria-label={t("close")}><Icon.X /></button>
        </div>
        <p className="hint rt-lead">{t("sameWorkLead", { name: run.name })}</p>
        <div className="dialog-body rt-rows">
          <div className="rt-row">
            <div className="rt-old">
              <span className="rt-label">{t("sameWorkLike")}</span>
              <span className="rt-name" title={run.path}>{run.name}</span>
            </div>
            <span className="rt-arrow" aria-hidden="true">+</span>
            <div className="rt-new">
              <div className="rt-pick">
                <select value={path} onChange={(e) => choose(e.target.value)} aria-label={t("newFile")}>
                  {!path && <option value="">{t("sameWorkChoose")}</option>}
                  {others.length > 0 && <optgroup label={t("sameWorkOpenFiles")}>
                    {others.map((r) => <option key={r.id} value={`run:${r.id}`}>{r.name}</option>)}
                  </optgroup>}
                  {cands.length > 0 && <optgroup label={t("sameWorkNewFiles")}>
                    {cands.map((c) => <option key={c.path} value={`path:${c.path}`}>{c.name} · {dateOf(c.mtime)}{c.similar ? "" : " ·  ≠"}</option>)}
                  </optgroup>}
                  {path.startsWith("path:") && !cands.some((c) => `path:${c.path}` === path) && <option value={path}>{base(path.slice(5))}</option>}
                </select>
                <button className="btn outline sm" onClick={other}>{t("otherFile")}</button>
              </div>
              <p className={`rt-status ${check}`}>
                {check === "checking" && t("checkingSignals")}
                {check === "ok" && (needed.length ? t("allSignalsFound", { n: needed.length }) : t("noSignalsNeeded"))}
                {check === "missing" && (missing.length === 1 ? t("signalMissingOne", { names: missing[0] })
                  : t("signalsMissing", { n: missing.length, names: missing.slice(0, 4).join(", ") + (missing.length > 4 ? "…" : "") }))}
                {check === "error" && error}
              </p>
            </div>
          </div>
          <fieldset className="sw-mode">
            <legend>{t("sameWorkWhat")}</legend>
            <label><input type="checkbox" className="sw-edits" checked={copyEdits} disabled={!edits} onChange={(e) => setCopyEdits(e.target.checked)} /> {t("sameWorkEdits", { n: edits })}</label>
            <label><input type="checkbox" className="sw-derived" checked={copyDerived} disabled={!derived} onChange={(e) => setCopyDerived(e.target.checked)} /> {t("sameWorkDerived", { n: derived })}</label>
          </fieldset>
          <fieldset className="sw-mode">
            <legend>{t("sameWorkWhere")}</legend>
            <label><input type="radio" name="sw-mode" checked={mode === "overlay"} onChange={() => setMode("overlay")} /> {t("sameWorkOverlay")}</label>
            <label><input type="radio" name="sw-mode" checked={mode === "beside"} onChange={() => setMode("beside")} /> {t("sameWorkBeside")}</label>
            <label><input type="radio" name="sw-mode" checked={mode === "tabs"} onChange={() => setMode("tabs")} /> {t("sameWorkTabs")}</label>
            <label><input type="radio" name="sw-mode" checked={mode === "none"} onChange={() => setMode("none")} /> {t("sameWorkNoPlots")}</label>
          </fieldset>
          <fieldset className="sw-mode">
            <legend>{t("sameWorkAfter")}</legend>
            <label><input type="checkbox" checked={linkPlots || useApp.getState().linkRuns} disabled={useApp.getState().linkRuns} onChange={(e) => setLinkPlots(e.target.checked)} /> {t("linkFiles")}</label>
            <label><input type="checkbox" checked={linkOps || useApp.getState().linkEdits} disabled={useApp.getState().linkEdits} onChange={(e) => setLinkOps(e.target.checked)} /> {t("linkEdits")}</label>
          </fieldset>
        </div>
        <div className="rt-summary">
          <div><span>{t("editsWord")}</span><b>{copyEdits ? edits : 0}</b></div>
          <div><span>{t("formulasWord")}</span><b>{copyDerived ? derived : 0}</b></div>
          <div><span>{t("layoutWord")}</span><b>{t(mode === "overlay" ? "sameWorkOverlayShort" : mode === "beside" ? "sameWorkBesideShort" : mode === "tabs" ? "sameWorkTabsShort" : "sameWorkNoPlotsShort")}</b></div>
        </div>
        <div className="dialog-foot">
          <span className="hint">{t("retargetFoot")}</span>
          <span className="spacer" />
          <button className="btn outline" onClick={close}>{t("cancel")}</button>
          <button className="btn primary" disabled={!path || busy || check === "checking" || check === "error" || (!copyEdits && !copyDerived && mode === "none")} onClick={apply}>{t(path.startsWith("run:") ? "sameWorkCopy" : "sameWorkAdd")}</button>
        </div>
      </div>
    </div>
  );
}
