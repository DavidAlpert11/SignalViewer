import { useEffect, useMemo, useState } from "react";
import { actions, nextColor, uid, useApp, type MapObject, type ObjectKind } from "../store";
import { useT, type TKey } from "../i18n";
import { iconSvg, OBJECT_KINDS } from "./mapIcons";
import { guessRoles, hasOwnAttitude, QUAT_ROLES, ROLES, trackOfClass, type Role } from "../mapObjects";
import { useEscape } from "./Overlays";
import SignalField from "./SignalField";
import { AXES, createFrameGroup, createSmoothGroup, frameGroupName } from "../frames";
import { api, type SignalInfo } from "../api";
import { detectAll, detectObjects, VEC_ROLES, type Candidate } from "../objectDetect";
import { addable, candidateObject, isAdded, linkAttitudes, NAMING_EXAMPLE, objectColors, objectSources, whyLines } from "../objectAdd";
import { copyText } from "../errorReport";

/* Q101 / Q102: the position may come in ECEF, NED or ENU (m) instead of latitude / longitude, and
   may be smoothed over a window in seconds. Both are derived signals ("frame" position -> LLA, then
   "vecsmooth"), made when the object is saved; the object points at their lat / lon / alt, so
   sessions, live mode and the rest of the app need nothing new. Editing reads the chain back. */
type PosFrame = "lla" | "ecef" | "ned" | "enu";
interface PosSetup { frame: PosFrame; vec: string[]; refMode: "signals" | "manual"; refSigs: string[]; refLla: string[];
  lat: string; lon: string; alt: string | null; smooth: number }

/** How an object's lat / lon / alt were made (L4: the one chain walk, objectSources). */
function readSetup(o: MapObject, derived: SignalInfo[]): PosSetup {
  const ch = objectSources(o, derived);
  const out: PosSetup = { frame: "lla", vec: ["", "", ""], refMode: "signals", refSigs: ["", "", ""], refLla: ["", "", ""],
    lat: ch.lat, lon: ch.lon, alt: ch.alt, smooth: ch.smooth };
  if (ch.frame) {
    const p = ch.frame.params;
    out.frame = ch.frame.src as PosFrame;
    out.vec = ch.frame.sources.slice(0, 3);
    if (p.ref === "manual") { out.refMode = "manual"; out.refLla = [p.ref_lat, p.ref_lon, p.ref_alt].map((v) => String(v ?? "")); }
    else out.refSigs = ch.frame.sources.slice(3, 6).concat(["", "", ""]).slice(0, 3);
  }
  return out;
}
const setupKey = (p: PosSetup) => JSON.stringify(p.frame === "lla" ? [p.frame, p.lat, p.lon, p.alt, p.smooth]
  : [p.frame, p.vec, p.frame === "ecef" ? null : p.refMode === "manual" ? p.refLla.map(Number) : p.refSigs, p.smooth]);

/* Adding / editing a map object: what it is (aircraft, ship...), its colour, and which signals give
   its position and attitude - each from any open file. Picking a file fills in the signals by their
   names (GPS.Lat / Lng / Alt together, angles from the attitude group). */

export default function ObjectDialog() {
  const req = useApp((s) => s.objectDialog);
  const runs = useApp((s) => s.runs);
  const ws = useApp((s) => s.ws);
  // N5: adding starts from the objects found in the open files; "Advanced…" (or by hand) is the form below
  const [form, setForm] = useState<{ preset: Candidate | null } | null>(null);
  useEffect(() => setForm(null), [req]);
  const plot = useMemo(() => ws.tabs.flatMap((tb) => tb.plots).find((p) => p.id === req?.plotId), [ws, req]);
  const cands = useMemo(() => detectAll(runs.filter((r) => r.format !== "derived")), [runs]);
  if (!req || !plot) return null;
  const derived = runs.find((r) => r.format === "derived")?.signals ?? [];
  const fresh = cands.filter((c) => !isAdded(c, plot, derived));
  if (req.objectId || form || (!fresh.length && !req.why && !cands.length)) {
    return <ObjectForm key={form?.preset?.key ?? "form"} preset={form?.preset ?? null} onBack={form && cands.length ? () => setForm(null) : undefined} />;
  }
  return <FoundObjects plotId={plot.id} cands={cands} why={!!req.why} onForm={(preset) => setForm({ preset })} />;
}

