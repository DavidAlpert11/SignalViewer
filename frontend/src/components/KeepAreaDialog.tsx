import { useEffect, useState } from "react";
import { useT, fmtNum } from "../i18n";
import { useApp } from "../store";
import { isOnlineBase, type GeoBase } from "../mapBase";
import { keepApi, useMyMaps, type KeepEstimate, type KeepProgress, type KeptArea } from "../mapLayers";
import { useEscape } from "./Overlays";

/** The area to keep: the recordings' tracks or what is on screen, as [south, west, north, east] (null: none). */
export type AreaOf = (kind: "tracks" | "view") => number[] | null;

/* M3: *Keep this area offline…* - before going to the field, the tiles of an area at a range of zooms are
   downloaded once into the tile cache and then shown with no internet (also with "Never use the network" on).
   Only from sources whose terms allow it (backend app/tilekeep.py says which and why): the ground heights (open
   data) and the user's own map servers; the street / satellite / topo servers refuse bulk downloads, and the
   dialog says so for the layer on screen. The kept areas are listed with their size and Delete. */
export default function KeepAreaDialog({ areaOf, base, onClose }: { areaOf: AreaOf; base: Exclude<GeoBase, "auto">; onClose: () => void }) {
  const t = useT();
  const lang = useApp((s) => s.lang);
  useEscape(onClose, true);
  const servers = useMyMaps().filter((m) => m.kind !== "mbtiles" && m.ok);
  const sources: { src: string; label: string }[] = [
    { src: "terrarium", label: t("kaGround") },
    ...servers.map((m) => ({ src: m.src, label: m.name })),
    ...(isOnlineBase(base) && !base.startsWith("my:") ? [{ src: base as string, label: t(`ml_${base}` as "ml_osm") }] : []),
  ];
  const [src, setSrc] = useState(base.startsWith("my:") && servers.some((m) => m.src === base) ? base as string : sources[0].src);
  const tracks = areaOf("tracks"), view = areaOf("view");
  const [kind, setKind] = useState<"tracks" | "view">(tracks ? "tracks" : "view");
  const bounds = kind === "tracks" ? tracks : view;
  const [zmin, setZmin] = useState(10);
  const [zmax, setZmax] = useState(src === "terrarium" ? 12 : 16);
  const [name, setName] = useState("");
  const [est, setEst] = useState<KeepEstimate | null>(null);
  const [err, setErr] = useState("");
  const [prog, setProg] = useState<KeepProgress | null>(null);
  const [areas, setAreas] = useState<KeptArea[]>([]);
  const running = !!prog?.running;

  const reload = () => keepApi.areas().then((r) => setAreas(r.areas)).catch(() => undefined);
  useEffect(() => { void reload(); void keepApi.progress().then(setProg).catch(() => undefined); }, []);
  // the estimate follows the choices (a short pause: the zoom fields are typed in)
  useEffect(() => {
    if (!bounds) { setEst(null); return; }
    const h = window.setTimeout(() => {
      keepApi.estimate(src, bounds, zmin, zmax).then((e) => { setEst(e); setErr(""); }).catch((e: Error) => { setEst(null); setErr(e.message); });
    }, 250);
    return () => window.clearTimeout(h);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [src, kind, zmin, zmax, bounds?.join(",")]);
  // progress while a download runs
  useEffect(() => {
    if (!running) return;
    const h = window.setInterval(() => {
      keepApi.progress().then((p) => { setProg(p); if (!p.running) void reload(); }).catch(() => undefined);
    }, 500);
    return () => window.clearInterval(h);
  }, [running]);

  const start = async () => {
    if (!bounds) return;
    setErr("");
    try {
      await keepApi.start(src, bounds, zmin, zmax, name || t("kaDefaultName", { n: areas.length + 1 }));
      setProg(await keepApi.progress());
      void reload();
    } catch (e) { setErr((e as Error).message); }
  };
  const mb = (b: number) => fmtNum(b / 1048576, lang, b < 10 * 1048576 ? 2 : 3);
  const srcName = (s: string) => sources.find((x) => x.src === s)?.label ?? s;

  return (
    <div className="scrim" onMouseDown={onClose}>
      <div className="dialog keep-dialog" role="dialog" aria-modal="true" aria-label={t("kaTitle")} onMouseDown={(e) => e.stopPropagation()}>
        <div className="dialog-head"><h2>{t("kaTitle")}</h2></div>
        <div className="dialog-body keep-form">
          <p className="hint">{t("kaIntro")}</p>
          <label><span>{t("kaLayer")}</span>
            <select value={src} disabled={running} onChange={(e) => { setSrc(e.target.value); if (e.target.value === "terrarium") setZmax(Math.min(zmax, 12)); }}>
              {sources.map((s) => <option key={s.src} value={s.src}>{s.label}</option>)}
            </select></label>
          <div className="keep-row" role="radiogroup" aria-label={t("kaArea")}>
            <span>{t("kaArea")}</span>
            <label className="acheck"><input type="radio" name="ka-area" checked={kind === "tracks"} disabled={!tracks || running} onChange={() => setKind("tracks")} />{t("kaAreaTracks")}</label>
            <label className="acheck"><input type="radio" name="ka-area" checked={kind === "view"} disabled={!view || running} onChange={() => setKind("view")} />{t("kaAreaView")}</label>
          </div>
          <div className="keep-row">
            <span>{t("kaZooms")}</span>
            <input type="number" className="num" min={0} max={19} value={zmin} disabled={running} aria-label={t("kaFrom")} onChange={(e) => setZmin(Math.max(0, Math.min(19, Number(e.target.value) || 0)))} />
            <span>–</span>
            <input type="number" className="num" min={0} max={19} value={zmax} disabled={running} aria-label={t("kaTo")} onChange={(e) => setZmax(Math.max(0, Math.min(19, Number(e.target.value) || 0)))} />
          </div>
          <label><span>{t("kaName")}</span><input value={name} disabled={running} placeholder={t("kaDefaultName", { n: areas.length + 1 })} onChange={(e) => setName(e.target.value)} /></label>
          {est && (
            <div className={`keep-est${est.allowed && !est.tooMany ? "" : " warn"}`} role="status" data-tiles={est.tiles}>
              {!est.allowed ? t("kaRefused", { why: est.reason })
                : est.tooMany ? t("kaTooMany", { n: fmtNum(est.tiles, lang, 6), limit: fmtNum(est.limit, lang, 6) })
                : <>{t("kaEstimate", { n: fmtNum(est.tiles, lang, 6), mb: mb(est.bytes), have: fmtNum(est.have, lang, 6) })}
                    {!est.network && <> {t("kaNetOff")}</>}</>}
            </div>
          )}
          {!bounds && <div className="keep-est warn">{t("kaNoArea")}</div>}
          {err && <div className="keep-est warn" role="alert">{err}</div>}
          {prog && (prog.running || prog.total) ? (
            <div className="keep-prog" role="status" data-running={prog.running ? 1 : undefined}>
              <progress max={prog.total || 1} value={prog.done || 0} />
              <span className="num">{t("kaProgress", { done: fmtNum(prog.done ?? 0, lang, 6), total: fmtNum(prog.total ?? 0, lang, 6) })}
                {(prog.failed ?? 0) > 0 && <> · {t("kaFailed", { n: fmtNum(prog.failed ?? 0, lang, 6) })}</>}</span>
              {prog.error && <span className="keep-err">{prog.error}</span>}
              {!prog.running && prog.stopped && <span>{t("kaStopped")}</span>}
            </div>
          ) : null}
          <h3 className="keep-h">{t("kaKept")}</h3>
          {areas.length === 0 ? <p className="hint">{t("kaNone")}</p> : (
            <table className="data keep-list">
              <tbody>{areas.map((a) => (
                <tr key={a.id} data-area={a.id}>
                  <td>{a.name}</td><td className="muted">{srcName(a.src)}</td>
                  <td className="num">{a.zmin}–{a.zmax}</td>
                  <td className="num">{fmtNum(a.present, lang, 6)} / {fmtNum(a.tiles, lang, 6)}</td>
                  <td className="num">{mb(a.bytes)} MB</td>
                  <td><button className="btn sm ghost" disabled={running} onClick={() => { void keepApi.remove(a.id).then(reload); }}>{t("kaDelete")}</button></td>
                </tr>))}</tbody>
            </table>
          )}
        </div>
        <div className="dialog-foot">
          <span className="spacer" />
          {running
            ? <button className="btn" onClick={() => { void keepApi.stop().then(setProg); }}>{t("kaStop")}</button>
            : <button className="btn" onClick={onClose}>{t("close")}</button>}
          <button className="btn primary keep-start" disabled={running || !est || !est.allowed || est.tooMany || !est.network} onClick={() => void start()}>{t("kaStart")}</button>
        </div>
      </div>
    </div>
  );
}
