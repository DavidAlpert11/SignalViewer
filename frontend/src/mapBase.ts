/* O1: which map layer is really drawn. "Automatic" is the offline map the app draws from bundled
   data - nothing leaves the PC unless an online layer is chosen by hand. With "Never use the
   network" (Settings, or SV_OFFLINE=1 for the app) an online layer falls back to the offline map;
   the backend refuses to download in that case too (app/tiles.py). */
import { useApp } from "./store";
import { isMyMap, myMap, myMapsLoaded, useMyMaps } from "./mapLayers";

/** M4: "my:<id>" = a layer of My maps (an MBTiles file or the user's own tile server). */
export type GeoBase = "auto" | "osm" | "esri" | "light" | "dark" | "satellite" | "satroads" | "topo" | "offline" | `my:${string}`;
export const GEO_BASES: GeoBase[] = ["auto", "offline", "osm", "esri", "light", "dark", "satellite", "satroads", "topo"];
/** A layer whose picture is a photo (names and borders drawn light over it). M2: "satroads" = the photo + roads. */
export const isPhotoBase = (b: string): boolean => b === "satellite" || b === "satroads";

/** Online = its tiles come from the internet. My maps: an MBTiles file or a server on this PC / the local network is not. */
export const isOnlineBase = (b: GeoBase): boolean =>
  b !== "auto" && b !== "offline" && (!isMyMap(b) || !(myMap(b)?.localOnly ?? true));

/** The layer drawn for the chosen one: "offline" or an online source (a map of My maps no longer in the list: offline). */
export function effectiveBase(chosen: GeoBase, networkOff: boolean): Exclude<GeoBase, "auto"> {
  if (chosen === "auto" || (networkOff && isOnlineBase(chosen))) return "offline";
  if (isMyMap(chosen) && myMapsLoaded() && !myMap(chosen)?.ok) return "offline";
  return chosen;
}

/** A saved layer value this version knows (sessions, the UI's settings). */
export const knownBase = (b: unknown): b is GeoBase => typeof b === "string" && ((GEO_BASES as string[]).includes(b) || /^my:[\w-]+$/.test(b));

/** The layer drawn now (hook): the chosen layer and the network setting together. */
export function useMapBase(): Exclude<GeoBase, "auto"> {
  const chosen = useApp((s) => s.geoBase);
  const off = useApp((s) => s.offlineOnly || s.offlineForced);
  useMyMaps();                                                  // re-drawn when My maps arrive / change
  return effectiveBase(chosen, off);
}