/** N5: "Objects found in this recording" - one row per candidate of every open file, Add all / Add
 *  selected (one Undo), *Why?* in plain words, the naming convention, Advanced… for the full form. */
function FoundObjects({ plotId, cands, why, onForm }: { plotId: string; cands: Candidate[]; why: boolean; onForm: (c: Candidate | null) => void }) {
  const t = useT();
  const lang = useApp((s) => s.lang);
  const ws = useApp((s) => s.ws);
  const runs = useApp((s) => s.runs);
  const plot = ws.tabs.flatMap((tb) => tb.plots).find((p) => p.id === plotId);
  const derived = runs.find((r) => r.format === "derived")?.signals ?? [];
  const added0 = (c: Candidate) => isAdded(c, plot, derived);
  const close = () => useApp.setState({ objectDialog: null });
  useEscape(close, true);
  const [colors] = useState(() => { const next = objectColors(plot); return new Map(cands.map((c) => [c.key, next()])); });
  const [names, setNames] = useState<Record<string, string>>({});
  const [color, setColor] = useState<Record<string, string>>({});
  const [checked, setChecked] = useState<Record<string, boolean>>(() => Object.fromEntries(cands.map((c) => [c.key, addable(c) && !added0(c)])));
  const [open, setOpen] = useState<Record<string, boolean>>(() => (why ? Object.fromEntries(cands.map((c) => [c.key, true])) : {}));
  const [busy, setBusy] = useState(false);
  // N5 (owner's decision 3): a row with no angles - "motion" (default) or the key of the row to borrow from
  const [attFrom, setAttFrom] = useState<Record<string, string>>({});
  const withAtt = cands.filter((c) => c.attitude !== "none");     // truth first: the list is sorted so
  const fileName = (c: Candidate) => runs.find((r) => r.id === c.runId)?.name ?? "";
  const many = new Set(cands.map((c) => c.runId)).size > 1;
  const can = cands.filter((c) => addable(c) && !added0(c));
  const sel = can.filter((c) => checked[c.key]);
  const add = async (list: Candidate[]) => {
    if (!list.length || busy) return;
    setBusy(true);
    try {
      const pairs = [];
      for (const c of list) {
        const o = await candidateObject(c, color[c.key] ?? colors.get(c.key)!, (names[c.key] ?? c.name).trim() || c.name);
        pairs.push({ c, o, from: c.attitude === "none" && attFrom[c.key] && attFrom[c.key] !== "motion" ? attFrom[c.key] : undefined });
      }
      actions.addObjects(plotId, linkAttitudes(pairs, cands, plot, derived));   // one commit: one Undo
      close();
    } catch (e) {
      useApp.getState().toast({ kind: "error", text: String((e as Error).message) });
    } finally { setBusy(false); }
  };
  // L5: a position in metres says its frame and where it is placed: "NED · origin ORGN[0]", "ECEF", "NED · needs an origin"
  const frameLabel = (c: Candidate) => {
    const frame = c.pos.toUpperCase();
    if (c.badUnit) return t("objRowBadUnit", { frame, unit: c.badUnit });
    if (c.pos === "ecef") return frame;
    return c.origin ? t("objRowOrigin", { frame, via: c.origin.via }) : t("objRowNeedsOrigin", { frame });
  };
  const chip = (id: string) => <span key={id} className="obj-chip-sig" title={id.slice(id.indexOf("/") + 1)}>{id.slice(id.indexOf("/") + 1)}</span>;
  return (
    <div className="scrim" onMouseDown={close}>
      <div className="dialog obj-found" role="dialog" aria-modal="true" aria-label={t("objFoundTitle")} onMouseDown={(e) => e.stopPropagation()}>
        <div className="dialog-head"><h2>{t("objFoundTitle")}</h2></div>
        <div className="dialog-body">
          {!cands.length && <p className="hint">{t("objFoundNone")}</p>}
          {cands.length > 0 && (
            <ul className="obj-found-list">
              {cands.map((c) => {
                const added = added0(c);
                const col = color[c.key] ?? colors.get(c.key)!;
                return (
                  <li key={c.key} className={`obj-found-row${added ? " added" : ""}`} data-key={c.key}>
                    <div className="obj-found-main">
                      <input type="checkbox" className="obj-found-check" aria-label={names[c.key] ?? c.name}
                        checked={!added && !!checked[c.key]} disabled={added || !addable(c)}
                        onChange={(e) => setChecked({ ...checked, [c.key]: e.target.checked })} />
                      <img src={iconSvg("aircraft", col)} alt="" width={22} height={22} />
                      <input className="obj-found-name" value={names[c.key] ?? c.name} disabled={added} aria-label={t("objName")}
                        onChange={(e) => setNames({ ...names, [c.key]: e.target.value })} />
                      <span className={`obj-cls cls-${c.cls}`}>{t(`objCls_${c.cls}` as TKey)}</span>
                      <input type="color" value={col} disabled={added} aria-label={t("objColor")} onChange={(e) => setColor({ ...color, [c.key]: e.target.value })} />
                      {many && <span className="obj-found-file" title={fileName(c)}>{fileName(c)}</span>}
                      <span className="spacer" />
                      {added ? <span className="obj-found-added">✓ {t("objAdded")}</span>
                        : c.pos !== "lla" ? <span className={`obj-found-frame${addable(c) ? "" : " obj-found-origin"}`}>{frameLabel(c)}</span> : null}
                      <button className="linklike obj-why" aria-expanded={!!open[c.key]} onClick={() => setOpen({ ...open, [c.key]: !open[c.key] })}>{t("objWhy")}</button>
                      {!added && <button className="linklike obj-adv" onClick={() => onForm(c)}>{t("objAdvanced")}</button>}
                    </div>
                    {!added && c.attitude === "none" && withAtt.length > 0 && (
                      <label className="obj-found-att" title={t("objAttSourceHint")}><span>{t("objAttSource")}</span>
                        <select value={attFrom[c.key] ?? "motion"} aria-label={`${t("objAttSource")}: ${names[c.key] ?? c.name}`}
                          onChange={(e) => setAttFrom({ ...attFrom, [c.key]: e.target.value })}>
                          <option value="motion">{t("objAttMotion")}</option>
                          {withAtt.map((x) => <option key={x.key} value={x.key}>{t("objAttFrom", { name: names[x.key] ?? x.name })}</option>)}
                        </select></label>
                    )}
                    <div className="obj-found-sigs">{[...(c.pos === "lla" ? (["lat", "lon", "alt"] as const) : VEC_ROLES), "roll", "pitch", "yaw", "qw", "qx", "qy", "qz"]
                      .map((r) => c.picks[r as keyof Candidate["picks"]]?.id).filter((x): x is string => !!x).map(chip)}</div>
                    {open[c.key] && <ul className="obj-why-lines">{whyLines(c, lang, attFrom[c.key] && attFrom[c.key] !== "motion" ? names[attFrom[c.key]] ?? cands.find((x) => x.key === attFrom[c.key])?.name : undefined).map((l, i) => <li key={i}>{l}</li>)}</ul>}
                  </li>
                );
              })}
            </ul>
          )}
          <div className="obj-naming">
            <b>{t("objNamingTitle")}</b>
            <p>{t("objNamingText")}</p>
            <pre dir="ltr">{NAMING_EXAMPLE}</pre>
            <div className="obj-naming-links">
              <button className="linklike" onClick={() => void copyText(NAMING_EXAMPLE)}>{t("objNamingCopy")}</button>
              <button className="linklike" onClick={() => useApp.setState({ guideOpen: true })}>{t("objNamingMore")}</button>
            </div>
          </div>
        </div>
        <div className="dialog-foot">
          <button className="btn obj-byhand" onClick={() => onForm(null)}>{t("objByHand")}</button>
          <span className="spacer" />
          <button className="btn" onClick={close}>{t("cancel")}</button>
          {can.length >= 2 && <button className="btn obj-add-sel" disabled={!sel.length || busy} onClick={() => void add(sel)}>{t("objAddSelected")}</button>}
          {can.length >= 1 && <button className="btn primary obj-add-all" disabled={busy || (can.length === 1 && !sel.length)}
            onClick={() => void add(can.length >= 2 ? can : sel)}>{can.length >= 2 ? t("objAddAll", { n: can.length }) : t("objAddOne")}</button>}
        </div>
      </div>
    </div>
  );
}

