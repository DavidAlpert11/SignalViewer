import { useEffect, useState } from "react";
import { actions, PLACE_ICONS, useApp, type Place, type PlaceIcon } from "../store";
import { useT, type TKey } from "../i18n";
import { api } from "../api";
import { allPlaces, parsePlace, placeIconSvg, PLACE_COLOR } from "../places";
import { mapFly } from "../globeBridge";
import { useEscape } from "./Overlays";

/* P7: a new place (from a right-click on the Map - its position filled in -, from *Add a place…* typed, from
   *Mark this spot*) or an existing one: name, icon, colour, position (decimal degrees or
   degrees-minutes-seconds, the backend's one parser), height (empty: the ground there), note, and which list
   keeps it. */
export default function PlaceDialog() {
  const t = useT();
  const req = useApp((s) => s.placeEdit)!;
  const editing = !!req.id;
  const close = () => useApp.setState({ placeEdit: null });
  useEscape(close, true);
  const p0 = req.place;
  const fmt = (v?: number) => (v === undefined || v === null || !Number.isFinite(v) ? "" : String(Math.round(v * 1e7) / 1e7));
  const [name, setName] = useState(p0.name ?? t("plDefaultName", { n: allPlaces().length + 1 }));
  const [icon, setIcon] = useState<PlaceIcon>(p0.icon ?? "pin");
  const [color, setColor] = useState(p0.color ?? PLACE_COLOR);
  const [pos, setPos] = useState(p0.lat !== undefined && p0.lon !== undefined ? `${fmt(p0.lat)}, ${fmt(p0.lon)}` : "");
  const [alt, setAlt] = useState(fmt(p0.alt));
  const [note, setNote] = useState(p0.note ?? "");
  const [where, setWhere] = useState<"session" | "mine">(req.where ?? "session");
  const [at, setAt] = useState<{ lat: number; lon: number } | null>(p0.lat !== undefined && p0.lon !== undefined ? { lat: p0.lat, lon: p0.lon } : null);
  const point = (p0.kind ?? "point") === "point";
  // the position as typed, read by the backend's parser (a short pause after typing)
  useEffect(() => {
    if (!point) return;
    const h = window.setTimeout(() => { void parsePlace(pos).then(setAt); }, 200);
    return () => window.clearTimeout(h);
  }, [pos, point]);
  const save = async () => {
    if (!at) return;
    let height: number | undefined = alt.trim() === "" ? undefined : Number(alt);
    if (height !== undefined && !Number.isFinite(height)) height = undefined;
    if (height === undefined && point) {
      try { height = (await api.groundAt(at.lat, at.lon)).ground ?? undefined; } catch { /* no elevation here: on the sea */ }
    }
    const body: Partial<Place> = { name: name.trim() || t("plDefaultName", { n: allPlaces().length + 1 }), lat: at.lat, lon: at.lon, alt: height,
      ...(point ? { icon } : {}), color, note: note.trim() || undefined };
    if (editing) {
      actions.updatePlace(req.id!, body);
      const mine = useApp.getState().myPlaces.some((x) => x.id === req.id);
      if ((where === "mine") !== mine) actions.movePlace(req.id!, where);
    } else {
      actions.addPlace({ kind: p0.kind ?? "point", ...p0, ...body } as Place, where);
      if (req.plotId) useApp.setState({ placesPanel: req.plotId });     // the list shows where it went
      if (req.plotId && !p0.lat) mapFly.get(req.plotId)?.({ lat: at.lat, lon: at.lon, alt: height });   // typed: go there
    }
    close();
  };
  return (
    <div className="scrim" onMouseDown={close}>
      <div className="dialog place-dialog" role="dialog" aria-modal="true" aria-label={t(editing ? "plDialogEdit" : "plDialogNew")} onMouseDown={(e) => e.stopPropagation()}>
        <div className="dialog-head"><h2>{t(editing ? "plDialogEdit" : "plDialogNew")}</h2></div>
        <div className="dialog-body place-form">
          <label><span>{t("plName")}</span><input className="place-name" value={name} autoFocus onChange={(e) => setName(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && at) void save(); }} /></label>
          {point && (
            <div className="place-icons" role="radiogroup" aria-label={t("plIcon")}>
              {PLACE_ICONS.map((k) => (
                <button key={k} role="radio" aria-checked={icon === k} className={`place-icon${icon === k ? " on" : ""}`} title={t(`plIcon_${k}` as TKey)}
                  aria-label={t(`plIcon_${k}` as TKey)} onClick={() => setIcon(k)}><img src={placeIconSvg(k, color, 22)} alt="" width={22} height={22} /></button>
              ))}
              <label className="place-color" title={t("plColor")}><input type="color" value={color} aria-label={t("plColor")} onChange={(e) => setColor(e.target.value)} /></label>
            </div>
          )}
          {point && <label><span>{t("plPosition")}</span>
            <input className="place-pos" dir="ltr" value={pos} placeholder="32.687, 35.39" title={t("plPositionHint")} aria-invalid={!!pos && !at}
              onChange={(e) => setPos(e.target.value)} /></label>}
          {point && pos && !at && <p className="hint warn" role="alert">{t("plPositionBad")}</p>}
          {point && <label><span>{t("plAlt")}</span>
            <input className="place-alt" dir="ltr" inputMode="decimal" value={alt} placeholder={t("plAltHint")} onChange={(e) => setAlt(e.target.value)} /></label>}
          <label><span>{t("plNote")}</span><input value={note} onChange={(e) => setNote(e.target.value)} /></label>
          <div className="seg place-where" role="radiogroup" aria-label={t("plWhere")}>
            <span className="seg-label">{t("plWhere")}</span>
            <button role="radio" aria-checked={where === "session"} className={where === "session" ? "on" : ""} title={t("plSessionHint")} onClick={() => setWhere("session")}>{t("plSession")}</button>
            <button role="radio" aria-checked={where === "mine"} className={where === "mine" ? "on" : ""} title={t("plMineHint")} onClick={() => setWhere("mine")}>{t("plMine")}</button>
          </div>
        </div>
        <div className="dialog-foot">
          {editing && <button className="btn danger" onClick={() => { actions.removePlace(req.id!); close(); }}>{t("plDelete")}</button>}
          <span className="spacer" />
          <button className="btn" onClick={close}>{t("cancel")}</button>
          <button className="btn primary place-save" disabled={!at} onClick={() => void save()}>{t("plSave")}</button>
        </div>
      </div>
    </div>
  );
}
