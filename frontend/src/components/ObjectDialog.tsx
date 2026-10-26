import { useMemo, useState } from "react";
import { actions, nextColor, uid, useApp, type MapObject, type ObjectKind } from "../store";
import { useT, type TKey } from "../i18n";
import { iconSvg, OBJECT_KINDS } from "./mapIcons";
import { guessRoles, QUAT_ROLES, ROLES, type Role } from "../mapObjects";
import { useEscape } from "./Overlays";
import SignalField from "./SignalField";
import { AXES, createFrameGroup, createSmoothGroup, frameGroupName } from "../frames";
import type { SignalInfo } from "../api";

/* Q101 / Q102: the position may come in ECEF, NED or ENU (m) instead of latitude / longitude, and
   may be smoothed over a window in seconds. Both are derived signals ("frame" position -> LLA, then
   "vecsmooth"), made when the object is saved; the object points at their lat / lon / alt, so
   sessions, live mode and the rest of the app need nothing new. Editing reads the chain back. */
type PosFrame = "lla" | "ecef" | "ned" | "enu";
interface PosSetup { frame: PosFrame; vec: string[]; refMode: "signals" | "manual"; refSigs: string[]; refLla: string[];
  lat: string; lon: string; alt: string | null; smooth: number }

/** How an object's lat / lon / alt were made (a chain of "vecsmooth" and "frame" derived signals). */
function readSetup(o: MapObject, derived: SignalInfo[]): PosSetup {
  const of = (id?: string | null) => (id && id.startsWith("derived/") ? derived.find((s) => s.id === id) : undefined);
  const out: PosSetup = { frame: "lla", vec: ["", "", ""], refMode: "signals", refSigs: ["", "", ""], refLla: ["", "", ""],
    lat: o.lat, lon: o.lon, alt: o.alt ?? null, smooth: 0 };
  const sm = of(o.lat);
  if (sm?.op === "vecsmooth" && sm.params?.kind === "lla" && sm.sources && sm.sources.length >= 2) {
    out.smooth = Number(sm.params.window) || 0;
    [out.lat, out.lon] = sm.sources;
    out.alt = sm.sources[2] ?? null;
  }
  const fr = of(out.lat);
  const p = fr?.params ?? {};
  if (fr?.op === "frame" && p.qty === "position" && p.dst === "lla" && ["ecef", "ned", "enu"].includes(String(p.src)) && fr.sources) {
    out.frame = p.src as PosFrame;
    out.vec = fr.sources.slice(0, 3);
    if (p.ref === "manual") { out.refMode = "manual"; out.refLla = [p.ref_lat, p.ref_lon, p.ref_alt].map((v) => String(v ?? "")); }
    else out.refSigs = fr.sources.slice(3, 6).concat(["", "", ""]).slice(0, 3);
  }
  return out;
}
const setupKey = (p: PosSetup) => JSON.stringify(p.frame === "lla" ? [p.frame, p.lat, p.lon, p.alt, p.smooth]
  : [p.frame, p.vec, p.frame === "ecef" ? null : p.refMode === "manual" ? p.refLla.map(Number) : p.refSigs, p.smooth]);

/* Adding / editing a map object: what it is (aircraft, ship...), its colour, and which signals give
   its position and attitude - each from any open file. Picking a file fills in the signals by their
   names (GPS.Lat / Lng / Alt together, angles from the attitude group). */

