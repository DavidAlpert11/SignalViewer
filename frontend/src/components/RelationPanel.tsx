import { useState } from "react";
import { actions, useApp, type MapObject, type Plot } from "../store";
import { fmtNum, useT, type TKey } from "../i18n";
import { altAt, angleUnitOf, fmtDistance, objectAt, trackTime, type ObjTrack } from "../mapObjects";
import { compareObjects, errorSignals, overlayObjects, pairOf, plotRelation, relation, type At, type CompareFrame } from "../relation";

/* N7: the relation between the primary and the secondary object at the cursor (Tacview-like) - a small
   box on the map that renders on its own as the time moves (the map does not), with the over-time
   actions: plot the relation, error signals, compare in a frame. */
export default function RelationPanel({ plot, objects, tracks }: { plot: Plot; objects: MapObject[]; tracks: Record<string, ObjTrack> }) {
  const t = useT();
  const lang = useApp((s) => s.lang);
  const cursor = useApp((s) => s.cursor);
  const streaming = useApp((s) => s.streaming);
  const [frame, setFrame] = useState<CompareFrame>("ned");
  const [busy, setBusy] = useState(false);
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
  const run = async (f: () => Promise<unknown>) => { setBusy(true); try { await f(); } finally { setBusy(false); } };
  const row = (k: TKey, v: string) => <div className="rel-row"><span>{t(k)}</span><bdi dir="ltr">{v}</bdi></div>;
  return (
    <div className="rel-panel" role="region" aria-label={t("relPanel")} onMouseDown={(e) => e.stopPropagation()} onDoubleClick={(e) => e.stopPropagation()}>
      <button className="rel-head linklike" aria-expanded={!folded} onClick={() => actions.updatePlot(plot.id, { relFolded: !folded || undefined })}>
        {folded ? "▸" : "▾"} <b style={{ color: S.color }}>{S.name}</b> → <b style={{ color: P.color }}>{P.name}</b>
      </button>
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
      {!folded && (
        <div className="rel-actions">
          <button className="btn sm rel-plot" disabled={busy} onClick={() => void run(() => plotRelation(P, S, objects))}>{t("relPlot")}</button>
          <button className="btn sm rel-errors" disabled={busy} onClick={() => void run(() => errorSignals(P, S, objects))}>{t("relErrors")}</button>
          <span className="rel-compare">
            <select value={frame} aria-label={t("relCompare")} title={t(`relFrameHint_${frame}` as TKey)} onChange={(e) => setFrame(e.target.value as CompareFrame)}>
              {(["ned", "enu", "ecef", "lla", "track"] as const).map((f) => <option key={f} value={f} title={t(`relFrameHint_${f}` as TKey)}>{f.toUpperCase()}</option>)}
            </select>
            <button className="btn sm rel-compare-btn" disabled={busy} title={t("relDiffsHint")} onClick={() => void run(() => compareObjects(P, objects, frame))}>{t("relDiffs")}</button>
            <button className="btn sm rel-overlay-btn" disabled={busy || frame === "track"} title={t("relOverlayHint")}
              onClick={() => { if (frame !== "track") void run(() => overlayObjects(P, objects, frame)); }}>{t("relOverlay")}</button>
          </span>
          <select className="rel-lines" value={plot.relLines ?? "pair"} aria-label={t("relLines")} title={t("relLines")}
            onChange={(e) => actions.updatePlot(plot.id, { relLines: e.target.value === "pair" ? undefined : e.target.value as "all" | "off" })}>
            <option value="pair">{t("relLinesPair")}</option><option value="all">{t("relLinesAll")}</option><option value="off">{t("relLinesOff")}</option>
          </select>
        </div>
      )}
    </div>
  );
}
