import { useMemo, useState } from "react";
import { actions, nextColor, uid, useApp, type MapObject, type ObjectKind } from "../store";
import { useT, type TKey } from "../i18n";
import { iconSvg, OBJECT_KINDS } from "./mapIcons";
import { guessRoles, QUAT_ROLES, ROLES, type Role } from "../mapObjects";
import { useEscape } from "./Overlays";
import SignalField from "./SignalField";

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
  if (!req || !plot) return null;

  const fillFrom = (rid: string) => {
    setMainRun(rid);
    const run = data.find((r) => r.id === rid);
    if (!run) return;
    const g = guessRoles(run);
    setO((c) => ({ ...c, lat: g.lat ?? "", lon: g.lon ?? "", alt: g.alt ?? null, yaw: g.yaw ?? null, pitch: g.pitch ?? null, roll: g.roll ?? null,
      qw: g.qw ?? null, qx: g.qx ?? null, qy: g.qy ?? null, qz: g.qz ?? null }));
    setQuat(!!g.qw);
  };
  const setKind = (k: ObjectKind) => setO((c) => {
    // a default name follows the kind ("Aircraft 1" -> "Ship 1"); a name the user typed stays
    const def = OBJECT_KINDS.some((kk) => c.name.startsWith(t(`obj_${kk}` as TKey)));
    return { ...c, kind: k, name: def ? c.name.replace(/^\S+(\s.*)?$/, `${t(`obj_${k}` as TKey)}$1`) : c.name };
  });
  const ok = !!o.lat && !!o.lon && !!o.name.trim();
  const save = () => {
    if (!ok) return;
    const clean = { ...o, name: o.name.trim() };
    if (editing) actions.updateObject(plot.id, o.id, clean); else actions.addObject(plot.id, clean);
    close();
  };

  // each role: a signal typed by name, from any open file (the main file's first), with its unit
  // and ƒ to change it right here (angles in radians -> degrees)
  const roleRow = (role: Role) => {
    const required = role === "lat" || role === "lon";
    return (
      <div key={role} className="obj-role">
        <span>{t(`objRole_${role}` as TKey)}{required ? " *" : ""}</span>
        <SignalField value={o[role] || null} ariaLabel={t(`objRole_${role}` as TKey)} prefer={mainRun}
          placeholder={required ? t("objChoose") : t("objNone")} noneLabel={required ? undefined : t("objNone")}
          onChange={(id) => setO((c) => ({ ...c, [role]: id ?? (required ? "" : null) }))} />
      </div>
    );
  };

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
          {!ok && <p className="hint err">{t("objNeedsPosition")}</p>}
        </div>
        <div className="dialog-foot">
          {editing && <button className="btn danger" onClick={() => { actions.removeObject(plot.id, o.id); close(); }}>{t("remove")}</button>}
          <span className="spacer" />
          <button className="btn" onClick={close}>{t("cancel")}</button>
          <button className="btn primary" disabled={!ok} onClick={save}>{editing ? t("save") : t("objAddBtn")}</button>
        </div>
      </div>
    </div>
  );
}
