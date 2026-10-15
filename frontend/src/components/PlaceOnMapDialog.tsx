import { useState } from "react";
import { createFrameGroup, frameGroupName } from "../frames";
import { actions, activeTab, signalName, uid, useApp, type MapObject, type ObjectKind } from "../store";
import { useT, type TKey } from "../i18n";
import { guessRoles } from "../mapObjects";
import { OBJECT_KINDS } from "./mapIcons";
import { useEscape } from "./Overlays";

/* T17c: put an XYZ plot's tracks on a map or the 3D globe - only when they are a place: metres in
   NED or ENU from an origin on Earth. Each track becomes three derived signals (the "frame"
   operation, position, to LLA - so they update with their files and are kept in sessions) and a
   map object on them. The origin is the first valid sample of a lat / lon / alt (usually the
   vehicle's GPS, guessed from the track's file) or numbers typed in. */

type Target = "new-geo" | "new-3d" | string;

export default function PlaceOnMapDialog() {
  const t = useT();
  const plotId = useApp((s) => s.placeDialog);
  const ws = useApp((s) => s.ws);
  const runs = useApp((s) => s.runs);
  const close = () => useApp.setState({ placeDialog: null });
  useEscape(close, !!plotId);
  const tab = activeTab(ws);
  const plot = tab.plots.find((p) => p.id === plotId);
  const signals = plot?.signals;
  const trios = (() => {
    const s = signals ?? [];
    const out: { sigs: string[]; color: string; name: string }[] = [];
    for (let k = 0; k + 2 < s.length; k += 3) {
      out.push({ sigs: [s[k].sig, s[k + 1].sig, s[k + 2].sig], color: s[k].color,
        name: [s[k], s[k + 1], s[k + 2]].map((x) => signalName(runs, x.sig, false)).join(" / ") });
    }
    return out;
  })();
  const maps = tab.plots.map((p, i) => ({ p, i })).filter(({ p }) => p.mode === "geo" || p.mode === "3d");
  const data = runs.filter((r) => r.format !== "derived");
  const firstRun = data.find((r) => trios[0]?.sigs[0].startsWith(r.id + "/")) ?? data[0];
  const g = firstRun ? guessRoles(firstRun) : {};

  const [frame, setFrame] = useState<"ned" | "enu">("ned");
  const [origin, setOrigin] = useState<"signals" | "manual">(g.lat && g.lon && g.alt ? "signals" : "manual");
  const [ref, setRef] = useState<string[]>([g.lat ?? "", g.lon ?? "", g.alt ?? ""]);
  const [manual, setManual] = useState<string[]>(["", "", ""]);
  const [target, setTarget] = useState<Target>(maps[0]?.p.id ?? "new-geo");
  const [kind, setKind] = useState<ObjectKind>("uav");
  const [busy, setBusy] = useState(false);
  if (!plotId || !plot) return null;

  const allSigs = data.flatMap((r) => r.signals.map((s) => ({ id: `${r.id}/${s.name}`, label: data.length > 1 ? `${r.name} · ${s.name}` : s.name })));
  const ok = trios.length > 0 && (origin === "signals" ? ref.every((x) => !!x)
    : manual.every((x) => x.trim() !== "" && Number.isFinite(Number(x))) && Math.abs(Number(manual[0])) <= 90);
  const roles: TKey[] = ["objRole_lat", "objRole_lon", "objRole_alt"];

  const apply = async () => {
    if (!ok) return;
    setBusy(true);
    try {
      const objs: MapObject[] = [];
      for (const tr of trios) {
        const refParams = origin === "signals" ? { ref: "signals" }
          : { ref: "manual", ref_lat: Number(manual[0]), ref_lon: Number(manual[1]), ref_alt: Number(manual[2]) };
        const sources = [...tr.sigs, ...(origin === "signals" ? ref : [])];
        // one nested group per track: lla_Pos_ned.lat / .lon / .alt (frames.ts)
        const ids = await createFrameGroup(sources, { qty: "position", src: frame, dst: "lla", ...refParams,
          alignment: plot.xyAlign ?? "linear" }, frameGroupName(frame, "lla", "position"));
        objs.push({ id: uid("o"), name: tr.name, kind, color: tr.color, lat: ids[0], lon: ids[1], alt: ids[2],
          altRef: "msl", angleUnit: "auto", trail: true });
      }
      if (target === "new-geo" || target === "new-3d") {
        if (!actions.addObjectsToNewPlot(target === "new-geo" ? "geo" : "3d", objs)) return;
      } else {
        for (const o of objs) actions.addObject(target, o);
      }
      useApp.getState().toast({ kind: "info", text: t("placeDone", { n: objs.length }) });
      close();
    } catch (e) {
      useApp.getState().toast({ kind: "error", text: String((e as Error).message) });
    } finally { setBusy(false); }
  };

  return (
    <div className="scrim" onMouseDown={close}>
      <div className="dialog obj-dialog" role="dialog" aria-modal="true" aria-label={t("placeTitle")} onMouseDown={(e) => e.stopPropagation()}>
        <div className="dialog-head"><h2>{t("placeTitle")}</h2></div>
        <div className="dialog-body">
          <p className="hint">{t("placeIntro")}</p>
          <div className="obj-row">
            <label><span>{t("placeFrame")}</span>
              <select value={frame} onChange={(e) => setFrame(e.target.value as "ned" | "enu")}>
                <option value="ned">{t("frameNed")}</option><option value="enu">{t("frameEnu")}</option>
              </select></label>
          </div>
          <div className="obj-row">
            <label><span>{t("placeOrigin")}</span>
              <select value={origin} onChange={(e) => setOrigin(e.target.value as "signals" | "manual")}>
                <option value="signals">{t("refSignals")}</option><option value="manual">{t("refManual")}</option>
              </select></label>
          </div>
          <div className="obj-roles">
            {roles.map((k, i) => (origin === "signals" ? (
              <label key={k} className="obj-role"><span>{t(k)}</span>
                <select value={ref[i]} aria-label={t(k)} onChange={(e) => setRef(ref.map((x, j) => (j === i ? e.target.value : x)))}>
                  <option value="">{t("objChoose")}</option>
                  {allSigs.map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}
                </select></label>
            ) : (
              <label key={k} className="obj-role"><span>{t(k)}{i < 2 ? " (°)" : " (m)"}</span>
                <input type="number" step="any" aria-label={t(k)} value={manual[i]} onChange={(e) => setManual(manual.map((x, j) => (j === i ? e.target.value : x)))} /></label>
            )))}
          </div>
          <p className="hint">{t(origin === "signals" ? "placeOriginSignalsHint" : "placeOriginManualHint")}</p>
          <div className="obj-row">
            <label><span>{t("placeTarget")}</span>
              <select value={target} onChange={(e) => setTarget(e.target.value)}>
                {maps.map(({ p, i }) => <option key={p.id} value={p.id}>{p.title || t("plotTitle", { n: i + 1 })} ({t(p.mode === "3d" ? "mode3d" : "modeGeo")})</option>)}
                <option value="new-geo">{t("placeNewMap")}</option>
                <option value="new-3d">{t("placeNew3d")}</option>
              </select></label>
            <label><span>{t("objKind")}</span>
              <select value={kind} onChange={(e) => setKind(e.target.value as ObjectKind)}>
                {OBJECT_KINDS.map((k) => <option key={k} value={k}>{t(`obj_${k}` as TKey)}</option>)}
              </select></label>
          </div>
          <p className="hint">{t("placeTracks", { n: trios.length })}</p>
        </div>
        <div className="dialog-foot">
          <span className="spacer" />
          <button className="btn" onClick={close}>{t("cancel")}</button>
          <button className="btn primary" disabled={!ok || busy} onClick={apply}>{busy ? t("loading") : t("placeApply")}</button>
        </div>
      </div>
    </div>
  );
}
