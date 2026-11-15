/* L5 F4: live instruments for any source - a MAVLink link, *Send data from Python*, a followed file, or a
   recording. Each tile is a signal's value IN FORCE at the time (the last sample received at or before it,
   never interpolated); while live the time stays at the newest data, so the tiles follow the source. The
   attitude indicator shows the object the map draws for this file (objectDetect: one rule for "is this a
   position / an attitude"). Tiles: the session's own list, else the template's at-a-glance names. */
import { useEffect, useMemo, useRef, useState } from "react";
import { api, type InstrumentObject, type InstrumentState, type InstrumentValue } from "../api";
import { actions, useApp } from "../store";
import type { MapObject } from "../store";
import { fmtNum, useT } from "../i18n";
import { detectObjects } from "../objectDetect";
import { INSTRUMENTS_MAX } from "../store/actions/profile";
import FlightDisplay from "./FlightDisplay";

/** A reading is flagged late when it is older than this (s) and than LATE_STEPS of its own typical interval:
 *  the source may have stopped sending. A state is never late - its age is how long it has held. */
const STALE_S = 3, LATE_STEPS = 5;
const isLate = (v: InstrumentValue | undefined) =>
  !!v && !v.state && v.age !== null && v.age > Math.max(STALE_S, LATE_STEPS * (v.step ?? 0));
const ROLES = ["roll", "pitch", "yaw", "qw", "qx", "qy", "qz", "lat", "lon", "alt"] as const;

/** The object of this run the map would draw: one the user placed on a map (their angle unit), else the
 *  first one detection proposes. */
function useRunObject(runId: string): { name: string; sigs: InstrumentObject } | null {
  const tabs = useApp((s) => s.ws.tabs);
  const run = useApp((s) => s.runs.find((r) => r.id === runId));
  return useMemo(() => {
    const own = (o: MapObject) => o.lat.startsWith(`${runId}/`);
    for (const tab of tabs) for (const p of tab.plots) {
      const o = (p.objects ?? []).find(own);
      if (o) {
        const sigs: InstrumentObject = {};
        for (const r of ROLES) { const v = o[r]; if (v) sigs[r] = v; }
        if (o.angleUnit === "deg" || o.angleUnit === "rad") sigs.angleUnit = o.angleUnit;
        return { name: o.name, sigs };
      }
    }
    if (!run) return null;
    const c = detectObjects(run).candidates.find((x) => x.attitude !== "none") ?? detectObjects(run).candidates[0];
    if (!c) return null;
    const sigs: InstrumentObject = {};
    for (const r of ROLES) { const p = c.picks[r]; if (p) sigs[r] = p.id; }
    return { name: c.name, sigs };
  }, [tabs, run, runId]);
}

