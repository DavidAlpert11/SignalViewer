import { useEffect, useRef, type ReactNode } from "react";
import { actions, type MapObject, type Plot } from "../store";
import { useT, type TKey } from "../i18n";
import { pairOf } from "../relation";
import { RelationToggle } from "./RelationPanel";
import MapStory from "./MapStory";

/* M6: a small picture of what each camera does - drawn in the text colour, no hard-coded colours */
function CamIcon({ m }: { m: "free" | "object" }) {
  const d = m === "free" ? "M8 2v12M2 8h12M8 2l-2 2M8 2l2 2M8 14l-2-2M8 14l2-2M2 8l2-2M2 8l2 2M14 8l-2-2M14 8l-2 2"
    : "M8 8m-1.6 0a1.6 1.6 0 1 0 3.2 0a1.6 1.6 0 1 0 -3.2 0M2.5 8a5.5 5.5 0 0 1 11 0M13.5 8l-1.5-1.2M13.5 8l1-1.6";
  return <svg className="cam-ico" viewBox="0 0 16 16" width="13" height="13" fill="none" stroke="currentColor" strokeWidth="1.4"
    strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={d} /></svg>;
}

/* 1.26: one bar for the map seen in 2D and in 3D (owner, 2026-11-11: "the buttons in 3D and 2D should be the
   same") - the camera (Free · On the object) on the object chosen beside it (the reference by default),
   + / − / fit, the relation box shown or hidden; each view's own extras after them (2D: north / track up,
   back to the object; 3D: a third object, data, events, measure, its own time). The same
   saved fields in both views (followObject, camera), so a switch between 2D and 3D keeps the camera.
   The offline pages (report_assets/relation.js svToolbar) have the same bar. */
export default function MapBar({ plot, objects, onZoom, onFit, className, objectHint, children }: {
  plot: Plot; objects: MapObject[]; onZoom: (dir: 1 | -1) => void; onFit: () => void; className: string; objectHint: TKey; children?: ReactNode;
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
  // two cameras (owner, 2026-11-16): Free, or On the object - turn around it, nearer / further down to it
  const mode = on ? "object" : "free";
  const set = (m: "free" | "object", id = target) => actions.setMapCamera(plot.id, m === "free" ? null : id);
  const cam: ["free" | "object", TKey, TKey][] = [["free", "g3CamFree", "g3CamFreeHint"], ["object", "g3CamObject", objectHint]];
  return (
    <div ref={barRef} className={`map-bar ${className}`} role="toolbar" aria-label={t("g3Bar")} onMouseDown={(e) => e.stopPropagation()} onDoubleClick={(e) => e.stopPropagation()}>
      <span className="g3-seg" role="radiogroup" aria-label={t("g3Camera")}>
        <span className="g3-seg-label">{t("g3Camera")}</span>
        {cam.map(([m, label, hint]) => (
          <button key={m} role="radio" aria-checked={mode === m} className={`g3-cam-${m}${mode === m ? " on" : ""}`} title={t(hint)} onClick={() => set(m)}>
            <CamIcon m={m} />{t(label)}</button>
        ))}
      </span>
      {on && <select className="geo-follow" value={target} title={t("objFollow")} aria-label={t("objFollow")}
        onChange={(e) => set("object", e.target.value)}>
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
