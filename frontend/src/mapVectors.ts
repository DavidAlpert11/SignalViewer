/* F6: an object's two signals (north, east) as arrows along its track - the places and values from the backend
   (/api/vectors: evenly along the distance, on the track's own times), for the 2D map and the 3D view. */
import { useEffect, useState } from "react";
import { call } from "./api";
import type { MapObject } from "./store";

export interface Vectors { t: number[]; lat: number[]; lon: number[]; alt: number[] | null; vn: number[]; ve: number[]; max: number }

/** The arrows of each object that has its two signals, by object id (refetched when its signals change). */
export function useVectors(objects: MapObject[], n = 40): Record<string, Vectors> {
  const [out, setOut] = useState<Record<string, Vectors>>({});
  const key = objects.filter((o) => o.vecN && o.vecE).map((o) => [o.id, o.lat, o.lon, o.alt ?? "", o.altRef ?? "", o.vecN, o.vecE].join(",")).join("|");
  useEffect(() => {
    let live = true;
    const want = objects.filter((o) => o.vecN && o.vecE);
    if (!want.length) { setOut({}); return; }
    void Promise.all(want.map((o) => call<Vectors>("/api/vectors", { lat: o.lat, lon: o.lon, alt: o.alt ?? null, altRef: o.altRef ?? "msl",
      vn: o.vecN, ve: o.vecE, n }).then((v) => [o.id, v] as const).catch(() => null)))
      .then((rows) => { if (live) setOut(Object.fromEntries(rows.filter((r): r is readonly [string, Vectors] => !!r))); });
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, n]);
  return out;
}
