import type { ReactNode } from "react";
import { actions, type MapObject, type Plot } from "../store";
import { useT, type TKey } from "../i18n";
import { pairOf } from "../relation";
import { RelationToggle } from "./RelationPanel";

/* 1.26: one bar for the map seen in 2D and in 3D (owner, 2026-11-11: "the buttons in 3D and 2D should be the
   same") - the camera (General · On the object · Chase) on the object chosen beside it (the reference by
   default), + / − / fit, the relation box shown or hidden; each view's own extras after them (2D: north /
   track up, back to the object; 3D: look at, a third object, data, events, measure, its own time). The same
   saved fields in both views (followObject, camera), so a switch between 2D and 3D keeps the camera.
   The offline pages (report_assets/relation.js svToolbar) have the same bar. */
export default function MapBar({ plot, objects, onZoom, onFit, className, chaseHint, children }: {
  plot: Plot; objects: MapObject[]; onZoom: (dir: 1 | -1) => void; onFit: () => void; className: string; chaseHint: TKey; children?: ReactNode;
}) {
  const t = useT();
  if (!objects.length) return null;
  const on = plot.followObject && objects.some((o) => o.id === plot.followObject) ? plot.followObject : null;
  const target = on ?? pairOf(plot).primary ?? objects[0].id;
  const mode = !on ? "free" : plot.camera === "chase" ? "chase" : plot.camera === "lookat" ? "lookat" : "centre";
  const set = (m: "free" | "centre" | "chase", id = target) =>
    actions.updatePlot(plot.id, m === "free" ? { followObject: null, camera: undefined } : { followObject: id, camera: m === "chase" ? "chase" : undefined });
  const cam: [string, "free" | "centre" | "chase", TKey, TKey, string][] = [
    ["g3CamFree", "free", "g3CamFree", "g3CamFreeHint", ""], ["g3CamCentre", "centre", "g3CamCentre", "g3CamCentreHint", ""],
    ["g3CamChase", "chase", "g3CamChase", chaseHint, "g3-cam-chase"]];
  return (
    <div className={`map-bar ${className}`} role="toolbar" aria-label={t("g3Bar")} onMouseDown={(e) => e.stopPropagation()} onDoubleClick={(e) => e.stopPropagation()}>
      <span className="g3-seg" role="radiogroup" aria-label={t("g3Camera")}>
        <span className="g3-seg-label">{t("g3Camera")}</span>
        {cam.map(([k, m, label, hint, cls]) => (
          <button key={k} role="radio" aria-checked={mode === m} className={`${cls}${mode === m ? " on" : ""}`.trim()} title={t(hint)} onClick={() => set(m)}>{t(label)}</button>
        ))}
      </span>
      <select className="geo-follow" value={target} title={t("objFollow")} aria-label={t("objFollow")}
        onChange={(e) => set(mode === "free" ? "centre" : mode === "chase" ? "chase" : "centre", e.target.value)}>
        {objects.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
      </select>
      <span className="map-zoom">
        <button className="geo-zoom-in" onClick={() => onZoom(1)} title={`${t("mapZoomIn")} (+)`} aria-label={t("mapZoomIn")}>+</button>
        <button className="geo-zoom-out" onClick={() => onZoom(-1)} title={`${t("mapZoomOut")} (−)`} aria-label={t("mapZoomOut")}>−</button>
        <button className="geo-fit" onClick={onFit} title={`${t("mapFitAll")} (0)`} aria-label={t("mapFitAll")}>
          <svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true"><path d="M2 6V2h4M10 2h4v4M14 10v4h-4M6 14H2v-4" /></svg></button>
      </span>
      <RelationToggle plot={plot} objects={objects} />
      {children}
    </div>
  );
}
