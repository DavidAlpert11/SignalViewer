import { useEffect, useMemo, useRef, useState } from "react";
import { actions, pickPath, useApp, type Place } from "../store";
import { translate, useT, type TKey } from "../i18n";
import { api } from "../api";
import { allPlaces, parsePlace, placeIconSvg, type ListedPlace } from "../places";
import { mapCameraNow, mapFly } from "../globeBridge";
import { prompt } from "./Overlays";
import { fmtCoord } from "../mapDefaults";

/* P7: the one place for the list of places (CLAUDE.md: one place per control) - docked in the Map, opened by
   the Map's ⋯ → Places…: a search box (that also takes a position and flies there), the two lists with an eye
   each, click = fly there, edit, delete, move between the lists, Save this view, import / export. */
export default function PlacesPanel({ plotId }: { plotId: string }) {
  const t = useT();
  const lang = useApp((s) => s.lang);
  useApp((s) => s.ws.places);                 // re-render when either list changes
  useApp((s) => s.myPlaces);
  const [q, setQ] = useState("");
  const [goto, setGoto] = useState<{ lat: number; lon: number } | null>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  useEffect(() => { searchRef.current?.focus(); }, []);
  useEffect(() => {
    const h = window.setTimeout(() => { void parsePlace(q).then(setGoto); }, 200);
    return () => window.clearTimeout(h);
  }, [q]);
  const list = allPlaces();
  const shown = useMemo(() => {
    const k = q.trim().toLowerCase();
    return k && !goto ? list.filter((p) => p.name.toLowerCase().includes(k) || (p.note ?? "").toLowerCase().includes(k)) : list;
  }, [list, q, goto]);
  const close = () => useApp.setState({ placesPanel: null });
  const fly = (p: Place) => {
    if (p.kind === "view" && p.view) mapFly.get(plotId)?.({ lat: p.lat, lon: p.lon, alt: p.alt, heading: p.view.heading, pitch: p.view.pitch, range: p.view.range });
    else if (p.points?.length) {
      // a line / area: its middle, far enough to see it whole
      const la = p.points.map((x) => x[0]), lo = p.points.map((x) => x[1]);
      const c = { lat: (Math.min(...la) + Math.max(...la)) / 2, lon: (Math.min(...lo) + Math.max(...lo)) / 2 };
      const span = Math.max((Math.max(...la) - Math.min(...la)) * 111_000, (Math.max(...lo) - Math.min(...lo)) * 111_000 * Math.cos((c.lat * Math.PI) / 180));
      mapFly.get(plotId)?.({ ...c, range: Math.max(1500, span * 2.2) });
    } else mapFly.get(plotId)?.({ lat: p.lat, lon: p.lon, alt: p.alt });
  };
  const saveView = async () => {
    const cam = mapCameraNow.get(plotId)?.();
    if (!cam) return;
    const n = list.filter((p) => p.kind === "view").length + 1;
    const name = await prompt(t("plSaveView"), t("plSaveViewName"), t("plViewDefault", { n }));
    if (name === null) return;
    actions.addPlace({ kind: "view", name: name.trim() || t("plViewDefault", { n }), lat: cam.lat, lon: cam.lon, alt: cam.alt,
      view: { heading: cam.heading ?? 0, pitch: cam.pitch ?? -35, range: cam.range ?? 0 } });
  };
  const importFile = async () => {
    const path = await pickPath({ mode: "open", title: t("plImport"), exts: [".kml", ".kmz", ".geojson", ".json", ".csv"] });
    if (!path) return;
    try {
      const r = await api.importPlaces(path);
      actions.addPlaces(r.places, "session");
      const parts = [translate(lang, "plImported", { n: r.places.length })];
      if (r.skipped) parts.push(translate(lang, "plSkipped", { n: r.skipped }));
      useApp.getState().toast({ kind: "info", text: parts.join(" · ") });
    } catch (e) { useApp.getState().toast({ kind: "error", text: String((e as Error).message) }); }
  };
  const exportFile = async () => {
    const path = await pickPath({ mode: "save", title: t("plExport"), exts: [".kml"], defaultName: "places.kml" });
    if (!path) return;
    try {
      const r = await api.exportPlaces(path, list.map(({ mine: _m, ...p }) => p), t("plPanel"));
      useApp.getState().toast({ kind: "info", text: translate(lang, "plExportDone", { n: r.places, path: r.path }) });
    } catch (e) { useApp.getState().toast({ kind: "error", text: String((e as Error).message) }); }
  };
  const row = (p: ListedPlace) => (
    <li key={p.id} className={`pl-row${p.hidden ? " hidden" : ""}`}>
      {p.kind !== "view" && <button className={`iconbtn sm obj-eye${p.hidden ? "" : " on"}`} aria-pressed={!p.hidden}
        title={t(p.hidden ? "plShow" : "plHide")} aria-label={`${t(p.hidden ? "plShow" : "plHide")}: ${p.name}`}
        onClick={() => actions.togglePlaceHidden(p.id)}>{p.hidden ? "◌" : "◉"}</button>}
      <button className="pl-go" title={t("plFly")} onClick={() => fly(p)}>
        {p.kind === "point" ? <img src={placeIconSvg(p.icon, p.color, 16)} alt="" width={16} height={16} />
          : <span className={`pl-kind ${p.kind}`} style={{ color: p.color }} aria-hidden="true">{p.kind === "view" ? "⌖" : p.kind === "area" ? "▱" : "〰"}</span>}
        <span className="pl-name">{p.name}</span>
        {p.kind !== "point" && <small>{t(`plKind_${p.kind}` as TKey)}</small>}
      </button>
      <button className="iconbtn sm" title={t(p.mine ? "plToSession" : "plToMine")} aria-label={`${t(p.mine ? "plToSession" : "plToMine")}: ${p.name}`}
        onClick={() => actions.movePlace(p.id, p.mine ? "session" : "mine")}>{p.mine ? "↓" : "★"}</button>
      <button className="iconbtn sm" title={t("plEdit")} aria-label={`${t("plEdit")}: ${p.name}`}
        onClick={() => useApp.setState({ placeEdit: { plotId, place: p, id: p.id, where: p.mine ? "mine" : "session" } })}>✎</button>
      <button className="iconbtn sm" title={t("plDelete")} aria-label={`${t("plDelete")}: ${p.name}`} onClick={() => actions.removePlace(p.id)}>×</button>
    </li>
  );
  const session = shown.filter((p) => !p.mine), mine = shown.filter((p) => p.mine);
  return (
    <aside className="places-panel" role="region" aria-label={t("plPanel")} onMouseDown={(e) => e.stopPropagation()} onDoubleClick={(e) => e.stopPropagation()}
      onContextMenu={(e) => e.stopPropagation()} onKeyDown={(e) => { if (e.key === "Escape") { e.stopPropagation(); close(); } }}>
      <div className="pl-head">
        <b title={t("plPanelHint")}>{t("plPanel")}</b>
        <span className="spacer" />
        <button className="iconbtn sm" aria-label={t("close")} title={t("close")} onClick={close}>×</button>
      </div>
      <input ref={searchRef} className="pl-search" type="search" value={q} placeholder={t("plSearch")} title={t("plSearchHint")} aria-label={t("plSearch")}
        onChange={(e) => setQ(e.target.value)}
        onKeyDown={(e) => {
          if (e.key !== "Enter") return;
          if (goto) mapFly.get(plotId)?.(goto);
          else if (shown[0]) fly(shown[0]);
        }} />
      {goto && <button className="btn sm pl-goto" onClick={() => mapFly.get(plotId)?.(goto)}>
        {t("plGoTo", { pos: fmtCoord(goto.lat, goto.lon, 5) })}</button>}
      <div className="pl-actions">
        <button className="btn sm pl-add" onClick={() => useApp.setState({ placeEdit: { plotId, place: { kind: "point" } } })}>+ {t("plAdd")}</button>
        <button className="btn sm pl-saveview" disabled={!mapCameraNow.get(plotId)} onClick={() => void saveView()}>{t("plSaveView")}</button>
        <button className="btn sm" title={t("plImportHint")} onClick={() => void importFile()}>{t("plImport")}</button>
        <button className="btn sm" disabled={!list.length} onClick={() => void exportFile()}>{t("plExport")}</button>
      </div>
      <div className="pl-lists">
        <h4 title={t("plSessionHint")}>{t("plSession")}</h4>
        {session.length ? <ul className="pl-list pl-session">{session.map(row)}</ul> : <p className="hint">{t("plNone")}</p>}
        <h4 title={t("plMineHint")}>{t("plMine")}</h4>
        {mine.length ? <ul className="pl-list pl-mine">{mine.map(row)}</ul> : <p className="hint">—</p>}
      </div>
    </aside>
  );
}
