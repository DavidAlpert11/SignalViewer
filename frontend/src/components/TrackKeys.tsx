import { useApp, type MapObject } from "../store";
import { fmtNum } from "../i18n";
import type { TrackColors } from "../mapObjects";

/** What a coloured track's colours are: a mode per colour, or the scale from lowest to highest. */
export default function TrackKeys({ objects, colors }: { objects: MapObject[]; colors: Record<string, TrackColors> }) {
  const lang = useApp((s) => s.lang);
  const runs = useApp((s) => s.runs);
  const shown = objects.filter((o) => colors[o.id]);
  if (!shown.length) return null;
  return (
    <div className="track-keys">
      {shown.map((o) => {
        const c = colors[o.id];
        const name = o.colorSig ? (runs.flatMap((r) => r.signals).find((x) => x.id === o.colorSig)?.name ?? "") : "";
        return (
          <div key={o.id} className="track-key">
            <b>{o.name}</b> <span className="tk-sig">{name}</span>
            {c.ramp
              ? <div className="tk-ramp"><span dir="ltr">{fmtNum(c.ramp.lo, lang, 4)}</span>
                  <i style={{ background: `linear-gradient(to right, ${c.ramp.colors.join(",")})` }} /><span dir="ltr">{fmtNum(c.ramp.hi, lang, 4)}</span></div>
              : <div className="tk-items">{c.key.slice(0, 14).map((k) => <span key={k.label}><i style={{ background: k.color }} />{k.label}</span>)}</div>}
          </div>
        );
      })}
    </div>
  );
}
