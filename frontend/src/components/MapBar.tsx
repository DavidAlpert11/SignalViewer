import { useEffect, useRef, type ReactNode } from "react";
import { actions, type MapObject, type Plot } from "../store";
import { useT, type TKey } from "../i18n";
import { pairOf } from "../relation";
import { RelationToggle } from "./RelationPanel";
import { mapCamera } from "../mapObjects";
import MapStory from "./MapStory";

/* M6: a small picture of what each camera does - drawn in the text colour, no hard-coded colours */
function CamIcon({ m }: { m: string }) {
  const d: Record<string, string> = {
    free: "M8 2v12M2 8h12M8 2l-2 2M8 2l2 2M8 14l-2-2M8 14l2-2M2 8l2-2M2 8l2 2M14 8l-2-2M14 8l-2 2",
    top: "M8 1v5M6 4l2 2 2-2M3 10h10l-2 4H5z",
    centre: "M8 8m-1.6 0a1.6 1.6 0 1 0 3.2 0a1.6 1.6 0 1 0 -3.2 0M2.5 8a5.5 5.5 0 0 1 11 0M13.5 8l-1.5-1.2M13.5 8l1-1.6",
    chase: "M8 3l3 4H5zM8 7v5M5 14h6",
    cockpit: "M2 9h12M5 9l-2 4M11 9l2 4M6 6a2 2 0 0 1 4 0",
  };
  return <svg className="cam-ico" viewBox="0 0 16 16" width="13" height="13" fill="none" stroke="currentColor" strokeWidth="1.4"
    strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={d[m]} /></svg>;
}

/* 1.26: one bar for the map seen in 2D and in 3D (owner, 2026-11-11: "the buttons in 3D and 2D should be the
   same") - the camera (General · On the object · Chase) on the object chosen beside it (the reference by
   default), + / − / fit, the relation box shown or hidden; each view's own extras after them (2D: north /
   track up, back to the object; 3D: look at, a third object, data, events, measure, its own time). The same
   saved fields in both views (followObject, camera), so a switch between 2D and 3D keeps the camera.
   The offline pages (report_assets/relation.js svToolbar) have the same bar. */
export default function MapBar({ plot, objects, onZoom, onFit, className, chaseHint, freeLook, children }: {
  plot: Plot; objects: MapObject[]; onZoom: (dir: 1 | -1) => void; onFit: () => void; className: string; chaseHint: TKey;
  /** 3D: the Cockpit's Look freely toggle - right after the cameras, while the Cockpit is chosen */
  freeLook?: ReactNode; children?: ReactNode;
}) {
  const t = useT();
  // the data box sits under the bar, however many rows the bar takes (Hebrew, a narrow plot: three) - it
  // was at a fixed 84 px and covered the bar's last row
  const barRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = barRef.current, host = el?.offsetParent as HTMLElement | null;
    if (!el || !host) return;
    const put = () => host.style.setProperty("--mapbar-bottom", `${el.offsetTop + el.offsetHeight}px`);
    put();
    const ro = new ResizeObserver(put);
    ro.observe(el);
    return () => ro.disconnect();
  }, [objects.length]);
  if (!objects.length) return null;
  const on = plot.followObject && objects.some((o) => o.id === plot.followObject) ? plot.followObject : null;
  const target = on ?? pairOf(plot).primary ?? objects[0].id;
  // P4: General · From above · On the object · Chase (From above keeps a chosen object in the middle)
  const cm = mapCamera({ ...plot, followObject: on });
  const mode = cm === "lookat" ? "centre" : cm;
  type Cam = "free" | "top" | "centre" | "chase" | "cockpit";
  // M6: each camera one job - From above never follows (an old session's From above on an object keeps it)
  const set = (m: Cam, id = target) =>
    actions.updatePlot(plot.id, m === "free" ? { followObject: null, camera: "free" } : m === "top" ? { followObject: null, camera: "top" }
      : { followObject: id, camera: m === "chase" ? "chase" : m === "cockpit" ? "cockpit" : undefined });
  // P9: Cockpit - from the object, looking where it points, rolling with it: 3D only (M6; flat it was Behind it again)
  const flat = className === "geo-bar";
  const cam: [string, Cam, TKey, TKey, string][] = ([
    ["g3CamFree", "free", "g3CamFree", "g3CamFreeHint", "g3-cam-free"], ["g3CamTop", "top", "g3CamTop", "g3CamTopHint", "g3-cam-top"],
    ["g3CamCentre", "centre", "g3CamCentre", "g3CamCentreHint", "g3-cam-centre"], ["g3CamChase", "chase", "g3CamChase", chaseHint, "g3-cam-chase"],
    ["g3CamCockpit", "cockpit", "g3CamCockpit", "g3CamCockpitHint", "g3-cam-cockpit"]] as [string, Cam, TKey, TKey, string][])
    .filter(([, m]) => !(flat && m === "cockpit"));
  const follows = mode !== "free" && mode !== "top";
  return (
    <div ref={barRef} className={`map-bar ${className}`} role="toolbar" aria-label={t("g3Bar")} onMouseDown={(e) => e.stopPropagation()} onDoubleClick={(e) => e.stopPropagation()}>
      <span className="g3-seg" role="radiogroup" aria-label={t("g3Camera")}>
        <span className="g3-seg-label">{t("g3Camera")}</span>
        {cam.map(([k, m, label, hint, cls]) => (
          <button key={k} role="radio" aria-checked={mode === m} className={`${cls}${mode === m ? " on" : ""}`.trim()} title={t(hint)} onClick={() => set(m)}>
            <CamIcon m={m} />{t(label)}</button>
        ))}
      </span>
      {mode === "cockpit" && freeLook}
      {follows && <select className="geo-follow" value={target} title={t("objFollow")} aria-label={t("objFollow")}
        onChange={(e) => set(mode === "chase" || mode === "cockpit" ? mode : "centre", e.target.value)}>
        {objects.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
      </select>}
      <span className="map-zoom">
        <button className="geo-zoom-in" onClick={() => onZoom(1)} title={`${t("mapZoomIn")} (+)`} aria-label={t("mapZoomIn")}>+</button>
        <button className="geo-zoom-out" onClick={() => onZoom(-1)} title={`${t("mapZoomOut")} (−)`} aria-label={t("mapZoomOut")}>−</button>
        <button className="geo-fit" onClick={onFit} title={`${t("mapFitAll")} (0)`} aria-label={t("mapFitAll")}>
          <svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true"><path d="M2 6V2h4M10 2h4v4M14 10v4h-4M6 14H2v-4" /></svg></button>
      </span>
      {/* F5: the height profile under the map, of the primary object */}
      <button className={`g3-toggle map-profile${plot.showProfile ? " on" : ""}`} aria-pressed={!!plot.showProfile} title={t("hpToggleHint")}
        onClick={() => actions.updatePlot(plot.id, { showProfile: !plot.showProfile })}>{t("hpToggle")}</button>
      <RelationToggle plot={plot} objects={objects} />
      <MapStory plot={plot} objects={objects} />
      {children}
    </div>
  );
}
