import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useApp } from "../store";
import { useT, type TKey } from "../i18n";
import { effectiveBase, isOnlineBase, isPhotoBase, type GeoBase } from "../mapBase";
import { removeMyMap, tileAt, useMyMaps } from "../mapLayers";
import KeepAreaDialog, { type AreaOf } from "./KeepAreaDialog";
import MyMapDialog from "./MyMapDialog";

/* M1: the map's background, chosen in one place - a button in the map's top-end corner (2D and 3D) opening a
   picker: a thumbnail of each layer at the place on screen (the offline map drawn here; an online layer only from
   what is on the disk - opening the picker downloads nothing), ☁ on the online ones, the reason when "Never use
   the network" is on, the Borders switch, My maps (M4) and Keep this area offline… (M3). The choice is the app's
   (remembered, and kept with a session, as before). */

const BUILT_IN: GeoBase[] = ["auto", "osm", "esri", "light", "dark", "satellite", "satroads", "topo"];

export default function MapLayers({ where, areaOf }: {
  /** the place on screen and its zoom (for the thumbnails); null when unknown */
  where: () => { lat: number; lon: number; z: number } | null;
  areaOf: AreaOf;
}) {
  const t = useT();
  const chosen = useApp((s) => s.geoBase);
  const netOff = useApp((s) => s.offlineOnly || s.offlineForced);
  const forced = useApp((s) => s.offlineForced);
  const dark = useApp((s) => s.theme) === "dark";
  const borders = useApp((s) => s.geoBorders);
  const mine = useMyMaps();
  const [open, setOpen] = useState(false);
  const [dialog, setDialog] = useState<"keep" | "add" | null>(null);
  const rootRef = useRef<HTMLDivElement>(null);
  const shown = effectiveBase(chosen, netOff);
  const sel = chosen === "offline" ? "auto" : chosen;

  useEffect(() => {
    if (!open) return;
    const away = (e: MouseEvent) => { if (!rootRef.current?.contains(e.target as Node)) setOpen(false); };
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") { e.stopPropagation(); setOpen(false); } };
    document.addEventListener("mousedown", away);
    document.addEventListener("keydown", esc, true);
    return () => { document.removeEventListener("mousedown", away); document.removeEventListener("keydown", esc, true); };
  }, [open]);

  const at = open ? where() : null;
  const [z, x, y] = at ? tileAt(at.lat, at.lon, Math.max(2, Math.min(13, Math.round(at.z) - 1))) : [2, 2, 1];
  const thumb = (b: string) => b === "auto" ? `/api/tiles/${dark ? "offline_topo_dark" : "offline_topo"}/${z}/${x}/${y}`
    : `/api/tiles/${encodeURIComponent(b)}/${z}/${x}/${y}?cached=1`;
  // (the store's own type of geoBase is narrower until L3 widens it to GeoBase - TASKS.md, a request from L4)
  type StoreBase = ReturnType<typeof useApp.getState>["geoBase"];
  const choose = (b: GeoBase) => { useApp.setState({ geoBase: b as StoreBase }); };

  const card = (b: GeoBase, label: string, extra?: { title?: string; problem?: string; remove?: () => void }) => {
    const online = isOnlineBase(b);
    const off = (online && netOff) || !!extra?.problem;
    return (
      <div key={b} className={`ml-card${sel === b ? " on" : ""}${off ? " off" : ""}`} data-base={b}>
        <button className="ml-pick" role="radio" aria-checked={sel === b} disabled={off}
          title={extra?.problem || (online && netOff ? t("geoLayerHintOff") : extra?.title ?? label)} onClick={() => choose(b)}>
          <span className="ml-thumb"><img src={thumb(b)} alt="" loading="lazy" onError={(e) => { (e.target as HTMLImageElement).style.visibility = "hidden"; }} /></span>
          <span className="ml-name">{online && <span className="ml-cloud" aria-label={t("mlOnline")}>☁ </span>}{label}</span>
        </button>
        {extra?.remove && <button className="iconbtn sm ml-remove" aria-label={t("mlRemove")} title={t("mlRemove")} onClick={extra.remove}>×</button>}
      </div>
    );
  };

  return (
    <div ref={rootRef} className="map-layers" onMouseDown={(e) => e.stopPropagation()} onDoubleClick={(e) => e.stopPropagation()}>
      <button className={`map-layers-btn${open ? " on" : ""}`} aria-expanded={open} aria-haspopup="dialog" title={t("mlTitle")}
        onClick={() => setOpen(!open)}>
        <svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
          <path d="M8 2 1.5 5.5 8 9l6.5-3.5L8 2ZM1.5 8.5 8 12l6.5-3.5M1.5 11 8 14.5l6.5-3.5" /></svg>
        <span>{t("mlButton")}</span>
        {isOnlineBase(shown) && <span className="ml-cloud" role="status" title={t("netOnlineHint")}>☁</span>}
      </button>
      {open && (
        <div className="map-layers-pop" role="dialog" aria-label={t("mlTitle")}>
          <div className="ml-head">
            <b>{t("mlTitle")}</b>
            <span className={`ml-net ${netOff ? "warn" : "ok"}`}>{t(netOff ? (forced ? "mlNetForced" : "mlNetOff") : "mlNetOk")}</span>
          </div>
          <div className="ml-grid" role="radiogroup" aria-label={t("mlTitle")}>
            {BUILT_IN.map((b) => card(b, t(`ml_${b}` as TKey)))}
            {mine.map((m) => card(m.src as GeoBase, m.name, {
              title: m.kind === "mbtiles" ? m.path : m.url, problem: m.ok ? "" : m.problem,
              remove: () => { if (sel === m.src) choose("auto"); void removeMyMap(m.src); } }))}
          </div>
          {(shown === "offline" || isPhotoBase(shown)) && (
            <label className="acheck ml-borders" title={t("geoBordersHint")}>
              <input type="checkbox" checked={borders} onChange={(e) => useApp.setState({ geoBorders: e.target.checked })} />{t("geoBorders")}</label>
          )}
          <p className="ml-note">{t(netOff ? "mlOffNote" : "mlOnlineNote")}</p>
          <div className="ml-actions">
            <button className="btn sm" onClick={() => { setOpen(false); setDialog("keep"); }}>{t("mlKeep")}</button>
            <button className="btn sm ghost" onClick={() => { setOpen(false); setDialog("add"); }}>{t("mlAdd")}</button>
          </div>
        </div>
      )}
      {dialog === "keep" && createPortal(<KeepAreaDialog areaOf={areaOf} base={shown} onClose={() => setDialog(null)} />, document.body)}
      {dialog === "add" && createPortal(<MyMapDialog onClose={() => setDialog(null)} onAdded={(src) => choose(src as GeoBase)} />, document.body)}
    </div>
  );
}