export default function Instruments({ runId, runKey }: { runId: string; runKey: string }) {
  const t = useT();
  const lang = useApp((s) => s.lang);
  const streaming = useApp((s) => s.streaming);
  const run = useApp((s) => s.runs.find((r) => r.id === runId));
  const cursorT = useApp((s) => (s.cursor.on ? s.cursor.t1 : null));
  const own = useApp((s) => s.ws.instruments);
  const glance = useApp((s) => s.ws.glance);
  const fromProfile = !own;
  const names = useMemo(() => own ?? [...new Set((glance ?? []).map((g) => g.name))], [own, glance]);
  const obj = useRunObject(runId);
  // the time: the cursor (pinned to the newest data while live), else this file's end
  const time = cursorT ?? (run && Number.isFinite(run.end) ? run.end : null);
  const [vals, setVals] = useState<InstrumentValue[] | null>(null);
  const [att, setAtt] = useState<InstrumentState | null>(null);
  // one request at a time; the newest wanted time is sent when the one in flight returns (live: ~1 per poll)
  const busy = useRef(false), want = useRef<(() => void) | null>(null);
  useEffect(() => {
    if (time === null) { setVals(null); setAtt(null); return; }
    let gone = false;
    const go = () => {
      busy.current = true;
      api.instruments(runId, time, names, obj && Object.keys(obj.sigs).length ? obj.sigs : null)
        .then((r) => { if (!gone) { setVals(r.items); setAtt(r.object); } })
        .catch(() => { if (!gone) setVals(null); })
        .finally(() => { busy.current = false; const next = want.current; want.current = null; next?.(); });
    };
    if (busy.current) want.current = go; else go();
    return () => { gone = true; };
  }, [runId, runKey, time, names, obj]);

  const shown = (n: string) => n.split("|")[0];
  const allNames = useMemo(() => (run?.signals ?? []).map((s) => s.name), [run]);
  const hasAtt = !!att && (att.roll !== null || att.pitch !== null);
  return (
    <div className="instruments" data-tiles={names.length} data-live={streaming ? "1" : "0"}>
      <p className="card-meta ins-when">
        {time === null ? t("insNoTime") : streaming ? <><span className="live-dot on" /> {t("insLive")}</> : t("insAtTime", { t: fmtNum(time, lang, 7) })}
      </p>
      {hasAtt && obj && (
        <div className="ins-att" title={t("insAttitudeWhy", { name: obj.name })} data-roll={att!.roll ?? ""} data-yaw={att!.yaw ?? ""}>
          <FlightDisplay s={{ name: obj.name, roll: att!.roll, pitch: att!.pitch, hdg: att!.yaw, gs: att!.gs, alt: att!.alt ?? NaN, agl: null }} />
        </div>
      )}
      {!names.length ? <div className="empty-state"><p>{t("insNone")}</p></div> : (
        <>
          {fromProfile && <p className="eyebrow">{t("insFromProfile")}</p>}
          <div className="kpis ins-tiles">
            {names.map((n, i) => {
              const v = vals?.find((x) => x.name === n) ?? vals?.[i];
              const stale = isLate(v);
              // the file's name of the signal, its unit shown once (beside the number)
              const full = v?.sig ? v.sig.slice(runId.length + 1) : shown(n);
              const label = v?.unit ? full.replace(/\s*\[[^\]]*\]$/, "") : full;
              return (
                <div key={n} className={`card kpi ins-tile${stale ? " warn" : ""}${v && !v.sig ? " ins-missing" : ""}`} data-name={n}
                  data-value={v?.value ?? ""}>
                  <div className="ins-tile-head">
                    <span className="kpi-label" title={full}>{label}</span>
                    <button className="iconbtn ins-x" aria-label={t("insRemove", { name: label })} title={t("insRemove", { name: label })}
                      onClick={() => actions.removeInstrument(n, names)}>×</button>
                  </div>
                  {!v ? <span className="kpi-value">…</span>
                    : !v.sig ? <span className="card-meta">{t("insMissing")}</span>
                    : v.value === null ? <span className="card-meta">{t("insNoSample")}</span>
                    : <span className="ins-read" dir="ltr"><span className="kpi-value">{v.text ?? fmtNum(v.value, lang, 4)}</span>{!v.text && v.unit && <span className="kpi-unit">{v.unit}</span>}</span>}
                  {stale && <span className="card-meta" title={t("insAgeHint", { s: fmtNum(v!.age!, lang, 3) })}>{t("insAge", { s: fmtNum(v!.age!, lang, 3) })}</span>}
                </div>
              );
            })}
          </div>
        </>
      )}
      <div className="ins-add">
        <select aria-label={t("insAdd")} value="" title={names.length >= INSTRUMENTS_MAX ? t("insFull", { n: INSTRUMENTS_MAX }) : t("insAddHint")}
          disabled={names.length >= INSTRUMENTS_MAX}
          onChange={(e) => { if (e.target.value) actions.addInstrument(e.target.value, names); }}>
          <option value="">{t("insAdd")}</option>
          {allNames.filter((n) => !names.includes(n)).map((n) => <option key={n} value={n}>{n}</option>)}
        </select>
      </div>
    </div>
  );
}
