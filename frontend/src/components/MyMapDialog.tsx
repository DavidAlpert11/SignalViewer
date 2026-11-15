import { useState } from "react";
import { useT } from "../i18n";
import { pickPath } from "../store";
import { addMyMap } from "../mapLayers";
import { useEscape } from "./Overlays";

/* M4: *Add a map…* - the organisation's own maps: a raster MBTiles file (fully offline) or a tile server address
   (XYZ, or TMS), e.g. a server on the local network. Checked by the backend (app/mymaps.py) when added: a vector
   MBTiles file or an address without {z} {x} {y} is refused with what to do. */
export default function MyMapDialog({ onClose, onAdded }: { onClose: () => void; onAdded: (src: string) => void }) {
  const t = useT();
  useEscape(onClose, true);
  const [kind, setKind] = useState<"mbtiles" | "server">("mbtiles");
  const [path, setPath] = useState("");
  const [url, setUrl] = useState("");
  const [tms, setTms] = useState(false);
  const [name, setName] = useState("");
  const [maxzoom, setMaxzoom] = useState(19);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const ok = kind === "mbtiles" ? !!path.trim() : !!url.trim();
  const add = async () => {
    setBusy(true); setErr("");
    try {
      const m = await addMyMap(kind === "mbtiles" ? { kind, path: path.trim(), name: name.trim() }
        : { kind: tms ? "tms" : "xyz", url: url.trim(), name: name.trim(), maxzoom });
      onAdded(m.src);
      onClose();
    } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  };
  return (
    <div className="scrim" onMouseDown={onClose}>
      <div className="dialog mymap-dialog" role="dialog" aria-modal="true" aria-label={t("mmTitle")} onMouseDown={(e) => e.stopPropagation()}>
        <div className="dialog-head"><h2>{t("mmTitle")}</h2></div>
        <div className="dialog-body keep-form">
          <p className="hint">{t("mmIntro")}</p>
          <div className="keep-row" role="radiogroup" aria-label={t("mmTitle")}>
            <label className="acheck"><input type="radio" name="mm-kind" checked={kind === "mbtiles"} onChange={() => setKind("mbtiles")} />{t("mmKindFile")}</label>
            <label className="acheck"><input type="radio" name="mm-kind" checked={kind === "server"} onChange={() => setKind("server")} />{t("mmKindServer")}</label>
          </div>
          {kind === "mbtiles" ? (
            <div className="keep-row">
              <span>{t("mmFile")}</span>
              <input className="mm-path" value={path} dir="ltr" onChange={(e) => setPath(e.target.value)} />
              <button className="btn sm" onClick={() => { void pickPath({ mode: "open", title: t("mmFile"), exts: [".mbtiles"] }).then((p) => { if (p) setPath(p); }); }}>{t("mmChoose")}</button>
            </div>
          ) : (<>
            <label><span>{t("mmUrl")}</span><input className="mm-url" value={url} dir="ltr" placeholder="http://maps.local/tiles/{z}/{x}/{y}.png" onChange={(e) => setUrl(e.target.value)} /></label>
            <p className="hint">{t("mmUrlHint")}</p>
            <div className="keep-row">
              <label className="acheck"><input type="checkbox" checked={tms} onChange={(e) => setTms(e.target.checked)} />{t("mmTms")}</label>
              <span>{t("mmMaxZoom")}</span>
              <input type="number" className="num" min={0} max={24} value={maxzoom} onChange={(e) => setMaxzoom(Math.max(0, Math.min(24, Number(e.target.value) || 0)))} />
            </div>
          </>)}
          <label><span>{t("mmName")}</span><input value={name} onChange={(e) => setName(e.target.value)} /></label>
          {err && <div className="keep-est warn" role="alert">{err}</div>}
        </div>
        <div className="dialog-foot">
          <span className="spacer" />
          <button className="btn" onClick={onClose}>{t("cancel")}</button>
          <button className="btn primary mm-add" disabled={!ok || busy} onClick={() => void add()}>{t("mmAdd")}</button>
        </div>
      </div>
    </div>
  );
}
