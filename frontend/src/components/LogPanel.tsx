import { useEffect, useMemo, useState } from "react";
import { api, type HealthReport, type LogEvent, type LogInfo, type LogParam } from "../api";
import { ensureLogs } from "../logs";
import { actions, pickPath, useApp } from "../store";
import { fmtNum, useT } from "../i18n";
import { Icon } from "../icons";
import { runLabels } from "../names";
import HealthRow from "./HealthRow";

/* Flight log of an ArduPilot .bin file: its events (messages, flight modes, events, errors) and
   its parameters. The rail button for this panel exists only while such a file is open, so
   nothing here is seen by anyone working with CSV / MAT files. */

type Kind = LogEvent["kind"];
const KINDS: Kind[] = ["msg", "mode", "event", "error"];

const fmtTime = (t: number, lang: "en" | "he") => fmtNum(t, lang, Math.abs(t) >= 1000 ? 7 : 5);
const fmtParam = (v: number) => (Number.isInteger(v) ? String(v) : String(Number(v.toPrecision(7))));
const toParamFile = (ps: LogParam[]) => ps.map((p) => `${p.name},${fmtParam(p.value)}`).join("\r\n") + "\r\n";

export default function LogPanel() {
  const t = useT();
  const lang = useApp((s) => s.lang);
  const runs = useApp((s) => s.runs);
  const logs = useApp((s) => s.logs);
  const markers = useApp((s) => s.logMarkers);
  const cursorT = useApp((s) => (s.cursor.on ? s.cursor.t1 : null));
  const logRuns = runs.filter((r) => r.log);
  const names = runLabels(runs);
  const [rid, setRid] = useState<string | null>(null);
  const run = logRuns.find((r) => r.id === rid) ?? logRuns[0];
  const info = run ? logs[run.id] : undefined;
  const [tab, setTab] = useState<"health" | "events" | "params">("health");

  useEffect(() => { ensureLogs(); }, [runs]);

  if (!run) {
    return (
      <aside className="side" aria-label={t("flightLog")}>
        <div className="side-head"><h2>{t("flightLog")}</h2></div>
        <p className="hint" style={{ padding: "0 14px" }}>{t("logNone")}</p>
      </aside>
    );
  }
  return (
    <aside className="side log-panel" aria-label={t("flightLog")}>
      <div className="side-head"><h2>{t("flightLog")}</h2></div>
      {logRuns.length > 1 && (
        <label className="afield log-file"><span>{t("file")}</span>
          <select value={run.id} onChange={(e) => setRid(e.target.value)}>
            {logRuns.map((r) => <option key={r.id} value={r.id}>{names.get(r.id) ?? r.name}</option>)}
          </select></label>
      )}
      {info?.firmware && <div className="log-fw" title={info.firmware}>{info.firmware}</div>}
      {runs.filter((r) => r.id !== run.id && r.format !== "derived").length > 0 && (
        <div className="log-actions">
          <button className="btn" onClick={() => useApp.setState({ syncFor: run.id })} title={t("syncMenu")}><Icon.Link /> {t("syncShort")}</button>
        </div>
      )}
      <div className="seg wide log-tabs" role="tablist">
        <button role="tab" aria-selected={tab === "health"} className={tab === "health" ? "on" : ""} onClick={() => setTab("health")}>
          {t("logHealth")}
        </button>
        <button role="tab" aria-selected={tab === "events"} className={tab === "events" ? "on" : ""} onClick={() => setTab("events")}>
          {t("logEvents")} <span className="cnt">{run.log!.events}</span>
          {run.log!.errors > 0 && <span className="lvl-dot error" title={t("logErrorsN", { n: run.log!.errors })} />}
        </button>
        <button role="tab" aria-selected={tab === "params"} className={tab === "params" ? "on" : ""} onClick={() => setTab("params")}>
          {t("logParams")} <span className="cnt">{run.log!.params}</span>
        </button>
      </div>
      {!info ? <p className="hint" style={{ padding: "0 14px" }}>…</p>
        : tab === "health" ? <Health key={run.id} runId={run.id} runKey={`${run.samples}:${run.log!.events}:${run.timeOffset}`} />
        : tab === "events" ? <Events key={run.id} info={info} lang={lang} cursorT={cursorT} markers={markers} />
          : <Params key={run.id} info={info} lang={lang} others={logRuns.filter((r) => r.id !== run.id).map((r) => ({ id: r.id, name: names.get(r.id) ?? r.name }))} />}
    </aside>
  );
}