export default function ObjectDialog() {
  const t = useT();
  const req = useApp((s) => s.objectDialog);
  const runs = useApp((s) => s.runs);
  const ws = useApp((s) => s.ws);
  const data = useMemo(() => runs.filter((r) => r.format !== "derived"), [runs]);
  const plot = useMemo(() => ws.tabs.flatMap((tb) => tb.plots).find((p) => p.id === req?.plotId), [ws, req]);
  const editing = plot?.objects?.find((o) => o.id === req?.objectId) ?? null;
  const close = () => useApp.setState({ objectDialog: null });
  useEscape(close, !!req);

  const [o, setO] = useState<MapObject>(() => {
    if (editing) return { ...editing };
    const run = data[0];
    const g = run ? guessRoles(run) : {};
    const n = (plot?.objects?.length ?? 0) + 1;
    return { id: uid("o"), name: `${t("obj_aircraft")} ${n}`, kind: "aircraft", color: nextColor(ws), lat: g.lat ?? "", lon: g.lon ?? "",
      alt: g.alt ?? null, yaw: g.yaw ?? null, pitch: g.pitch ?? null, roll: g.roll ?? null,
      qw: g.qw ?? null, qx: g.qx ?? null, qy: g.qy ?? null, qz: g.qz ?? null, angleUnit: "auto", trail: true };
  });
  const runOf = (sig?: string | null) => (sig ? sig.slice(0, sig.indexOf("/")) : "");
  const [mainRun, setMainRun] = useState(runOf(o.lat) || data[0]?.id || "");
  // the attitude: three angles, or a quaternion (four signals - e.g. a PX4 log has only that)
  const [quat, setQuat] = useState(!!o.qw);
  const derivedSigs = runs.find((r) => r.format === "derived")?.signals ?? [];
  const [orig] = useState<PosSetup | null>(() => (editing ? readSetup(editing, derivedSigs) : null));
  const [pos, setPos] = useState<PosSetup>(() => {
    if (orig) return { ...orig };
    const g = data[0] ? guessRoles(data[0]) : {};
    return { frame: "lla", vec: ["", "", ""], refMode: g.lat && g.lon && g.alt ? "signals" : "manual",
      refSigs: [g.lat ?? "", g.lon ?? "", g.alt ?? ""], refLla: ["", "", ""], lat: o.lat, lon: o.lon, alt: o.alt ?? null, smooth: 0 };
  });
  const [smoothText, setSmoothText] = useState(String(orig?.smooth ?? 0));
  const [busy, setBusy] = useState(false);
  if (!req || !plot) return null;

  const fillFrom = (rid: string) => {
    setMainRun(rid);
    const run = data.find((r) => r.id === rid);
    if (!run) return;
    const g = guessRoles(run);
    setO((c) => ({ ...c, yaw: g.yaw ?? null, pitch: g.pitch ?? null, roll: g.roll ?? null,
      qw: g.qw ?? null, qx: g.qx ?? null, qy: g.qy ?? null, qz: g.qz ?? null }));
    setPos((c) => ({ ...c, lat: g.lat ?? "", lon: g.lon ?? "", alt: g.alt ?? null,
      refSigs: c.refSigs.every((x) => !x) ? [g.lat ?? "", g.lon ?? "", g.alt ?? ""] : c.refSigs }));
    setQuat(!!g.qw);
  };
  const setKind = (k: ObjectKind) => setO((c) => {
    // a default name follows the kind ("Aircraft 1" -> "Ship 1"); a name the user typed stays
    const def = OBJECT_KINDS.some((kk) => c.name.startsWith(t(`obj_${kk}` as TKey)));
    return { ...c, kind: k, name: def ? c.name.replace(/^\S+(\s.*)?$/, `${t(`obj_${k}` as TKey)}$1`) : c.name };
  });
  const smooth = Number(smoothText);
  const smoothOk = smoothText.trim() !== "" && Number.isFinite(smooth) && smooth >= 0;
  const local = pos.frame === "ned" || pos.frame === "enu";
  const refOk = !local || (pos.refMode === "signals" ? pos.refSigs.every((x) => !!x)
    : pos.refLla.every((x) => x.trim() !== "" && Number.isFinite(Number(x))) && Math.abs(Number(pos.refLla[0])) <= 90);
  const posOk = pos.frame === "lla" ? !!pos.lat && !!pos.lon : pos.vec.every((x) => !!x) && refOk;
  const ok = posOk && smoothOk && !!o.name.trim();
  const save = async () => {
    if (!ok || busy) return;
    const want: PosSetup = { ...pos, smooth };
    let ids: [string, string, string | null];
    setBusy(true);
    try {
      if (orig && setupKey(orig) === setupKey(want)) {
        ids = [o.lat, o.lon, o.alt ?? null];                 // the same as before: no new signals
      } else {
        if (want.frame === "lla") ids = [want.lat, want.lon, want.alt];
        else {
          const ref = want.frame === "ecef" ? {} : want.refMode === "manual"
            ? { ref: "manual", ref_lat: Number(want.refLla[0]), ref_lon: Number(want.refLla[1]), ref_alt: Number(want.refLla[2]) }
            : { ref: "signals" };
          const src = [...want.vec, ...(local && want.refMode === "signals" ? want.refSigs : [])];
          const f = await createFrameGroup(src, { qty: "position", src: want.frame, dst: "lla", ...ref }, frameGroupName(want.frame, "lla", "position"));
          ids = [f[0], f[1], f[2]];
        }
        if (smooth > 0) {
          const s3 = await createSmoothGroup(ids.filter((x): x is string => !!x), smooth, "lla");
          ids = [s3[0], s3[1], s3[2] ?? null];
        }
      }
      const clean = { ...o, name: o.name.trim(), lat: ids[0], lon: ids[1], alt: ids[2] };
      if (editing) actions.updateObject(plot.id, o.id, clean); else actions.addObject(plot.id, clean);
      close();
    } catch (e) {
      useApp.getState().toast({ kind: "error", text: String((e as Error).message) });
    } finally { setBusy(false); }
  };

  // each role: a signal typed by name, from any open file (the main file's first), with its unit
  // and ƒ to change it right here (angles in radians -> degrees)
  const roleRow = (role: Role) => {
    const required = role === "lat" || role === "lon";
    const isPos = role === "lat" || role === "lon" || role === "alt";
    if (isPos && pos.frame !== "lla") return null;
    const value = isPos ? pos[role] : o[role];
    return (
      <div key={role} className="obj-role">
        <span>{t(`objRole_${role}` as TKey)}{required ? " *" : ""}</span>
        <SignalField value={value || null} ariaLabel={t(`objRole_${role}` as TKey)} prefer={mainRun}
          placeholder={required ? t("objChoose") : t("objNone")} noneLabel={required ? undefined : t("objNone")}
          onChange={(id) => (isPos ? setPos((c) => ({ ...c, [role]: id ?? (required ? "" : null) }))
            : setO((c) => ({ ...c, [role]: id ?? (required ? "" : null) })))} />
      </div>
    );
  };
  const setVecAt = (i: number, id: string | null) => setPos((c) => ({ ...c, vec: c.vec.map((x, k) => (k === i ? id ?? "" : x)) }));
  const posRows = pos.frame === "lla" ? null : (
    <>
      <div className="obj-roles">
        {AXES[pos.frame].map((ax, i) => (
          <div key={ax} className="obj-role"><span>{ax} (m) *</span>
            <SignalField value={pos.vec[i] || null} ariaLabel={`${pos.frame.toUpperCase()} ${ax}`} prefer={mainRun}
              placeholder={t("objChoose")} onChange={(id) => setVecAt(i, id)} /></div>
        ))}
      </div>
      {local && <>
        <div className="obj-row">
          <label><span>{t("placeOrigin")}</span>
            <select className="obj-ref" value={pos.refMode} onChange={(e) => setPos({ ...pos, refMode: e.target.value as "signals" | "manual" })}>
              <option value="signals">{t("refSignals")}</option><option value="manual">{t("refManual")}</option>
            </select></label>
        </div>
        <div className="obj-roles">
          {(["objRole_lat", "objRole_lon", "objRole_alt"] as TKey[]).map((k, i) => (pos.refMode === "signals" ? (
            <div key={k} className="obj-role"><span>{t(k)}</span>
              <SignalField value={pos.refSigs[i] || null} ariaLabel={`${t("placeOrigin")} ${t(k)}`} placeholder={t("objChoose")} prefer={mainRun}
                onChange={(id) => setPos((c) => ({ ...c, refSigs: c.refSigs.map((x, j) => (j === i ? id ?? "" : x)) }))} /></div>
          ) : (
            <label key={k} className="obj-role"><span>{t(k)}{i < 2 ? " (°)" : " (m)"}</span>
              <input type="number" step="any" className={`obj-ref-${i}`} aria-label={`${t("placeOrigin")} ${t(k)}`} value={pos.refLla[i]}
                onChange={(e) => setPos((c) => ({ ...c, refLla: c.refLla.map((x, j) => (j === i ? e.target.value : x)) }))} /></label>
          )))}
        </div>
        <p className="hint">{t(pos.refMode === "signals" ? "placeOriginSignalsHint" : "placeOriginManualHint")}</p>
      </>}
    </>
  );

  return (
    <div className="scrim" onMouseDown={close}>
      <div className="dialog obj-dialog" role="dialog" aria-modal="true" aria-label={editing ? t("objEdit") : t("objAdd")} onMouseDown={(e) => e.stopPropagation()}>
        <div className="dialog-head"><h2>{editing ? t("objEdit") : t("objAdd")}</h2></div>
        <div className="dialog-body">
          <div className="obj-kinds" role="radiogroup" aria-label={t("objKind")}>
            {OBJECT_KINDS.map((k) => (
              <button key={k} role="radio" aria-checked={o.kind === k} className={`obj-kind${o.kind === k ? " on" : ""}`} onClick={() => setKind(k)}>
                <img src={iconSvg(k, o.color)} alt="" width={30} height={30} /><span>{t(`obj_${k}` as TKey)}</span>
              </button>
            ))}
          </div>
          <div className="obj-row">
            <label className="obj-name"><span>{t("objName")}</span>
              <input value={o.name} onChange={(e) => setO({ ...o, name: e.target.value })} autoFocus /></label>
            <label className="obj-color"><span>{t("objColor")}</span>
              <input type="color" value={o.color} onChange={(e) => setO({ ...o, color: e.target.value })} /></label>
          </div>
          {data.length > 1 && (
            <label className="obj-main"><span>{t("objFillFrom")}</span>
              <select value={mainRun} onChange={(e) => fillFrom(e.target.value)}>
                {data.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
              </select></label>
          )}
          <div className="obj-row">
            <label><span>{t("objPosFrom")}</span>
              <select className="obj-pos-frame" value={pos.frame} onChange={(e) => setPos({ ...pos, frame: e.target.value as PosFrame })}>
                <option value="lla">{t("objPosLla")}</option><option value="ecef">{t("frameEcef")}</option>
                <option value="ned">{t("frameNed")}</option><option value="enu">{t("frameEnu")}</option>
              </select></label>
            <label title={t("objSmoothHint")}><span>{t("objSmooth")}</span>
              <input type="number" className="obj-smooth" min={0} step="any" value={smoothText} onChange={(e) => setSmoothText(e.target.value)} /></label>
          </div>
          {pos.frame !== "lla" && <p className="hint">{t("objPosFrameHint")}</p>}
          {posRows}
          <div className="obj-row">
            <label><span>{t("objAttitude")}</span>
              <select value={quat ? "quat" : "angles"} onChange={(e) => {
                const q = e.target.value === "quat";
                setQuat(q);
                // only one kind of attitude is kept
                setO((c) => (q ? { ...c, yaw: null, pitch: null, roll: null } : { ...c, qw: null, qx: null, qy: null, qz: null }));
              }}>
                <option value="angles">{t("objAttAngles")}</option><option value="quat">{t("objAttQuat")}</option>
              </select></label>
          </div>
          <div className="obj-roles">{(quat ? [...ROLES.slice(0, 3), ...QUAT_ROLES] : ROLES).map(roleRow)}</div>
          {!o.yaw && !o.qw && <p className="hint">{t("objHeadingFromMotion")}</p>}
          <p className="hint">{t("objAttHint")}</p>
          <div className="obj-row">
            <label><span>{t("objAngleUnit")}</span>
              <select value={o.angleUnit ?? "auto"} onChange={(e) => setO({ ...o, angleUnit: e.target.value as MapObject["angleUnit"] })}>
                <option value="auto">{t("objUnitAuto")}</option><option value="deg">{t("objUnitDeg")}</option><option value="rad">{t("objUnitRad")}</option>
              </select></label>
            {o.alt && <label><span>{t("objAltRef")}</span>
              <select value={o.altRef ?? "msl"} onChange={(e) => setO({ ...o, altRef: e.target.value as MapObject["altRef"] })}>
                <option value="msl">{t("objAltMsl")}</option><option value="home">{t("objAltHome")}</option><option value="agl">{t("objAltAgl")}</option>
              </select></label>}
            <label className="check"><input type="checkbox" checked={o.trail !== false} onChange={(e) => setO({ ...o, trail: e.target.checked })} />{t("objTrail")}</label>
          </div>
          {!posOk && <p className="hint err">{t("objNeedsPosition")}</p>}
          {!smoothOk && <p className="hint err">{t("objSmoothBad")}</p>}
        </div>
        <div className="dialog-foot">
          {editing && <button className="btn danger" onClick={() => { actions.removeObject(plot.id, o.id); close(); }}>{t("remove")}</button>}
          <span className="spacer" />
          <button className="btn" onClick={close}>{t("cancel")}</button>
          <button className="btn primary obj-save" disabled={!ok || busy} onClick={() => void save()}>{editing ? t("save") : t("objAddBtn")}</button>
        </div>
      </div>
    </div>
  );
}
