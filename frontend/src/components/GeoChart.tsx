import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api";
import { actions, shownSpan, useApp, type MapObject, type Plot } from "../store";
import { drawObjectIcon } from "./mapIcons";
import { objectAt, type ObjTrack } from "../mapObjects";
import type { Country } from "../worldCountries";
import { dpr, indexSpan, PLOT_THEME, uiScale, useSize } from "./chartUtil";

interface Props { plot: Plot; index: number; onLoading: (b: boolean) => void; emptyText: string; notDegrees: string }

interface Track { id: string; lon: Float64Array; lat: Float32Array; t: Float64Array }
/** cx, cy: map centre in Web-Mercator world units (0..1); z: zoom (256 * 2^z pixels across the world). */
interface View { cx: number; cy: number; z: number }

export type GeoBase = "auto" | "osm" | "esri" | "light" | "dark" | "satellite" | "topo" | "offline";
const MAXZ: Record<string, number> = { osm: 19, esri: 19, light: 16, dark: 16, satellite: 19, topo: 17, offline: 14 };
/* The offline map: tiles the app draws itself from bundled data (terrain, water, roads), so a map
   works on a machine with no internet; also what fills in for an online tile that cannot be had. */
const OFFLINE_MAXZ = 14;
const offlineSrc = (dark: boolean) => (dark ? "offline_topo_dark" : "offline_topo");
const OVERLAY: Record<string, string> = { light: "light_ref", dark: "dark_ref" };    // labels, drawn over the map
const ESRI_ATT = "Esri, HERE, Garmin, © OpenStreetMap contributors, GIS User Community";
const ATTRIB: Record<string, string> = {
  osm: "© OpenStreetMap contributors", esri: ESRI_ATT, light: ESRI_ATT, dark: ESRI_ATT,
  satellite: "Tiles © Esri — Esri, Maxar, Earthstar Geographics, GIS User Community",
  topo: "© OpenStreetMap contributors, SRTM | © OpenTopoMap (CC-BY-SA)",
  offline: "Natural Earth · Terrain Tiles (Mapzen: SRTM, GMTED2010, ETOPO1) · © OpenStreetMap contributors",
};

/* --------------------------------------------------------------- projection */
const LAT_MAX = 85.05112878;
const mx = (lon: number) => (lon + 180) / 360;
const my = (lat: number) => {
  const s = Math.sin((Math.max(-LAT_MAX, Math.min(LAT_MAX, lat)) * Math.PI) / 180);
  return 0.5 - Math.log((1 + s) / (1 - s)) / (4 * Math.PI);
};
const lonOf = (x: number) => x * 360 - 180;
const latOf = (y: number) => (Math.atan(Math.sinh(Math.PI * (1 - 2 * y))) * 180) / Math.PI;

/** Longitudes given as 0..360 are shown as -180..180, like the map. */
function normLon(lon: Float64Array): Float64Array {
  let lo = Infinity, hi = -Infinity;
  for (const v of lon) if (Number.isFinite(v)) { if (v < lo) lo = v; if (v > hi) hi = v; }
  if (lo >= 0 && hi > 180 && hi <= 360) return Float64Array.from(lon, (v) => (v > 180 ? v - 360 : v));
  return lon;
}

function fitView(tracks: Track[], w: number, h: number): View | null {
  let x0 = Infinity, x1 = -Infinity, y0 = Infinity, y1 = -Infinity;
  for (const t of tracks) for (let i = 0; i < t.lon.length; i++) {
    const a = t.lon[i], b = t.lat[i];
    if (!Number.isFinite(a) || !Number.isFinite(b) || Math.abs(b) > 90 || Math.abs(a) > 360) continue;
    const X = mx(a), Y = my(b);
    if (X < x0) x0 = X; if (X > x1) x1 = X; if (Y < y0) y0 = Y; if (Y > y1) y1 = Y;
  }
  if (!Number.isFinite(x0)) return null;
  const dx = Math.max(x1 - x0, 2e-9) * 1.25, dy = Math.max(y1 - y0, 2e-9) * 1.25;
  const z = Math.log2(Math.min(w / dx, h / dy) / 256);
  return { cx: (x0 + x1) / 2, cy: (y0 + y1) / 2, z: Math.max(1, Math.min(21, z)) };
}