/* ------------------------------------------------------------------------- events */
function Events({ info, lang, cursorT, markers }: { info: LogInfo; lang: "en" | "he"; cursorT: number | null; markers: string }) {
  const t = useT();
  const [q, setQ] = useState("");
  const [kinds, setKinds] = useState<Record<Kind, boolean>>({ msg: true, mode: true, event: true, error: true });
  const [important, setImportant] = useState(false);
  const off = info.timeOffset || 0;
  const counts = useMemo(() => {
    const c: Record<Kind, number> = { msg: 0, mode: 0, event: 0, error: 0 };
    info.events.forEach((e) => { c[e.kind]++; });
    return c;
  }, [info]);
  const shown = useMemo(() => {
    const ql = q.trim().toLowerCase();
    return info.events.filter((e) => kinds[e.kind] && (!important || e.level !== "info") && (!ql || e.text.toLowerCase().includes(ql)));
  }, [info, q, kinds, important]);
  // the event in force at the cursor (the last one at or before it)
  const current = useMemo(() => {
    if (cursorT === null) return -1;
    let k = -1;
    shown.forEach((e, i) => { if (e.t + off <= cursorT + 1e-9) k = i; });
    return k;
  }, [shown, cursorT, off]);
  useEffect(() => {
    if (current >= 0) document.getElementById(`logev-${current}`)?.scrollIntoView({ block: "nearest" });
  }, [current]);

  return (
    <>
      <label className="filter">
        <Icon.Search />
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder={t("logSearchEvents")} aria-label={t("logSearchEvents")} />
        {q && <button className="iconbtn" style={{ height: 20, minWidth: 20 }} onClick={() => setQ("")} aria-label={t("close")}><Icon.X /></button>}
      </label>
      <div className="log-chips" role="group" aria-label={t("logKinds")}>
        {KINDS.filter((k) => counts[k] > 0).map((k) => (
          <button key={k} className={`chipbtn ${kinds[k] ? "on" : ""}`} aria-pressed={kinds[k]} onClick={() => setKinds({ ...kinds, [k]: !kinds[k] })}>
            <span className={`kind-dot ${k}`} />{t(`logKind_${k}` as "logKind_msg")} <span className="cnt">{counts[k]}</span>
          </button>
        ))}
        <button className={`chipbtn ${important ? "on" : ""}`} aria-pressed={important} onClick={() => setImportant(!important)}>
          <span className="lvl-dot warning" />{t("logImportant")}
        </button>
      </div>
      <ol className="log-list" aria-label={t("logEvents")}>
        {shown.map((e, i) => (
          <li key={i} id={`logev-${i}`}>
            <button className={`log-row lvl-${e.level}${i === current ? " current" : ""}`} onClick={() => actions.goToTime(e.t + off)}
              title={t("logGoTo")}>
              <span className="log-t">{fmtTime(e.t + off, lang)}</span>
              <span className={`kind-dot ${e.kind}`} aria-label={t(`logKind_${e.kind}` as "logKind_msg")} />
              <span className="log-text">{e.text}</span>
            </button>
          </li>
        ))}
        {!shown.length && <li className="hint" style={{ padding: "6px 14px" }}>{t("logNoMatch")}</li>}
      </ol>
      <label className="afield log-markers"><span>{t("logOnPlots")}</span>
        <select value={markers} onChange={(e) => useApp.setState({ logMarkers: e.target.value as "off" | "important" | "all" })}>
          <option value="important">{t("logMarkersImportant")}</option>
          <option value="all">{t("logMarkersAll")}</option>
          <option value="off">{t("logMarkersOff")}</option>
        </select></label>
    </>
  );
}