function ObjectForm({ preset, onBack }: { preset: Candidate | null; onBack?: () => void }) {
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
    // N5: from a found object (Advanced…), else the old guess from the first file
    const g: Partial<Record<Role, string>> = preset
      ? Object.fromEntries(Object.entries(preset.picks).filter(([r]) => !VEC_ROLES.includes(r as never)).map(([r, p]) => [r, p!.id]))
      : run ? guessRoles(run) : {};
    const n = (plot?.objects?.length ?? 0) + 1;
    return { id: uid("o"), name: preset?.name ?? `${t("obj_aircraft")} ${n}`, kind: "aircraft", color: nextColor(ws), lat: g.lat ?? "", lon: g.lon ?? "",
      alt: g.alt ?? null, yaw: g.yaw ?? null, pitch: g.pitch ?? null, roll: g.roll ?? null,
      qw: g.qw ?? null, qx: g.qx ?? null, qy: g.qy ?? null, qz: g.qz ?? null, angleUnit: "auto", trail: true,
      ...(preset ? { cls: preset.cls, ...(trackOfClass(preset.cls) ? { track: trackOfClass(preset.cls) } : {}) } : {}) };
  });
  // 26.A5: what "Automatic" takes the angles to be, and why - shown in the choice, so it can be checked
  const [guess, setGuess] = useState<{ unit: "deg" | "rad"; why: string } | null>(null);
  useEffect(() => {
    if (!o.yaw && !o.pitch && !o.roll) { setGuess(null); return; }
    let gone = false;
    api.angleUnits({ yaw: o.yaw, pitch: o.pitch, roll: o.roll }).then((r) => {
      const all = Object.values(r.units);
      if (!gone) setGuess(all[0] ?? null);          // one rule for all the angles (or each by its name)
    }).catch(() => { if (!gone) setGuess(null); });
    return () => { gone = true; };
  }, [o.yaw, o.pitch, o.roll]);
  const runOf = (sig?: string | null) => (sig ? sig.slice(0, sig.indexOf("/")) : "");
  const [mainRun, setMainRun] = useState(preset?.runId || runOf(o.lat) || data[0]?.id || "");
  // the attitude: three angles, or a quaternion (four signals - e.g. a PX4 log has only that)
  const [quat, setQuat] = useState(!!o.qw);
  const derivedSigs = runs.find((r) => r.format === "derived")?.signals ?? [];
  const [orig] = useState<PosSetup | null>(() => (editing ? readSetup(editing, derivedSigs) : null));
  const [pos, setPos] = useState<PosSetup>(() => {
    if (orig) return { ...orig };
    if (preset && preset.pos !== "lla") {
      // L5: the found origin, else a suggestion - the same file's position in lat / lon / alt (a receiver
      // first: its first fix is the closest thing to an origin), else typed in by hand
      const v = VEC_ROLES.map((r) => preset.picks[r]?.id ?? "");
      const refSigs = preset.origin?.ids ?? suggestedOrigin(preset)?.ids;
      return { frame: preset.pos, vec: v, refMode: refSigs ? "signals" : "manual", refSigs: refSigs ? [...refSigs] : ["", "", ""], refLla: ["", "", ""], lat: "", lon: "", alt: null, smooth: 0 };
    }
    const g = data[0] && !preset ? guessRoles(data[0]) : {};
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
      const clean: MapObject = { ...o, name: o.name.trim(), lat: ids[0], lon: ids[1], alt: ids[2] };
      // N5: an object with angles of its own has no other source; a new one without them is drawn by its motion
      if (hasOwnAttitude(clean)) { delete clean.attitudeSource; delete clean.minSpeed; }
      else if (!editing && !clean.attitudeSource) clean.attitudeSource = "motion";
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
        {preset && pos.refMode === "signals" && (() => {
          // L5: say where the origin came from while it is still the one we filled in
          const sug = preset.origin ? null : suggestedOrigin(preset);
          const same = (ids?: string[]) => !!ids && ids.every((x, i) => x === pos.refSigs[i]);
          return preset.origin && same(preset.origin.ids) ? <p className="hint obj-origin-why">{t("objOriginFound", { via: preset.origin.via })}</p>
            : sug && same(sug.ids) ? <p className="hint obj-origin-why">{t("objOriginSuggested", { name: sug.name })}</p> : null;
        })()}
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
          {!hasOwnAttitude(o) && (() => {
            // N5 (owner's decision 3): no angles of its own - from its motion, or another object's (the primary / truth first)
            const src = o.attitudeSource;
            const val = src && typeof src === "object" ? src.object : "motion";
            const others = (plot.objects ?? []).filter((x) => x.id !== o.id && hasOwnAttitude(x))
              .sort((a, b) => Number(b.id === plot.primaryObject) - Number(a.id === plot.primaryObject) || Number(b.cls === "truth") - Number(a.cls === "truth"));
            return (
              <div className="obj-row obj-attsrc">
                <label title={t("objAttSourceHint")}><span>{t("objAttSource")}</span>
                  <select className="obj-att-source" value={others.some((x) => x.id === val) ? val : "motion"}
                    onChange={(e) => setO({ ...o, attitudeSource: e.target.value === "motion" ? "motion" : { object: e.target.value } })}>
                    <option value="motion">{t("objAttMotion")}</option>
                    {others.map((x) => <option key={x.id} value={x.id}>{t("objAttFrom", { name: x.name })}</option>)}
                  </select></label>
                {val === "motion" && <label title={t("objMinSpeedHint")}><span>{t("objMinSpeed")}</span>
                  <input type="number" className="obj-min-speed" min={0} step="any" value={o.minSpeed ?? 1}
                    onChange={(e) => { const v = Number(e.target.value); setO({ ...o, minSpeed: Number.isFinite(v) && v >= 0 ? v : 1 }); }} /></label>}
              </div>
            );
          })()}
          <p className="hint">{t("objAttHint")}</p>
          <div className="obj-row">
            <label><span>{t("objAngleUnit")}</span>
              <select value={o.angleUnit ?? "auto"} onChange={(e) => setO({ ...o, angleUnit: e.target.value as MapObject["angleUnit"] })}>
                <option value="auto">{guess && !quat ? `${t("objUnitAuto")} - ${t(guess.unit === "deg" ? "objUnitDeg" : "objUnitRad")} (${t(("objUnitWhy_" + guess.why) as TKey)})` : t("objUnitAuto")}</option><option value="deg">{t("objUnitDeg")}</option><option value="rad">{t("objUnitRad")}</option>
              </select></label>
            {o.alt && <label><span>{t("objAltRef")}</span>
              <select value={o.altRef ?? "msl"} onChange={(e) => setO({ ...o, altRef: e.target.value as MapObject["altRef"] })}>
                <option value="msl">{t("objAltMsl")}</option><option value="home">{t("objAltHome")}</option><option value="agl">{t("objAltAgl")}</option>
              </select></label>}
            <label className="check"><input type="checkbox" checked={o.trail !== false} onChange={(e) => setO({ ...o, trail: e.target.checked })} />{t("objTrail")}</label>
            {o.trail !== false && <label><span>{t("objTrackLook")}</span>
              <select className="obj-track-look" value={o.track ?? "line"} onChange={(e) => setO({ ...o, track: e.target.value === "line" ? undefined : e.target.value as MapObject["track"] })}>
                {(["line", "dash", "points"] as const).map((k) => <option key={k} value={k}>{t(`objTrack_${k}` as TKey)}</option>)}
              </select></label>}
          </div>
          {o.trail !== false && (
            <div className="obj-row obj-trackcolor">
              <label><span>{t("objTrackColor")}</span>
                <select value={o.trackColor ?? "object"} aria-label={t("objTrackColor")} onChange={(e) => {
                  const m = e.target.value as NonNullable<MapObject["trackColor"]>;
                  // a sensible first signal: the flight mode for "state", the altitude for "value"
                  const guess = m === "state" ? runs.find((r) => r.id === mainRun)?.signals.find((x) => x.labels && /mode/i.test(x.name) && !/num|rsn|reason/i.test(x.name))?.id
                    ?? runs.find((r) => r.id === mainRun)?.signals.find((x) => x.labels)?.id
                    : m === "value" ? o.alt ?? undefined : undefined;
                  setO({ ...o, trackColor: m === "object" ? undefined : m, colorSig: m === "object" ? null : (o.trackColor === m ? o.colorSig : guess ?? o.colorSig ?? null) });
                }}>
                  <option value="object">{t("objTrackOwn")}</option>
                  <option value="state">{t("objTrackState")}</option>
                  <option value="value">{t("objTrackValue")}</option>
                </select></label>
              {o.trackColor && o.trackColor !== "object" && (
                <div className="obj-role"><span>{t("objTrackBy")}</span>
                  <SignalField value={o.colorSig ?? null} ariaLabel={t("objTrackBy")} prefer={mainRun} placeholder={t("objChoose")}
                    onChange={(id) => setO({ ...o, colorSig: id })} /></div>
              )}
            </div>
          )}
          {!posOk && <p className="hint err">{t("objNeedsPosition")}</p>}
          {!smoothOk && <p className="hint err">{t("objSmoothBad")}</p>}
        </div>
        <div className="dialog-foot">
          {editing && <button className="btn danger" onClick={() => { actions.removeObject(plot.id, o.id); close(); }}>{t("remove")}</button>}
          {onBack && <button className="btn obj-back" onClick={onBack}>{t("objFoundTitle")}</button>}
          <span className="spacer" />
          <button className="btn" onClick={close}>{t("cancel")}</button>
          <button className="btn primary obj-save" disabled={!ok || busy} onClick={() => void save()}>{editing ? t("save") : t("objAddBtn")}</button>
        </div>
      </div>
    </div>
  );
}

/** L5: an origin to suggest for a local position that has none: a latitude / longitude / altitude object of
 *  the same file - a receiver first (its first fix), else any. Its first valid sample becomes the origin. */
function suggestedOrigin(c: Candidate): { ids: [string, string, string]; name: string } | undefined {
  const run = useApp.getState().runs.find((r) => r.id === c.runId);
  if (!run) return undefined;
  const lla = detectObjects(run).candidates.filter((x) => x.pos === "lla" && x.picks.lat && x.picks.lon && x.picks.alt);
  const s = lla.find((x) => x.cls === "receiver") ?? lla[0];
  return s ? { ids: [s.picks.lat!.id, s.picks.lon!.id, s.picks.alt!.id], name: s.name } : undefined;
}
