import { actions, useApp, type MapObject, type Plot } from "../store";
import { fmtNum, useT, type TKey } from "../i18n";
import { altAt, angleUnitOf, fmtDistance, objectAt, trackTime, type ObjTrack } from "../mapObjects";
import { pairOf, relation, type At } from "../relation";

/** L7: the two rings, as drawn on the map: solid around the reference, dashed around the object compared with it. */
export function RingIcon({ kind }: { kind: "primary" | "secondary" }) {
  return (
    <svg className={`ring-icon ${kind}`} viewBox="0 0 16 16" width="14" height="14" aria-hidden="true">
      <circle cx="8" cy="8" r="5.5" fill="none" stroke="var(--amber)" strokeWidth="2" strokeDasharray={kind === "secondary" ? "3 2.2" : undefined} />
    </svg>
  );
}

/** L7: the one place to choose the pair - Reference ⇄ Compared with - shared by the map's relation box
 *  and the 3D view's bar (it replaced the 3D view's own Primary / Second selects). Each choice is one Undo. */
export function RelationPicker({ plot, objects }: { plot: Plot; objects: MapObject[] }) {
  const t = useT();
  const { primary, secondary } = pairOf(plot);
  if (objects.length < 2 || !primary) return null;
  return (
    <span className="rel-pick" role="group" aria-label={t("relPick")}>
      <label className="rel-ref" title={t("relRingTip_primary")}>
        <RingIcon kind="primary" /><span>{t("relPrimary")}</span>
        <select value={primary} aria-label={t("relPrimary")}
          onChange={(e) => { const x = e.target.value; actions.setObjectPair(plot.id, x, x === secondary ? primary : secondary); }}>
          {objects.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
        </select>
      </label>
      <button className="iconbtn sm rel-swap" disabled={!secondary} title={`${t("relSwap")} (X)`} aria-label={t("relSwap")}
        onClick={() => { if (secondary) actions.setObjectPair(plot.id, secondary, primary); }}>⇄</button>
      <label className="rel-cmp" title={t("relRingTip_secondary")}>
        <RingIcon kind="secondary" /><span>{t("relSecondary")}</span>
        <select value={secondary ?? ""} aria-label={t("relSecondary")} onChange={(e) => actions.setObjectPair(plot.id, primary, e.target.value)}>
          {objects.filter((o) => o.id !== primary).map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
        </select>
      </label>
    </span>
  );
}

/* N7: the relation between the reference and the compared object at the cursor (Tacview-like) - a small
   box on the map that renders on its own as the time moves (the map does not), with the over-time
   actions: plot the relation, error signals, compare in a frame. L7: its header says which ring is which
   and chooses the pair. */
export default function RelationPanel({ plot, objects, tracks }: { plot: Plot; objects: MapObject[]; tracks: Record<string, ObjTrack> }) {
  const t = useT();
  const lang = useApp((s) => s.lang);
  const cursor = useApp((s) => s.cursor);
  const streaming = useApp((s) => s.streaming);
  const { primary, secondary } = pairOf(plot);
  const P = objects.find((o) => o.id === primary), S = objects.find((o) => o.id === secondary);
  if (!P || !S) return null;
  const folded = !!plot.relFolded;
  const at = (o: MapObject, dt = 0): At | null => {
    const tr = tracks[o.id];
    if (!tr) return null;
    const tt = trackTime(tr, cursor.on ? cursor.t1 : null, streaming) + dt;
    const st = objectAt(tr, tt, angleUnitOf(o, objects));
    return st ? { lat: st.lat, lon: st.lon, alt: o.alt ? altAt(tr, tt) : null, hdg: st.heading } : null;
  };
  const p0 = at(P), s0 = at(S), p1 = at(P, 0.5), s1 = at(S, 0.5);
  const r = p0 && s0 ? relation(p0, s0, p1 ?? undefined, s1 ?? undefined, p1 && s1 ? 0.5 : 0) : null;
  const deg = (v: number | null) => (v === null ? "—" : `${fmtNum(v, lang, 4)}°`);
  const row = (k: TKey, v: string) => <div className="rel-row"><span>{t(k)}</span><bdi dir="ltr">{v}</bdi></div>;
  return (
    <div className="rel-panel" role="region" aria-label={t("relPanel")} onMouseDown={(e) => e.stopPropagation()} onDoubleClick={(e) => e.stopPropagation()}>
      <div className="rel-head">
        <button className="iconbtn sm rel-fold" aria-expanded={!folded} aria-label={t(folded ? "relUnfold" : "relFold")} title={t(folded ? "relUnfold" : "relFold")}
          onClick={() => actions.updatePlot(plot.id, { relFolded: !folded || undefined })}>{folded ? "▸" : "▾"}</button>
        <RelationPicker plot={plot} objects={objects} />
      </div>
      {!folded && r && (
        <div className="rel-body">
          {row("relRange", fmtDistance(r.slant ?? r.horiz, lang))}
          {r.slant !== null && row("relHoriz", fmtDistance(r.horiz, lang))}
          {r.dalt !== null && row("relDalt", `${r.dalt >= 0 ? "+" : ""}${fmtDistance(r.dalt, lang)}`)}
          {row("relBearing", deg(r.bearing))}
          {r.relBearing !== null && row("relRelBearing", deg(r.relBearing))}
          {r.closure !== null && row("relClosure", `${fmtNum(r.closure, lang, 4)} m/s`)}
          {r.tca !== null && row("relTca", `${fmtNum(r.tca, lang, 4)} s`)}
          {r.hdgDiff !== null && row("relHdgDiff", deg(r.hdgDiff))}
          {r.aspect !== null && row("relAspect", `${deg(r.aspect)}${r.aspectSide ? ` ${r.aspectSide}` : ""}`)}
        </div>
      )}
      {/* L8: one Compare… (the dialog holds the old four actions as presets); shown folded too - the box is the place */}
      <div className="rel-actions">
        <button className="btn sm rel-compare-open" onClick={() => useApp.setState({ compareDialog: { plotId: plot.id } })} title={t("cmpOpenHint")}>{t("cmpOpen")}</button>
        {!folded && (
          <select className="rel-lines" value={plot.relLines ?? "pair"} aria-label={t("relLines")} title={t("relLines")}
            onChange={(e) => actions.updatePlot(plot.id, { relLines: e.target.value === "pair" ? undefined : e.target.value as "all" | "off" })}>
            <option value="pair">{t("relLinesPair")}</option><option value="all">{t("relLinesAll")}</option><option value="off">{t("relLinesOff")}</option>
          </select>
        )}
      </div>
    </div>
  );
}