/* ------------------------------------------------------------------------- parameters */
type PFilter = "all" | "changed" | "nondefault" | "diff";

function Params({ info, lang, others }: { info: LogInfo; lang: "en" | "he"; others: { id: string; name: string }[] }) {
  const t = useT();
  const logs = useApp((s) => s.logs);
  const [q, setQ] = useState("");
  const [filter, setFilter] = useState<PFilter>("all");
  const [other, setOther] = useState<string>(others[0]?.id ?? "");
  const off = info.timeOffset || 0;
  const otherInfo = filter === "diff" && other ? logs[other] : undefined;
  const otherMap = useMemo(() => new Map((otherInfo?.params ?? []).map((p) => [p.name, p.value])), [otherInfo]);
  const changedN = info.params.filter((p) => p.changes.length).length;
  const nonDefN = info.params.filter((p) => p.default !== null && p.default !== p.value).length;

  const shown = useMemo(() => {
    const ql = q.trim().toLowerCase();
    let ps = info.params;
    if (filter === "changed") ps = ps.filter((p) => p.changes.length);
    else if (filter === "nondefault") ps = ps.filter((p) => p.default !== null && p.default !== p.value);
    else if (filter === "diff" && otherInfo) {
      const names = new Set([...ps.map((p) => p.name), ...otherInfo.params.map((p) => p.name)]);
      const mine = new Map(ps.map((p) => [p.name, p]));
      ps = [...names].sort().filter((n) => mine.get(n)?.value !== otherMap.get(n))
        .map((n) => mine.get(n) ?? { name: n, value: NaN, first: NaN, default: null, changes: [] });
    }
    return ql ? ps.filter((p) => p.name.toLowerCase().includes(ql)) : ps;
  }, [info, q, filter, otherInfo, otherMap]);

  const copy = async () => {
    try { await navigator.clipboard.writeText(toParamFile(shown.filter((p) => Number.isFinite(p.value)))); useApp.getState().toast({ kind: "info", text: t("logParamsCopied", { n: shown.length }) }); }
    catch { useApp.getState().toast({ kind: "error", text: t("copyFailed") }); }
  };
  const save = async () => {
    const path = await pickPath({ mode: "save", title: t("logSaveParams"), exts: [".param"], defaultName: "params.param" });
    if (!path) return;
    try {
      const r = await api.saveText(path, toParamFile(shown.filter((p) => Number.isFinite(p.value))), ".param", false);
      useApp.getState().toast({ kind: "info", text: t("savedTo", { path: r.path }) });
    } catch (e) { useApp.getState().toast({ kind: "error", text: String((e as Error).message) }); }
  };

  return (
    <>
      <label className="filter">
        <Icon.Search />
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder={t("logSearchParams")} aria-label={t("logSearchParams")} />
        {q && <button className="iconbtn" style={{ height: 20, minWidth: 20 }} onClick={() => setQ("")} aria-label={t("close")}><Icon.X /></button>}
      </label>
      <div className="log-chips" role="group">
        <button className={`chipbtn ${filter === "all" ? "on" : ""}`} aria-pressed={filter === "all"} onClick={() => setFilter("all")}>{t("logAll")}</button>
        {changedN > 0 && <button className={`chipbtn ${filter === "changed" ? "on" : ""}`} aria-pressed={filter === "changed"} onClick={() => setFilter("changed")}
          title={t("logChangedHint")}>{t("logChanged")} <span className="cnt">{changedN}</span></button>}
        {info.hasDefaults && <button className={`chipbtn ${filter === "nondefault" ? "on" : ""}`} aria-pressed={filter === "nondefault"} onClick={() => setFilter("nondefault")}>
          {t("logNotDefault")} <span className="cnt">{nonDefN}</span></button>}
        {others.length > 0 && <button className={`chipbtn ${filter === "diff" ? "on" : ""}`} aria-pressed={filter === "diff"} onClick={() => setFilter("diff")}>{t("logDiff")}</button>}
      </div>
      {filter === "diff" && others.length > 0 && (
        <label className="afield log-file"><span>{t("logCompareWith")}</span>
          <select value={other} onChange={(e) => setOther(e.target.value)}>
            {others.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
          </select></label>
      )}
      <div className="log-params" role="table" aria-label={t("logParams")}>
        <div className="prow head" role="row">
          <span role="columnheader">{t("logName")}</span>
          <span role="columnheader">{filter === "diff" ? t("logThisFile") : t("logValue")}</span>
          {filter === "diff" && <span role="columnheader">{t("logOtherFile")}</span>}
        </div>
        {shown.map((p) => {
          const us = p.name.indexOf("_");
          const nonDef = p.default !== null && p.default !== p.value;
          return (
            <div key={p.name} className="prow" role="row">
              <span className="pname" role="cell" title={p.name}>
                {us > 0 ? <><b>{p.name.slice(0, us)}</b>{p.name.slice(us)}</> : <b>{p.name}</b>}
              </span>
              <span className={`pval${nonDef ? " nondef" : ""}`} role="cell"
                title={nonDef ? t("logDefaultIs", { v: fmtParam(p.default!) }) : undefined}>
                {Number.isFinite(p.value) ? fmtParam(p.value) : "—"}
                {nonDef && filter !== "diff" && <span className="pdef">{fmtParam(p.default!)}</span>}
              </span>
              {filter === "diff" && <span className="pval other" role="cell">{otherMap.has(p.name) ? fmtParam(otherMap.get(p.name)!) : "—"}</span>}
              {p.changes.length > 0 && filter !== "diff" && (
                <span className="pchanges" role="cell">
                  {fmtParam(p.first)}
                  {p.changes.map(([ct, v], i) => (
                    <button key={i} className="pchange" onClick={() => actions.goToTime(ct + off)} title={t("logGoTo")}>
                      → {fmtParam(v)} <span className="at">@ {fmtTime(ct + off, lang)}</span>
                    </button>
                  ))}
                </span>
              )}
            </div>
          );
        })}
        {!shown.length && <div className="hint" style={{ padding: "6px 14px" }}>{t("logNoMatch")}</div>}
      </div>
      <div className="log-foot">
        <button className="btn" onClick={copy} disabled={!shown.length}><Icon.Copy /> {t("logCopy")}</button>
        <button className="btn" onClick={save} disabled={!shown.length}><Icon.Save /> {t("logSaveParams")}</button>
      </div>
      <p className="hint log-note">{filter === "all" && !q ? t("logParamNote") : t("logParamNoteShown", { n: shown.length })}</p>
    </>
  );
}

/* ------------------------------------------------------------------------- health check */
function Health({ runId, runKey }: { runId: string; runKey: string }) {
  const t = useT();
  const [rep, setRep] = useState<HealthReport | null | "none">(null);
  useEffect(() => {
    let off = false;
    api.runHealth(runId).then((r) => { if (!off) setRep(r); }).catch(() => { if (!off) setRep("none"); });
    return () => { off = true; };
  }, [runId, runKey]);
  if (rep === null) return <p className="hint" style={{ padding: "0 14px" }}>…</p>;
  if (rep === "none") return <p className="hint" style={{ padding: "0 14px" }}>{t("healthNone")}</p>;
  return (
    <div className="health">
      <p className={`health-sum ${rep.errors ? "error" : rep.warnings ? "warning" : "ok"}`}>
        {rep.errors || rep.warnings ? t("healthSummary", { e: rep.errors, w: rep.warnings }) : t("healthAllOk")}
      </p>
      <ol className="health-list">
        {rep.findings.map((f, i) => <HealthRow key={i} f={f} runId={runId} />)}
      </ol>
      <p className="hint log-note">{t("healthNote")}</p>
    </div>
  );
}
