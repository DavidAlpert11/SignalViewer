import { DATA_EXTS } from "../values";
import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { pickPath, useApp } from "../store";
import { translate, useT } from "../i18n";
import { Icon } from "../icons";
import { useEscape } from "./Overlays";
import { DERIVED, homeRun } from "../peers";
import { addRunLike, usedNames, type SameWorkMode } from "../sameWork";

interface Cand { path: string; name: string; mtime: number; similar: boolean }
const base = (p: string) => p.split(/[\\/]/).pop() || p;

/** Q87: open another file with the work of one open file - on the same plots or in new tabs. */
export default function SameWorkDialog() {
  const t = useT();
  const lang = useApp((s) => s.lang);
  const from = useApp((s) => s.sameWorkFor)!;
  const runs = useApp((s) => s.runs);
  const run = runs.find((r) => r.id === from);
  const close = () => useApp.setState({ sameWorkFor: null });
  useEscape(close);
  const [path, setPath] = useState("");
  const [cands, setCands] = useState<Cand[]>([]);
  const [check, setCheck] = useState<"idle" | "checking" | "ok" | "missing" | "error">("idle");
  const [missing, setMissing] = useState<string[]>([]);
  const [error, setError] = useState("");
  const [mode, setMode] = useState<SameWorkMode>("overlay");
  const [link, setLink] = useState(true);
  const [busy, setBusy] = useState(false);
  const needed = useMemo(() => usedNames(from), [from]);
  const open = useMemo(() => new Set(runs.filter((r) => r.path).map((r) => r.path.replace(/\\/g, "/").toLowerCase())), [runs]);
  const edits = run?.signals.filter((s) => s.transform).length ?? 0;
  const derived = (runs.find((r) => r.format === DERIVED)?.signals ?? []).filter((d) => homeRun(runs, d.id) === from).length;

  const choose = async (p: string) => {
    setPath(p); setCheck("checking"); setMissing([]);
    try {
      const { signals } = await api.fileSignals(p, run?.importSettings);
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
      if (free.length) choose((free.find((c) => c.similar) ?? free[0]).path);
    }).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [from]);
  const other = async () => {
    const p = await pickPath({ mode: "open", title: t("sameWorkPick"), exts: DATA_EXTS });
    if (p) choose(p);
  };

  const apply = async () => {
    setBusy(true);
    try {
      const r = await addRunLike(from, path, mode);
      close();
      if (!r) return;
      if (link) useApp.setState({ linkRuns: true, linkEdits: true });
      const st = useApp.getState();
      const name = st.runs.find((x) => x.id === r.to)?.name ?? base(path);
      st.toast({ kind: "info", text: translate(lang, mode === "overlay" ? "sameWorkDoneOverlay" : "sameWorkDoneTabs",
        { name, edits: r.edits, derived: r.derived, plots: r.plots, tabs: r.tabs })
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
                  {cands.map((c) => <option key={c.path} value={c.path}>{c.name} · {dateOf(c.mtime)}{c.similar ? "" : " ·  ≠"}</option>)}
                  {path && !cands.some((c) => c.path === path) && <option value={path}>{base(path)}</option>}
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
            <legend>{t("sameWorkWhere")}</legend>
            <label><input type="radio" name="sw-mode" checked={mode === "overlay"} onChange={() => setMode("overlay")} /> {t("sameWorkOverlay")}</label>
            <label><input type="radio" name="sw-mode" checked={mode === "tabs"} onChange={() => setMode("tabs")} /> {t("sameWorkTabs")}</label>
          </fieldset>
          <label className="acheck"><input type="checkbox" checked={link} onChange={(e) => setLink(e.target.checked)} /> {t("sameWorkLink")}</label>
        </div>
        <div className="rt-summary">
          <div><span>{t("editsWord")}</span><b>{edits}</b></div>
          <div><span>{t("formulasWord")}</span><b>{derived}</b></div>
          <div><span>{t("layoutWord")}</span><b>{t(mode === "overlay" ? "sameWorkOverlayShort" : "sameWorkTabsShort")}</b></div>
        </div>
        <div className="dialog-foot">
          <span className="hint">{t("retargetFoot")}</span>
          <span className="spacer" />
          <button className="btn outline" onClick={close}>{t("cancel")}</button>
          <button className="btn primary" disabled={!path || busy || check === "checking" || check === "error"} onClick={apply}>{t("sameWorkAdd")}</button>
        </div>
      </div>
    </div>
  );
}