/* --------------------------------------------------------------- tiles (shared by every map) */
const tileCache = new Map<string, HTMLImageElement | "failed">();
const loading = new Set<string>();
let listeners: (() => void)[] = [];
function getTile(src: string, z: number, x: number, y: number): HTMLImageElement | null {
  const key = `${src}/${z}/${x}/${y}`;
  const hit = tileCache.get(key);
  if (hit === "failed") return null;
  if (hit) { tileCache.delete(key); tileCache.set(key, hit); return hit; }          // LRU order
  if (!loading.has(key) && loading.size < 24) {
    loading.add(key);
    const img = new Image();
    img.onload = () => { loading.delete(key); tileCache.set(key, img); trim(); listeners.forEach((f) => f()); };
    img.onerror = () => { loading.delete(key); tileCache.set(key, "failed"); listeners.forEach((f) => f()); };
    img.src = `/api/tiles/${key}`;
  }
  return null;
}
function trim() {
  while (tileCache.size > 800) tileCache.delete(tileCache.keys().next().value!);
}

let countriesP: Promise<Country[]> | null = null;
const loadCountries = () => (countriesP ??= import("../worldCountries").then((m) => m.COUNTRIES));
/** Place / airport names for the offline map (x lon, y lat, n English, h Hebrew, r rank: 1 = most important). */
interface Place { x: number; y: number; n: string; h: string; r: number; a?: number }
let placesP: Promise<Place[]> | null = null;
const loadPlaces = () => (placesP ??= fetch("/api/basemap/places").then((r) => r.json()).then((d) => d.places as Place[]).catch(() => []));

/** Geo plot: longitude (X signal) and latitude (the plot's signals) on a map - street, light, dark,
 *  satellite or topographic tiles (fetched through the app and cached on disk, so places already
 *  seen work offline), over bundled country borders and names that always work offline.
 *  Wheel = zoom, drag = pan, double-click = fit to the track. */
