import { actions, useApp, type MapObject, type Plot } from "../store";
import { fmtNum, useT, type TKey } from "../i18n";
import { altAt, angleUnitOf, fmtDistance, objectAt, trackTime, type ObjTrack } from "../mapObjects";
import { errorAlong, pairOf, relation, type At } from "../relation";
import { findPlace, shownPlaces } from "../places";

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
  // P7: the compared list ends with the places (distance and bearing from the reference to a fixed point)
  const places = shownPlaces();
  const rp = plot.relPlace && places.some((p) => p.id === plot.relPlace) ? plot.relPlace : null;
  if ((objects.length < 2 && !places.length) || !primary) return null;
  return (
    <span className="rel-pick" role="group" aria-label={t("relPick")}>
      <label className="rel-ref" title={t("relRingTip_primary")}>
        <RingIcon kind="primary" /><span>{t("relPrimary")}</span>
        <select value={primary} aria-label={t("relPrimary")}
          onChange={(e) => { const x = e.target.value; actions.setObjectPair(plot.id, x, x === secondary ? primary : secondary); }}>
          {objects.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
        </select>
      </label>
      <button className="iconbtn sm rel-swap" disabled={!secondary || !!rp} title={`${t("relSwap")} (X)`} aria-label={t("relSwap")}
        onClick={() => { if (secondary) actions.setObjectPair(plot.id, secondary, primary); }}>⇄</button>
      <label className="rel-cmp" title={t("relRingTip_secondary")}>
        <RingIcon kind="secondary" /><span>{t("relSecondary")}</span>
        <select value={rp ? `place:${rp}` : secondary ?? ""} aria-label={t("relSecondary")} onChange={(e) => {
          const v = e.target.value;
          if (v.startsWith("place:")) actions.updatePlot(plot.id, { relPlace: v.slice(6) });
          else { if (plot.relPlace) actions.updatePlot(plot.id, { relPlace: undefined }); actions.setObjectPair(plot.id, primary, v); }
        }}>
          {!secondary && !rp && <option value="">—</option>}
          {objects.filter((o) => o.id !== primary).map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
          {places.length > 0 && <optgroup label={t("plRelGroup")}>
            {places.map((p) => <option key={p.id} value={`place:${p.id}`}>{p.name}</option>)}</optgroup>}
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
  const place = findPlace(plot.relPlace);
  const P = objects.find((o) => o.id === primary);
  // P7: compared with a place - a fixed point (its own height when it has one)
  const S: MapObject | undefined = place && !place.hidden && place.kind !== "view"
    ? { id: `place:${place.id}`, name: place.name, kind: "vehicle", color: place.color ?? "#d29922", lat: "", lon: "" } : objects.find((o) => o.id === secondary);
  if (!P || (!S && !shownPlaces().length)) return null;      // one object and places: the box offers the places
  const folded = !!plot.relFolded;
  if (plot.relHidden) return null;
  const at = (o: MapObject, dt = 0): At | null => {
    if (place && o.id === `place:${place.id}`) return { lat: place.lat, lon: place.lon, alt: place.alt ?? null, hdg: null };
    const tr = tracks[o.id];
    if (!tr) return null;
    const tt = trackTime(tr, cursor.on ? cursor.t1 : null, streaming) + dt;
    const st = objectAt(tr, tt, angleUnitOf(o, objects));
    return st ? { lat: st.lat, lon: st.lon, alt: o.alt ? altAt(tr, tt) : null, hdg: st.heading } : null;
  };
  // P6: a hidden one of the pair keeps its place: its side says so, and no relation is worked out
  const off = !!(P.hidden || S?.hidden);
  const p0 = off ? null : at(P), s0 = off || !S ? null : at(S), p1 = off ? null : at(P, 0.5), s1 = off || !S ? null : at(S, 0.5);
  const r = p0 && s0 ? relation(p0, s0, p1 ?? undefined, s1 ?? undefined, p1 && s1 ? 0.5 : 0) : null;
  const deg = (v: number | null) => (v === null ? "—" : `${fmtNum(v, lang, 4)}°`);
  const row = (k: TKey, v: string) => <div className="rel-row"><span>{t(k)}</span><bdi dir="ltr">{v}</bdi></div>;
  return (
    <div className="rel-panel" role="region" aria-label={t("relPanel")} onMouseDown={(e) => e.stopPropagation()} onDoubleClick={(e) => e.stopPropagation()}>
      <div className="rel-head">
        <button className="iconbtn sm rel-fold" aria-expanded={!folded} aria-label={t(folded ? "relUnfold" : "relFold")} title={t(folded ? "relUnfold" : "relFold")}
          onClick={() => actions.updatePlot(plot.id, { relFolded: !folded || undefined })}>{folded ? "▸" : "▾"}</button>
        <RelationPicker plot={plot} objects={objects} />
        {off && <span className="rel-off">{P.hidden ? `${P.name}: ${t("relObjHidden")}` : `${S?.name}: ${t("relObjHidden")}`}</span>}
        <button className="iconbtn sm rel-hide" aria-label={t("relHide")} title={t("relHide")} onClick={() => actions.updatePlot(plot.id, { relHidden: true })}>×</button>
      </div>
      {!folded && r && (
        <div className="rel-body">
          {row("relRange", fmtDistance(r.slant ?? r.horiz, lang))}
          {r.slant !== null && row("relHoriz", fmtDistance(r.horiz, lang))}
          {r.dalt !== null && row("relDalt", `${r.dalt >= 0 ? "+" : ""}${fmtDistance(r.dalt, lang)}`)}
          {row("relBearing", deg(r.bearing))}
          {r.relBearing !== null && row("relRelBearing", deg(r.relBearing))}
          {r.closure !== null && row("relClosure", `${fmtNum(r.closure, lang, 4)} m/s`)}
          {r.tca !== null && (
            // 1.26: a click goes to the closest moment (the cursor there, every plot and the map follow)
            <button className="rel-row rel-tca" title={t("relTcaGo")} onClick={() => {
              const c = useApp.getState().cursor, base = trackTime(tracks[P.id], c.on ? c.t1 : null, streaming);
              useApp.setState({ cursor: { ...c, on: true, t1: base + r.tca!, active: 1 } });
            }}><span>{t("relTca")}</span><bdi dir="ltr">{fmtNum(r.tca, lang, 4)} s</bdi></button>
          )}
          {r.hdgDiff !== null && row("relHdgDiff", deg(r.hdgDiff))}
          {r.aspect !== null && row("relAspect", `${deg(r.aspect)}${r.aspectSide ? ` ${r.aspectSide}` : ""}`)}
        </div>
      )}
      {/* P9: the pair is one vehicle - the error surface between their tracks (3D; the flat drawing colours the
          compared track), its toggle and scale */}
      {!folded && (() => {
        const tp = tracks[P.id], tq = S && !place ? tracks[S.id] : undefined;
        const alt = (tr: ObjTrack & { alt?: ArrayLike<number> | null }) => (i: number) => (tr.alt ? tr.alt[i] : NaN);
        const e = tp && tq ? errorAlong(tp, alt(tp), tq, alt(tq)) : null;
        if (!e?.same) return null;
        return (
          <label className="rel-err" title={t("errSurfaceHint")}>
            <input type="checkbox" checked={plot.errorSurface !== false} onChange={(ev) => actions.updatePlot(plot.id, { errorSurface: ev.target.checked ? undefined : false })} />
            {t("errSurface")} <bdi dir="ltr">0</bdi><i className="ramp" aria-hidden="true" /><bdi dir="ltr">{fmtDistance(e.p95, lang)}</bdi> <small>({t("errScale")})</small>
          </label>
        );
      })()}
      {/* L8: one Compare… (the dialog holds the old four actions as presets); shown folded too - the box is the place */}
      <div className="rel-actions">
        <button className="btn sm rel-compare-open" onClick={() => useApp.setState({ compareDialog: { plotId: plot.id } })} title={t("cmpOpenHint")}>{t("cmpOpen")}</button>
        {!folded && (
          <select className="rel-lines" value={plot.relLines ?? "pair"} aria-label={t("relLines")} title={t("relLines")}
            onChange={(e) => actions.updatePlot(plot.id, { relLines: e.target.value === "pair" ? undefined : e.target.value as "all" | "off" })}>
            {/* it stands beside Compare… and read as "Compare… the pair": each choice says what it is about */}
            <option value="pair">{t("relLinesShort")}: {t("relLinesPair")}</option><option value="all">{t("relLinesShort")}: {t("relLinesAll")}</option><option value="off">{t("relLinesShort")}: {t("relLinesOff")}</option>
          </select>
        )}
      </div>
    </div>
  );
}

/** 1.26: the relation box shown / hidden - the same button in the 2D map's and the 3D view's bars. */
export function RelationToggle({ plot, objects }: { plot: Plot; objects: MapObject[] }) {
  const t = useT();
  if (objects.length < 2 && !(objects.length && shownPlaces().length)) return null;
  const on = !plot.relHidden;
  return <button className={`rel-toggle${on ? " on" : ""}`} aria-pressed={on} title={t("relToggleHint")}
    onClick={() => actions.updatePlot(plot.id, { relHidden: on || undefined })}>{t("relPanel")}</button>;
}