export default function GeoChart({ plot, index, onLoading, emptyText, notDegrees }: Props) {
  const theme = useApp((s) => s.theme);
  const lang = useApp((s) => s.lang);
  const scale = useApp((s) => s.uiScale);
  const runs = useApp((s) => s.runs);
  const dataVersion = useApp((s) => s.dataVersion);
  const cursor = useApp((s) => s.cursor);
  const cvals = useApp((s) => s.cvals);
  const playMode = useApp((s) => s.playMode);
  const windowSec = useApp((s) => s.windowSec);
  const baseSetting = useApp((s) => s.geoBase);
  const base = baseSetting === "auto" ? (theme === "dark" ? "dark" : "osm") : baseSetting;
  const wrapRef = useRef<HTMLDivElement>(null);
  const cvRef = useRef<HTMLCanvasElement>(null);
  const size = useSize(wrapRef);
  const [tracks, setTracks] = useState<Track[]>([]);
  const [view, setView] = useState<View | null>(null);
  const baseRef = useRef<{ key: string; canvas: HTMLCanvasElement } | null>(null);
  /* objects: each one's signals on one time axis, fetched when its signals change */
  const objects: MapObject[] = useMemo(() => plot.objects ?? [], [plot.objects]);
  const [objTracks, setObjTracks] = useState<Record<string, ObjTrack>>({});
  const objKey = objects.map((o) => [o.id, o.lat, o.lon, o.alt, o.yaw, o.pitch, o.roll].join(":")).join("|");
  const [countries, setCountries] = useState<Country[] | null>(null);
  const [places, setPlaces] = useState<Place[] | null>(null);
  const [tick, setTick] = useState(0);
  const userView = useRef(false);               // the user zoomed / panned: stop auto-fitting
  const [mouse, setMouse] = useState<{ lon: number; lat: number } | null>(null);

  const ys = plot.signals.map((s) => s.sig);
  const yKey = ys.join("|");
  const runsKey = runs.map((r) => `${r.id}:${r.timeOffset}:${r.samples}:${r.signals.length}`).join("|");

  useEffect(() => { loadCountries().then(setCountries); loadPlaces().then(setPlaces); }, []);
  useEffect(() => {
    const f = () => setTick((n) => n + 1);
    listeners.push(f);
    return () => { listeners = listeners.filter((g) => g !== f); };
  }, []);

  useEffect(() => {
    if (!plot.xSignal || !ys.length) { setTracks([]); return; }
    let cancelled = false;
    const h = window.setTimeout(async () => {
      onLoading(true);
      try {
        const r = await api.xy(plot.xSignal!, ys, plot.xyAlign ?? "linear", null, null);
        if (!cancelled) setTracks(r.filter((s) => !s.missing).map((s) => ({ id: s.id, lon: normLon(s.x), lat: s.y, t: s.t })));
      } catch (e) {
        if (!cancelled) useApp.getState().toast({ kind: "error", text: String((e as Error).message) });
      } finally { if (!cancelled) onLoading(false); }
    }, 60);
    return () => { cancelled = true; window.clearTimeout(h); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [plot.xSignal, yKey, plot.xyAlign, dataVersion, runsKey]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const out: Record<string, ObjTrack> = {};
      for (const o of plot.objects ?? []) {
        try {
          const r = await api.objectTrack(o);
          out[o.id] = { t: r.t, lat: r.lat, lon: normLon(r.lon), yaw: r.yaw, course: r.course, units: r.units };
        } catch { /* a signal no longer open: the object is skipped */ }
      }
      if (!cancelled) setObjTracks(out);
    })();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [objKey, dataVersion, runsKey]);
  /** Tracks and objects, for fitting the view. */
  const allTracks = (): Track[] => [...tracks, ...Object.entries(objTracks).map(([id, o]) => ({ id, lon: o.lon, lat: Float32Array.from(o.lat), t: o.t }))];
  const allTracksRef = useRef(allTracks);
  allTracksRef.current = allTracks;

  /* fit to the track whenever data arrives, until the user moves the map */
  useEffect(() => {
    if (size.w < 50 || size.h < 50) return;
    if (userView.current && view) return;
    setView(fitView(allTracks(), size.w, size.h));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tracks, objTracks, size.w, size.h]);

  /* following an object: the map keeps it in the middle as the time moves (zoom stays the user's) */
  useEffect(() => {
    const id = plot.followObject;
    const tr = id ? objTracks[id] : null;
    if (!tr || !cursor.on || cursor.t1 === null) return;
    const o = objects.find((x) => x.id === id);
    const st = objectAt(tr, cursor.t1, o?.angleUnit);
    if (!st) return;
    userView.current = true;
    setView((v) => (v ? { ...v, cx: mx(st.lon), cy: my(st.lat) } : v));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [plot.followObject, objTracks, cursor.t1, cursor.on]);
  useEffect(() => { userView.current = false; }, [plot.xSignal, yKey]);

  const badRange = tracks.some((t) => {
    let bad = 0, n = 0;
    for (let i = 0; i < t.lat.length; i += Math.max(1, Math.floor(t.lat.length / 500))) { n++; if (Math.abs(t.lat[i]) > 90 || Math.abs(t.lon[i]) > 360) bad++; }
    return n > 0 && bad / n > 0.5;
  });

  /* ------------------------------ drawing ------------------------------ */
  useEffect(() => {
    const cv = cvRef.current;
    if (!cv || size.w < 50 || size.h < 50) return;
    const r = dpr(), W = size.w, H = size.h;
    cv.width = Math.round(W * r); cv.height = Math.round(H * r);
    const screen = cv.getContext("2d")!;
    screen.setTransform(r, 0, 0, r, 0, 0);
    let ctx = screen;
    const pt = PLOT_THEME[theme];
    const dark = theme === "dark";
    ctx.fillStyle = dark ? "#0e1620" : "#dfe9f1";               // sea
    ctx.fillRect(0, 0, W, H);
    if (!view) return;
    const S = 256 * 2 ** view.z;
    const X = (wx: number) => W / 2 + (wx - view.cx) * S;
    const Y = (wy: number) => H / 2 + (wy - view.cy) * S;
    const family = getComputedStyle(document.body).fontFamily;
    const font = `${Math.round(11 * uiScale())}px ${family}`;
    const wx0 = view.cx - W / 2 / S, wx1 = view.cx + W / 2 / S, wy0 = view.cy - H / 2 / S, wy1 = view.cy + H / 2 / S;

    // The base layer - tiles, borders, names - changes only with the view, size, theme, language or
    // newly arrived tiles. It is kept in a canvas of its own: during playback only the tracks and
    // objects are drawn again over a copy of it (a full redraw per frame held playback to ~36 fps).
    const baseKey = [W, H, r, view.cx, view.cy, view.z, theme, base, lang, !!countries, !!places, tick, uiScale()].join("|");
    const kept = baseRef.current?.key === baseKey ? baseRef.current.canvas : null;
    if (kept) screen.drawImage(kept, 0, 0, W, H);
    else {
    const bc = document.createElement("canvas");
    bc.width = cv.width; bc.height = cv.height;
    ctx = bc.getContext("2d")!;
    ctx.setTransform(r, 0, 0, r, 0, 0);
    ctx.fillStyle = dark ? "#0e1620" : "#dfe9f1";
    ctx.fillRect(0, 0, W, H);

    // 1. countries filled: what shows while online tiles load (the offline map has its own land)
    if (countries && base !== "offline") {
      ctx.lineWidth = 1;
      ctx.fillStyle = dark ? "#1d2735" : "#f3f1ea"; ctx.strokeStyle = dark ? "#41536b" : "#a8a49a";
      for (const c of countries) for (const poly of c.p) {
        let minx = Infinity, maxx = -Infinity, miny = Infinity, maxy = -Infinity;
        ctx.beginPath();
        for (let i = 0; i < poly.length; i += 2) {
          const px = X(mx(poly[i] / 100)), py = Y(my(poly[i + 1] / 100));
          if (px < minx) minx = px; if (px > maxx) maxx = px; if (py < miny) miny = py; if (py > maxy) maxy = py;
          if (i === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
        }
        if (maxx < 0 || minx > W || maxy < 0 || miny > H) continue;
        ctx.closePath(); ctx.fill(); ctx.stroke();
      }
    }

    // 2. tiles at the nearest whole zoom (a missing tile falls back to a lower-zoom one already loaded)
    let tilesShown = 0, tilesWanted = 0, offlineUsed = 0;
    const offSrc = offlineSrc(dark);
    const src = base === "offline" ? offSrc : base;
    {
      const zi = Math.max(0, Math.min(MAXZ[base] ?? 19, Math.round(view.z)));
      const n = 2 ** zi, tsz = S / n;
      const tx0 = Math.floor(wx0 * n), tx1 = Math.floor(wx1 * n), ty0 = Math.max(0, Math.floor(wy0 * n)), ty1 = Math.min(n - 1, Math.floor(wy1 * n));
      ctx.imageSmoothingEnabled = true;
      for (let ty = ty0; ty <= ty1; ty++) for (let tx = tx0; tx <= tx1; tx++) {
        const txw = ((tx % n) + n) % n;
        const dx = X(tx / n), dy = Y(ty / n);
        tilesWanted++;
        const img = getTile(src, zi, txw, ty);
        // an online tile that cannot be had (no internet): the offline map's tile in its place
        if (!img && base !== "offline" && zi <= OFFLINE_MAXZ && tileCache.get(`${src}/${zi}/${txw}/${ty}`) === "failed") {
          const off = getTile(offSrc, zi, txw, ty);
          if (off) { ctx.drawImage(off, dx, dy, tsz + 0.5, tsz + 0.5); tilesShown++; offlineUsed++; continue; }
        }
        if (img) {
          ctx.drawImage(img, dx, dy, tsz + 0.5, tsz + 0.5); tilesShown++;
          const ov = OVERLAY[base] ? getTile(OVERLAY[base], zi, txw, ty) : null;
          if (ov) ctx.drawImage(ov, dx, dy, tsz + 0.5, tsz + 0.5);
          continue;
        }
        for (let up = 1; up <= 6 && zi - up >= 0; up++) {                     // a parent tile, magnified
          const f = 2 ** up;
          const parent = tileCache.get(`${src}/${zi - up}/${Math.floor(txw / f)}/${Math.floor(ty / f)}`);
          if (parent && parent !== "failed") {
            const sw = 256 / f;
            ctx.drawImage(parent, (txw % f) * sw, (ty % f) * sw, sw, sw, dx, dy, tsz + 0.5, tsz + 0.5);
            break;
          }
        }
      }
    }

    // 3. what the offline map's tiles do not carry: borders, and names (drawn here: crisp, in the UI language)
    const ownNames = base === "offline" || offlineUsed > 0 || tilesShown < tilesWanted / 2;
    if (countries && (base === "offline" || offlineUsed > 0)) {
      ctx.lineWidth = 1; ctx.setLineDash([4, 3]);
      ctx.strokeStyle = dark ? "rgba(200,190,230,.55)" : "rgba(110,80,140,.55)";
      for (const c of countries) for (const poly of c.p) {
        let minx = Infinity, maxx = -Infinity, miny = Infinity, maxy = -Infinity;
        ctx.beginPath();
        for (let i = 0; i < poly.length; i += 2) {
          const px = X(mx(poly[i] / 100)), py = Y(my(poly[i + 1] / 100));
          if (px < minx) minx = px; if (px > maxx) maxx = px; if (py < miny) miny = py; if (py > maxy) maxy = py;
          if (i === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
        }
        if (maxx < 0 || minx > W || maxy < 0 || miny > H) continue;
        ctx.closePath(); ctx.stroke();
      }
      ctx.setLineDash([]);
    }
    const labelBoxes: [number, number, number, number][] = [];
    const overlaps = (box: [number, number, number, number]) =>
      labelBoxes.some((b) => !(box[2] < b[0] || box[0] > b[2] || box[3] < b[1] || box[1] > b[3]));
    // places first (by importance, more as you zoom in), then the country names where there is room
    if (places && ownNames && view.z >= 3) {
      // cities first; towns from zoom ~9; villages only from zoom 11 (else the names cover the map)
      const maxRank = view.z < 4 ? 2 : view.z < 5 ? 3 : view.z < 6 ? 4 : view.z < 9 ? 5 : view.z < 11 ? 6 : view.z < 12 ? 8 : 9;
      const list = places.filter((p) => p.r <= maxRank && (!p.a || view.z >= 8));
      list.sort((a, b) => a.r - b.r);
      for (const p of list) {
        const px = X(mx(p.x)), py = Y(my(p.y));
        if (px < -40 || px > W + 40 || py < -10 || py > H + 10) continue;
        const name = lang === "he" && p.h ? p.h : p.n;
        if (!name) continue;
        const size = p.r <= 2 ? 12.5 : p.r <= 4 ? 11.5 : 10.5;
        ctx.font = `${p.r <= 3 ? 600 : 400} ${Math.round(size * uiScale())}px ${family}`;
        const label = p.a ? "✈ " + name : name;
        const w = ctx.measureText(label).width + 8, h = size + 4;
        const box: [number, number, number, number] = [px + 4, py - h / 2, px + 4 + w, py + h / 2];
        if (overlaps(box)) continue;
        labelBoxes.push(box);
        if (!p.a) { ctx.beginPath(); ctx.arc(px, py, p.r <= 3 ? 2.6 : 2, 0, Math.PI * 2); ctx.fillStyle = dark ? "#e6edf3" : "#30363d"; ctx.fill(); }
        ctx.textAlign = "left"; ctx.textBaseline = "middle";
        ctx.lineWidth = 3; ctx.strokeStyle = dark ? "rgba(14,22,32,.9)" : "rgba(255,255,255,.92)";
        ctx.strokeText(label, px + 6, py);
        ctx.fillStyle = dark ? "#e6edf3" : "#24292f"; ctx.fillText(label, px + 6, py);
      }
    }
    if (countries && ownNames) {
      ctx.font = `600 ${Math.round(11 * uiScale())}px ${family}`;
      ctx.textAlign = "center"; ctx.textBaseline = "middle";
      const boxes = labelBoxes;
      const list = countries.filter((c) => c.r <= view.z + 2.5 && view.z < 9).sort((a, b) => a.r - b.r);
      for (const c of list) {
        const px = X(mx(c.x)), py = Y(my(c.y));
        if (px < 0 || px > W || py < 0 || py > H) continue;
        const name = lang === "he" && c.h ? c.h : c.n;
        const w = ctx.measureText(name).width + 6, h = 14;
        const box: [number, number, number, number] = [px - w / 2, py - h / 2, px + w / 2, py + h / 2];
        if (boxes.some((b) => !(box[2] < b[0] || box[0] > b[2] || box[3] < b[1] || box[1] > b[3]))) continue;
        boxes.push(box);
        ctx.lineWidth = 3; ctx.strokeStyle = dark ? "rgba(14,22,32,.85)" : "rgba(255,255,255,.85)";
        ctx.strokeText(name, px, py);
        ctx.fillStyle = dark ? "#c9d4e0" : "#4a4f57"; ctx.fillText(name, px, py);
      }
    }

    screen.drawImage(bc, 0, 0, W, H);
    baseRef.current = { key: baseKey, canvas: bc };
    ctx = screen;
    }

    // 4. tracks, with a halo so they read on any map
    plot.signals.forEach((ps) => {
      const t = tracks.find((x) => x.id === ps.sig);
      if (!t) return;
      const pts: [number, number][] = [];
      const path = (i0 = 0, i1 = t.lon.length) => {
        ctx.beginPath();
        let pen = false;
        for (let i = i0; i < i1; i++) {
          const a = t.lon[i], b = t.lat[i] * ps.scale + ps.offset;
          if (!Number.isFinite(a) || !Number.isFinite(b)) { pen = false; continue; }
          const px = X(mx(a)), py = Y(my(b));
          if (i0 === 0 && i1 === t.lon.length && (!pts.length || i === t.lon.length - 1)) pts.push([px, py]);
          if (pen) ctx.lineTo(px, py); else { ctx.moveTo(px, py); pen = true; }
        }
      };
      ctx.lineJoin = "round"; ctx.lineCap = "round";
      // the timeline's mode: the whole track faint for context, the part up to the time (or the last
      // seconds) in full colour
      const span = shownSpan({ playMode, windowSec, cursor });
      const [i0, i1] = span && t.t.length === t.lon.length ? indexSpan(t.t, span) : [0, t.lon.length];
      if (span) {
        path(); ctx.globalAlpha = 0.28; ctx.strokeStyle = ps.color; ctx.lineWidth = ps.width + 0.5; ctx.stroke(); ctx.globalAlpha = 1;
      }
      path(i0, i1); ctx.strokeStyle = dark ? "rgba(0,0,0,.65)" : "rgba(255,255,255,.9)"; ctx.lineWidth = ps.width + 3.5; ctx.stroke();
      path(i0, i1); ctx.strokeStyle = ps.color; ctx.lineWidth = ps.width + 0.5; ctx.stroke();
      const dot = (p: [number, number] | undefined, fill: string) => {
        if (!p) return;
        ctx.beginPath(); ctx.arc(p[0], p[1], 5, 0, Math.PI * 2); ctx.fillStyle = fill; ctx.fill();
        ctx.lineWidth = 2; ctx.strokeStyle = "#ffffff"; ctx.stroke();
      };
      dot(pts[0], "#2da44e"); dot(pts[pts.length - 1], "#e5484d");     // start = green, end = red
    });

    // 5. cursor position(s)
    if (cursor.on && plot.xSignal) {
      const marks: [number, string][] = [[0, "1"]];
      if (cursor.dual) marks.push([1, "2"]);
      for (const [k, tag] of marks) {
        const lon0 = cvals[plot.xSignal]?.[k];
        if (lon0 === null || lon0 === undefined) continue;
        const lon = normLon(new Float64Array([lon0]))[0];
        plot.signals.forEach((ps) => {
          const v = cvals[ps.sig]?.[k];
          if (v === null || v === undefined) return;
          const px = X(mx(lon)), py = Y(my(v * ps.scale + ps.offset));
          ctx.beginPath(); ctx.arc(px, py, 7, 0, Math.PI * 2); ctx.fillStyle = pt.amber; ctx.fill();
          ctx.lineWidth = 2; ctx.strokeStyle = "#ffffff"; ctx.stroke();
          if (cursor.dual) { ctx.font = font; ctx.fillStyle = pt.amberInk; ctx.textAlign = "center"; ctx.textBaseline = "middle"; ctx.fillText(tag, px, py + 0.5); }
        });
      }
    }

    // 5b. objects: the track (as the timeline shows it) and the icon where the object is at the time,
    //     pointing where it heads; outside its own time span it is not shown
    const span5 = shownSpan({ playMode, windowSec, cursor });
    for (const o of objects) {
      const tr = objTracks[o.id];
      if (!tr || !tr.t.length) continue;
      if (o.trail !== false) {
        const [a0, a1] = span5 ? indexSpan(tr.t, span5) : [0, tr.t.length];
        const pathIn = (i0: number, i1: number) => {
          ctx.beginPath();
          let pen = false;
          for (let i = i0; i < i1; i++) {
            const a = tr.lon[i], b = tr.lat[i];
            if (!Number.isFinite(a) || !Number.isFinite(b)) { pen = false; continue; }
            const px = X(mx(a)), py = Y(my(b));
            if (pen) ctx.lineTo(px, py); else { ctx.moveTo(px, py); pen = true; }
          }
        };
        ctx.lineJoin = "round"; ctx.lineCap = "round";
        if (span5) { pathIn(0, tr.t.length); ctx.globalAlpha = 0.28; ctx.strokeStyle = o.color; ctx.lineWidth = 2; ctx.stroke(); ctx.globalAlpha = 1; }
        pathIn(a0, a1); ctx.strokeStyle = dark ? "rgba(0,0,0,.6)" : "rgba(255,255,255,.85)"; ctx.lineWidth = 4.5; ctx.stroke();
        pathIn(a0, a1); ctx.strokeStyle = o.color; ctx.lineWidth = 2; ctx.stroke();
      }
      const tNow = cursor.on && cursor.t1 !== null ? cursor.t1 : tr.t[tr.t.length - 1];
      const st = objectAt(tr, tNow, o.angleUnit);
      if (!st) continue;
      const px = X(mx(st.lon)), py = Y(my(st.lat));
      const sz = (o.size ?? 26) * uiScale();
      drawObjectIcon(ctx, o.kind, px, py, st.heading, sz, o.color, dark);
      ctx.font = `600 ${Math.round(11.5 * uiScale())}px ${family}`;
      ctx.textAlign = "left"; ctx.textBaseline = "middle";
      ctx.lineWidth = 3; ctx.strokeStyle = dark ? "rgba(14,22,32,.9)" : "rgba(255,255,255,.92)";
      ctx.strokeText(o.name, px + sz * 0.6, py - sz * 0.45);
      ctx.fillStyle = dark ? "#e6edf3" : "#24292f"; ctx.fillText(o.name, px + sz * 0.6, py - sz * 0.45);
    }

    // 6. scale bar and attribution (every map provider asks for it)
    const mPerPx = (Math.cos((latOf(view.cy) * Math.PI) / 180) * 40075016.686) / S;
    const nice = [1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000, 100000, 200000, 500000, 1e6, 2e6, 5e6];
    const len = nice.filter((m) => m / mPerPx <= 120).pop() ?? 1;
    const bw = len / mPerPx;
    ctx.font = font; ctx.textAlign = "left"; ctx.textBaseline = "bottom";
    const label = len >= 1000 ? `${len / 1000} km` : `${len} m`;
    const veil = dark ? "rgba(14,22,32,.78)" : "rgba(255,255,255,.82)";
    ctx.fillStyle = veil;
    ctx.fillRect(6, H - 28, Math.max(bw, ctx.measureText(label).width) + 12, 22);
    ctx.strokeStyle = pt.text; ctx.lineWidth = 2;
    ctx.beginPath(); ctx.moveTo(12, H - 14); ctx.lineTo(12, H - 10); ctx.lineTo(12 + bw, H - 10); ctx.lineTo(12 + bw, H - 14); ctx.stroke();
    ctx.fillStyle = pt.text; ctx.fillText(label, 12, H - 13);
    const att = ATTRIB[base] ?? "";
    ctx.font = `${Math.round(9.5 * uiScale())}px ${family}`;
    ctx.textAlign = "right";
    const aw = ctx.measureText(att).width;
    ctx.fillStyle = veil;
    ctx.fillRect(W - aw - 10, H - 16, aw + 10, 16);
    ctx.fillStyle = dark ? "#9fb0c3" : "#3d4650"; ctx.fillText(att, W - 5, H - 3);
  }, [tracks, view, size.w, size.h, theme, scale, cursor, cvals, plot.signals, plot.xSignal, countries, places, base, tick, lang, playMode, windowSec, objTracks, objects]);

  /* ------------------------- zoom / pan / readout ------------------------ */
  const viewRef = useRef(view);
  viewRef.current = view;
  useEffect(() => {
    const cv = cvRef.current;
    if (!cv) return;
    const at = (e: { clientX: number; clientY: number }, v: View) => {
      const b = cv.getBoundingClientRect(), S = 256 * 2 ** v.z;
      const bx = e.clientX - b.left - b.width / 2, by = e.clientY - b.top - b.height / 2;
      return { wx: v.cx + bx / S, wy: v.cy + by / S, bx, by };
    };
    const onWheel = (e: WheelEvent) => {
      const v = viewRef.current;
      if (!v) return;
      e.preventDefault();
      const g = at(e, v);
      const z = Math.max(1, Math.min(22, v.z + (e.deltaY < 0 ? 0.35 : -0.35)));
      const S = 256 * 2 ** z;
      userView.current = true;
      setView({ z, cx: g.wx - g.bx / S, cy: Math.max(0, Math.min(1, g.wy - g.by / S)) });   // keep the point under the pointer
    };
    const onDown = (e: MouseEvent) => {
      actions.setActivePlot(index);
      const v = viewRef.current;
      if (!v || e.button > 1) return;
      e.preventDefault();
      const x0 = e.clientX, y0 = e.clientY, S = 256 * 2 ** v.z;
      cv.style.cursor = "grabbing";
      const move = (ev: MouseEvent) => {
        userView.current = true;
        setView({ z: v.z, cx: v.cx - (ev.clientX - x0) / S, cy: Math.max(0, Math.min(1, v.cy - (ev.clientY - y0) / S)) });
      };
      const up = () => { cv.style.cursor = "grab"; window.removeEventListener("mousemove", move); window.removeEventListener("mouseup", up); };
      window.addEventListener("mousemove", move); window.addEventListener("mouseup", up);
    };
    const onMove = (e: MouseEvent) => { const v = viewRef.current; if (v) { const g = at(e, v); setMouse({ lon: lonOf(g.wx), lat: latOf(g.wy) }); } };
    const onLeave = () => setMouse(null);
    const onDbl = () => { userView.current = false; setView(fitView(allTracksRef.current(), size.w, size.h)); };
    cv.addEventListener("wheel", onWheel, { passive: false });
    cv.addEventListener("mousedown", onDown);
    cv.addEventListener("mousemove", onMove);
    cv.addEventListener("mouseleave", onLeave);
    cv.addEventListener("dblclick", onDbl);
    return () => {
      cv.removeEventListener("wheel", onWheel); cv.removeEventListener("mousedown", onDown);
      cv.removeEventListener("mousemove", onMove); cv.removeEventListener("mouseleave", onLeave);
      cv.removeEventListener("dblclick", onDbl);
    };
  }, [index, tracks, size.w, size.h]);

  const prec = view ? Math.max(1, Math.min(8, Math.round(view.z * 0.3 + 1))) : 2;
  return (
    <div className="plot-canvas geo" ref={wrapRef} style={{ position: "relative" }}>
      <canvas ref={cvRef} style={{ width: size.w, height: size.h, display: "block", cursor: "grab" }} />
      {mouse && <div className="geo-readout">{mouse.lat.toFixed(prec)}°, {mouse.lon.toFixed(prec)}°</div>}
      {(!plot.xSignal || !ys.length) && !objects.length && <div className="plot-empty">{emptyText}</div>}
      {badRange && <div className="plot-empty">{notDegrees}</div>}
    </div>
  );
}
