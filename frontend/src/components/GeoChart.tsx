import { countRender } from "../perf";
import { runsDataKey } from "../values";
import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api";
import { actions, activeTab, shownSpan, useApp, type MapObject, type Plot } from "../store";
import { useMapBase } from "../mapBase";
import { drawObjectIcon } from "./mapIcons";
import { altAt, angleUnitOf, colorRuns, fmtDistance as fmtDistanceShort, derivedAttitude, objectAt, trackColors, trackKey, trackRequest, trackTime, type ObjTrack, type TrackColors } from "../mapObjects";
import TrackKeys from "./TrackKeys";
import RelationPanel, { RingIcon } from "./RelationPanel";
import { pairOf, relation } from "../relation";
import { labelsOf, stateColor } from "../values";
import { fmtNum, useT } from "../i18n";
import { getPrefValue, setPref } from "../prefs";
import type { Country } from "../worldCountries";
import { dpr, indexSpan, ink, PLOT_THEME, uiScale, useSize, wheelZoom } from "./chartUtil";

interface Props { plot: Plot; index: number; onLoading: (b: boolean) => void; emptyText: string; notDegrees: string }

interface Track { id: string; lon: Float64Array; lat: Float64Array; t: Float64Array }
/** cx, cy: map centre in Web-Mercator world units (0..1); z: zoom (256 * 2^z pixels across the world). */
interface View { cx: number; cy: number; z: number }

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

const HINT_PREF = "mapHintSeen";
const reducedMotion = () => { try { return window.matchMedia("(prefers-reduced-motion: reduce)").matches; } catch { return false; } };

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
  countRender("GeoChart");
  const t = useT();
  const theme = useApp((s) => s.theme);
  const lang = useApp((s) => s.lang);
  const scale = useApp((s) => s.uiScale);
  const runs = useApp((s) => s.runs);
  const dataVersion = useApp((s) => s.dataVersion);
  // N6: the time is read when drawing (useApp.getState) - the map moves its objects without a React
  // render per frame of playback
  const cursorOn = useApp((s) => s.cursor.on);
  // U6: the time under the pointer over a time plot of this tab - a ghost of each object there
  const pointerT = useApp((s) => (s.pointer && activeTab(s.ws).plots.some((p) => p.id === s.pointer!.plotId) ? s.pointer.t : null));
  const streaming = useApp((s) => s.streaming);
  const cvals = useApp((s) => s.cvals);
  const playMode = useApp((s) => s.playMode);
  const windowSec = useApp((s) => s.windowSec);
  // O1: automatic = the offline map (nothing leaves the PC); an online layer only when chosen, and
  // never with "Never use the network" (1.22.0 had made automatic OpenStreetMap)
  const base = useMapBase();
  // country borders (and names) drawn over the maps whose tiles have none: the offline map and the
  // satellite photos (owner's request, 2026-11-04); the street maps draw their own
  const borders = useApp((s) => s.geoBorders);
  const wrapRef = useRef<HTMLDivElement>(null);
  const cvRef = useRef<HTMLCanvasElement>(null);
  const size = useSize(wrapRef);
  const [tracks, setTracks] = useState<Track[]>([]);
  const [view, setView] = useState<View | null>(null);
  const baseRef = useRef<{ hard: string; tick: number; view: View; canvas: HTMLCanvasElement } | null>(null);
  /* objects: each one's signals on one time axis, fetched when its signals change */
  const objects: MapObject[] = useMemo(() => plot.objects ?? [], [plot.objects]);
  const [objTracks, setObjTracks] = useState<Record<string, ObjTrack>>({});
  const objTracksRef = useRef(objTracks);
  objTracksRef.current = objTracks;
  const objKey = objects.map((o) => trackKey(o, objects)).join("|");
  const [countries, setCountries] = useState<Country[] | null>(null);
  const [places, setPlaces] = useState<Place[] | null>(null);
  const [tick, setTick] = useState(0);
  const userView = useRef(false);               // the user zoomed / panned: stop auto-fitting
  const [mouse, setMouse] = useState<{ lon: number; lat: number } | null>(null);
  /** L7: what the ring under the mouse means (solid: the reference, dashed: compared with it) */
  const [ringTip, setRingTip] = useState<{ kind: "primary" | "secondary" | "none"; name: string; x: number; y: number } | null>(null);

  const ys = plot.signals.map((s) => s.sig);
  const yKey = ys.join("|");
  const runsKey = runsDataKey(runs);

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
          const r = await api.objectTrack(trackRequest(o, plot.objects ?? []));
          out[o.id] = { t: r.t, lat: r.lat, lon: normLon(r.lon), yaw: r.yaw, course: r.course, units: r.units, color: r.color, alt: r.alt };
        } catch { /* a signal no longer open: the object is skipped */ }
      }
      if (!cancelled) setObjTracks(out);
    })();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [objKey, dataVersion, runsKey]);
  /* each object's track colours (by a state or a value) and their key */
  const objColors = useMemo(() => {
    const out: Record<string, TrackColors> = {};
    for (const o of objects) {
      const tr = objTracks[o.id];
      if (!tr?.color || !o.trackColor || o.trackColor === "object" || !o.colorSig) continue;
      const c = trackColors(o.trackColor, tr.color, labelsOf(runs, o.colorSig) ?? null, (x) => fmtNum(x, lang, 4), (x) => stateColor(x, theme));
      if (c) out[o.id] = c;
    }
    return out;
  }, [objects, objTracks, runs, lang, theme]);
  /** Tracks and objects, for fitting the view. */
  const allTracks = (): Track[] => [...tracks, ...Object.entries(objTracks).map(([id, o]) => ({ id, lon: o.lon, lat: o.lat, t: o.t }))];
  const allTracksRef = useRef(allTracks);
  allTracksRef.current = allTracks;

  /* fit to the track whenever data arrives, until the user moves the map */
  useEffect(() => {
    if (size.w < 50 || size.h < 50) return;
    if (userView.current && view) return;
    setView(fitView(allTracks(), size.w, size.h));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tracks, objTracks, size.w, size.h]);

  /* following an object: the map keeps it in the middle as the time moves (zoom stays the user's);
     N6: a drag while following moves the map around the object (followOff, in world units) instead of
     fighting the user - "Back to following" puts it in the middle again */
  const followOff = useRef<{ x: number; y: number } | null>(null);
  const [offFollow, setOffFollow] = useState(false);
  const followTarget = (): { cx: number; cy: number } | null => {
    const id = plot.followObject;
    const tr = id ? objTracksRef.current[id] : null;
    const c = useApp.getState().cursor;
    if (!tr || !c.on || c.t1 === null) return null;
    const o = objects.find((x) => x.id === id);
    const st = objectAt(tr, trackTime(tr, c.t1, streaming), o ? angleUnitOf(o, objects) : undefined);
    if (!st) return null;
    const off = followOff.current;
    const goal = { cx: mx(st.lon) + (off?.x ?? 0), cy: my(st.lat) + (off?.y ?? 0) };
    // N6: while playing, ease after it (a noisy position does not shake the map); else right on it
    const app = useApp.getState(), now = performance.now(), last = eased.current;
    if (app.smoothFollow && app.playing && last && last.id === id && now - last.t < 250) {
      const a = 1 - Math.exp(-(now - last.t) / 120);
      goal.cx = last.cx + (goal.cx - last.cx) * a; goal.cy = last.cy + (goal.cy - last.cy) * a;
    }
    eased.current = { id: id!, t: now, cx: goal.cx, cy: goal.cy };
    return goal;
  };
  const eased = useRef<{ id: string; t: number; cx: number; cy: number } | null>(null);
  const followRef = useRef(followTarget);
  followRef.current = followTarget;
  useEffect(() => { followOff.current = null; setOffFollow(false); }, [plot.followObject]);
  useEffect(() => {
    const g = followRef.current();
    if (!g) return;
    userView.current = true;
    setView((v) => (v ? { ...v, cx: g.cx, cy: g.cy } : v));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [plot.followObject, objTracks, cursorOn, streaming]);
  useEffect(() => { userView.current = false; }, [plot.xSignal, yKey]);

  const badRange = tracks.some((t) => {
    let bad = 0, n = 0;
    for (let i = 0; i < t.lat.length; i += Math.max(1, Math.floor(t.lat.length / 500))) { n++; if (Math.abs(t.lat[i]) > 90 || Math.abs(t.lon[i]) > 360) bad++; }
    return n > 0 && bad / n > 0.5;
  });

  /* ------------------------------ drawing ------------------------------ */
  const drawRef = useRef<() => void>(() => {});
  const objAt = useRef(new Map<string, { px: number; py: number; lat: number; lon: number; alt: number | null; sz: number }>());   // N7: where each icon was drawn (a click picks one)
  const rotRef = useRef(0);                       // Track up: degrees the map is turned (0 = north up)
  const topRef = useRef<HTMLCanvasElement>(null);
  const northRef = useRef<HTMLSpanElement>(null);
  const upEased = useRef<{ t: number; h: number } | null>(null);
  /** Track up: the heading of the followed object (else the primary, else the first) at the time - eased
   *  while playing when following is smooth; the last one is kept while it has none. */
  const upHeading = (): number => {
    const id = plot.followObject ?? (plot.primaryObject && objects.some((o) => o.id === plot.primaryObject) ? plot.primaryObject : objects[0]?.id);
    const tr = id ? objTracksRef.current[id] : undefined;
    const app = useApp.getState(), c = app.cursor;
    const o = objects.find((x) => x.id === id);
    const st = tr && o ? objectAt(tr, trackTime(tr, c.on ? c.t1 : null, streaming), angleUnitOf(o, objects)) : null;
    const last = upEased.current, now = performance.now();
    let h = st?.heading ?? last?.h ?? 0;
    if (st?.heading != null && last && app.smoothFollow && app.playing && now - last.t < 250) {
      const d = ((h - last.h + 540) % 360) - 180;
      h = last.h + d * (1 - Math.exp(-(now - last.t) / 200));
    }
    upEased.current = { t: now, h: ((h % 360) + 360) % 360 };
    return upEased.current.h;
  };
  const lastMove = useRef(0);                     // when the view last changed (pan / zoom): reuse the base meanwhile
  const drawnView = useRef<View | null>(null);
  const settleTimer = useRef(0);
  useEffect(() => {
   const draw = () => {
    const cv = cvRef.current;
    if (!cv || size.w < 50 || size.h < 50) return;
    const cursor = useApp.getState().cursor;
    // N6: Track up - the canvas is a square as wide as the view's diagonal, turned (CSS) so the heading
    // points up: turning it costs nothing per frame, and the map drawn on it is the same as north up
    const up = plot.mapUp === "track";
    const r = dpr(), W = up ? Math.ceil(Math.hypot(size.w, size.h)) : size.w, H = up ? W : size.h;
    const ang = up ? upHeading() : 0;
    rotRef.current = ang;
    cv.style.transform = up ? `rotate(${-ang}deg)` : "";
    if (northRef.current) northRef.current.style.transform = `rotate(${-ang}deg)`;
    // resizing a canvas clears and reallocates it: only when its size changes (it was every frame)
    if (cv.width !== Math.round(W * r) || cv.height !== Math.round(H * r)) { cv.width = Math.round(W * r); cv.height = Math.round(H * r); }
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

    // The base layer - tiles, borders, names - changes only with the view, size, theme, language or
    // newly arrived tiles. It is kept in a canvas of its own: during playback only the tracks and
    // objects are drawn again over a copy of it (a full redraw per frame held playback to ~36 fps).
    // N6: it is drawn with a margin around the screen, and while the map is dragged or zoomed (or a
    // tile arrives meanwhile) the one already drawn is moved / scaled instead of drawn again - every
    // move of a drag redrew every tile (p95 117 ms a frame on the copter log); it is drawn again when
    // the movement pauses
    const M = Math.round(Math.max(W, H) * 0.25);
    const hardKey = [W, H, r, theme, base, lang, !!countries, !!places, uiScale(), borders].join("|");
    const prevView = drawnView.current;
    if (!prevView || prevView.cx !== view.cx || prevView.cy !== view.cy || prevView.z !== view.z) lastMove.current = performance.now();
    drawnView.current = view;
    const B = baseRef.current;
    let reused = false;
    if (B && B.hard === hardKey) {
      const k = 2 ** (view.z - B.view.z);
      const ox = W / 2 + (B.view.cx - view.cx) * S - (W / 2 + M) * k, oy = H / 2 + (B.view.cy - view.cy) * S - (H / 2 + M) * k;
      const same = B.view.cx === view.cx && B.view.cy === view.cy && B.view.z === view.z && B.tick === tick;
      const covers = ox <= 0.5 && oy <= 0.5 && ox + (W + 2 * M) * k >= W - 0.5 && oy + (H + 2 * M) * k >= H - 0.5;
      const moving = performance.now() - lastMove.current < 180;
      if (same || (covers && moving && k > 0.49 && k < 2.01)) {
        screen.drawImage(B.canvas, ox, oy, (W + 2 * M) * k, (H + 2 * M) * k);
        reused = true;
        if (!same) {                                   // draw it properly once the movement pauses
          window.clearTimeout(settleTimer.current);
          settleTimer.current = window.setTimeout(() => drawRef.current(), 200);
        }
      }
    }
    if (!reused) ((W: number, H: number) => {
    const X = (wx: number) => W / 2 + (wx - view.cx) * S;
    const Y = (wy: number) => H / 2 + (wy - view.cy) * S;
    const wx0 = view.cx - W / 2 / S, wx1 = view.cx + W / 2 / S, wy0 = view.cy - H / 2 / S, wy1 = view.cy + H / 2 / S;
    const bc = document.createElement("canvas");
    bc.width = Math.round(W * r); bc.height = Math.round(H * r);
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

    // 3. what the offline map's tiles and the satellite photos do not carry: borders, and names
    //    (drawn here: crisp, in the UI language). A halo under each border so it reads on any land,
    //    and dashed, so it is not taken for a road.
    const ownLayer = borders && (base === "offline" || base === "satellite");
    const ownNames = ownLayer || offlineUsed > 0 || tilesShown < tilesWanted / 2;
    const onDark = dark || base === "satellite";                 // names and borders light on a photo
    if (countries && (ownLayer || offlineUsed > 0)) {
      const z = view.z, w = z < 3 ? 0.8 : z < 4 ? 1.1 : z < 7 ? 1.5 : 2;
      const path = (c: Country) => {
        let any = false;
        ctx.beginPath();
        for (const poly of c.p) {
          let minx = Infinity, maxx = -Infinity, miny = Infinity, maxy = -Infinity;
          for (let i = 0; i < poly.length; i += 2) {
            const px = X(mx(poly[i] / 100)), py = Y(my(poly[i + 1] / 100));
            if (px < minx) minx = px; if (px > maxx) maxx = px; if (py < miny) miny = py; if (py > maxy) maxy = py;
            if (i === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
          }
          ctx.closePath();
          if (!(maxx < 0 || minx > W || maxy < 0 || miny > H)) any = true;
        }
        return any;
      };
      for (const c of countries) {
        if (!path(c)) continue;
        if (z >= 3) {                                            // the whole world: no halo (too busy)
          ctx.setLineDash([]); ctx.lineWidth = w + 2.2;
          ctx.strokeStyle = onDark ? "rgba(0,0,0,.45)" : "rgba(255,255,255,.75)"; ctx.stroke();
        }
        ctx.setLineDash([7, 3]); ctx.lineWidth = w;
        ctx.strokeStyle = base === "satellite" ? "rgba(255,226,140,.95)" : onDark ? "rgba(214,196,245,.9)" : "rgba(118,62,160,.9)";
        ctx.stroke();
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
        if (!p.a) { ctx.beginPath(); ctx.arc(px, py, p.r <= 3 ? 2.6 : 2, 0, Math.PI * 2); ctx.fillStyle = onDark ? "#e6edf3" : "#30363d"; ctx.fill(); }
        ctx.textAlign = "left"; ctx.textBaseline = "middle";
        ctx.lineWidth = 3; ctx.strokeStyle = onDark ? "rgba(14,22,32,.9)" : "rgba(255,255,255,.92)";
        ctx.strokeText(label, px + 6, py);
        ctx.fillStyle = onDark ? "#e6edf3" : "#24292f"; ctx.fillText(label, px + 6, py);
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
        ctx.lineWidth = 3; ctx.strokeStyle = onDark ? "rgba(14,22,32,.85)" : "rgba(255,255,255,.85)";
        ctx.strokeText(name, px, py);
        ctx.fillStyle = onDark ? "#c9d4e0" : "#4a4f57"; ctx.fillText(name, px, py);
      }
    }

    screen.drawImage(bc, -M, -M, W, H);
    baseRef.current = { hard: hardKey, tick, view, canvas: bc };
    })(W + 2 * M, H + 2 * M);
    ctx = screen;

    // 4. tracks, with a halo so they read on any map
    plot.signals.forEach((ps0) => {
      const t = tracks.find((x) => x.id === ps0.sig);
      if (!t) return;
      // the same position as an object: one colour for both (the object's), not two unrelated ones
      const twin = objects.find((o) => o.lat === ps0.sig && o.lon === plot.xSignal);
      const ps = twin ? { ...ps0, color: twin.color } : ps0;
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
        path(); ctx.globalAlpha = 0.28; ctx.strokeStyle = ink(ps.color, theme); ctx.lineWidth = ps.width + 0.5; ctx.stroke(); ctx.globalAlpha = 1;
      }
      path(i0, i1); ctx.strokeStyle = dark ? "rgba(0,0,0,.65)" : "rgba(255,255,255,.9)"; ctx.lineWidth = ps.width + 3.5; ctx.stroke();
      path(i0, i1); ctx.strokeStyle = ink(ps.color, theme); ctx.lineWidth = ps.width + 0.5; ctx.stroke();
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
    const at5 = new Map<string, { px: number; py: number; lat: number; lon: number; alt: number | null; sz: number }>();
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
        const cols = objColors[o.id];
        // a coloured track: each stretch of one colour drawn on its own
        // N5: a receiver's fixes as points, a navigation solution dashed (o.track; default a line)
        const dots = (i0: number, i1: number, r: number, color: (i: number) => string | null) => {
          const step = Math.max(1, Math.ceil((i1 - i0) / 4000));
          for (let i = i0; i < i1; i += step) {
            const a = tr.lon[i], b = tr.lat[i], c = color(i);
            if (!c || !Number.isFinite(a) || !Number.isFinite(b)) continue;
            ctx.beginPath(); ctx.arc(X(mx(a)), Y(my(b)), r, 0, Math.PI * 2); ctx.fillStyle = c; ctx.fill();
          }
        };
        const dash = o.track === "dash" ? [7, 5] : [];
        const stroke = (i0: number, i1: number, w: number) => {
          if (o.track === "points") { dots(i0, i1, w * 0.9, (i) => (cols ? cols.at[i] : o.color)); return; }
          ctx.setLineDash(dash);
          if (!cols) { pathIn(i0, i1); ctx.strokeStyle = o.color; ctx.lineWidth = w; ctx.stroke(); }
          else for (const r of colorRuns(cols.at, i0, i1)) { pathIn(r.a, r.b); ctx.strokeStyle = r.color; ctx.lineWidth = w; ctx.stroke(); }
          ctx.setLineDash([]);
        };
        if (span5) { ctx.globalAlpha = 0.28; stroke(0, tr.t.length, 2); ctx.globalAlpha = 1; }
        if (o.track === "points") dots(a0, a1, 3.2, () => (dark ? "rgba(0,0,0,.6)" : "rgba(255,255,255,.85)"));
        else { ctx.setLineDash(dash); pathIn(a0, a1); ctx.strokeStyle = dark ? "rgba(0,0,0,.6)" : "rgba(255,255,255,.85)"; ctx.lineWidth = cols ? 5.5 : 4.5; ctx.stroke(); ctx.setLineDash([]); }
        stroke(a0, a1, cols ? 3 : 2);
      }
      const tNow = trackTime(tr, cursor.on ? cursor.t1 : null, streaming);
      const sz = (o.size ?? 26) * uiScale();
      const ghost = pointerT !== null && Math.abs(pointerT - tNow) > 1e-9 ? objectAt(tr, pointerT, angleUnitOf(o, objects)) : null;
      if (ghost) {                    // where it was at the moment under the pointer: faint, no name
        ctx.save(); ctx.globalAlpha = 0.45;
        drawObjectIcon(ctx, o.kind, X(mx(ghost.lon)), Y(my(ghost.lat)), ghost.heading, sz * 0.9, o.color, dark, derivedAttitude(o, objects));
        ctx.restore();
      }
      const st = objectAt(tr, tNow, angleUnitOf(o, objects));
      if (!st) continue;
      const px = X(mx(st.lon)), py = Y(my(st.lat));
      at5.set(o.id, { px, py, lat: st.lat, lon: st.lon, alt: altAt(tr, tNow), sz });
      drawObjectIcon(ctx, o.kind, px, py, st.heading, sz, o.color, dark, derivedAttitude(o, objects));
      ctx.font = `600 ${Math.round(11.5 * uiScale())}px ${family}`;
      ctx.textAlign = "left"; ctx.textBaseline = "middle";
      ctx.lineWidth = 3; ctx.strokeStyle = dark ? "rgba(14,22,32,.9)" : "rgba(255,255,255,.92)";
      ctx.strokeText(o.name, px + sz * 0.6, py - sz * 0.45);
      ctx.fillStyle = dark ? "#e6edf3" : "#24292f"; ctx.fillText(o.name, px + sz * 0.6, py - sz * 0.45);
    }
    // N7: the primary (a ring) and the secondary (a dashed ring), and a line between them with the range
    // (or from the primary to every object, or none - plot.relLines)
    const pair = pairOf(plot);
    const P5 = pair.primary ? at5.get(pair.primary) : undefined;
    if (P5 && plot.relLines !== "off") {
      const to = plot.relLines === "all" ? objects.filter((o) => o.id !== pair.primary).map((o) => o.id) : pair.secondary ? [pair.secondary] : [];
      ctx.font = `600 ${Math.round(11 * uiScale())}px ${family}`;
      for (const id of to) {
        const q = at5.get(id);
        if (!q) continue;
        ctx.setLineDash([6, 4]); ctx.lineWidth = 1.6; ctx.strokeStyle = dark ? "rgba(230,237,243,.8)" : "rgba(36,41,47,.75)";
        ctx.beginPath(); ctx.moveTo(P5.px, P5.py); ctx.lineTo(q.px, q.py); ctx.stroke(); ctx.setLineDash([]);
        const rr = relation({ lat: P5.lat, lon: P5.lon, alt: P5.alt, hdg: null }, { lat: q.lat, lon: q.lon, alt: q.alt, hdg: null });
        const txt = fmtDistanceShort(rr.slant ?? rr.horiz, lang);
        const mxp = (P5.px + q.px) / 2, myp = (P5.py + q.py) / 2;
        ctx.textAlign = "center"; ctx.textBaseline = "middle";
        ctx.lineWidth = 3; ctx.strokeStyle = dark ? "rgba(14,22,32,.9)" : "rgba(255,255,255,.92)"; ctx.strokeText(txt, mxp, myp);
        ctx.fillStyle = dark ? "#e6edf3" : "#24292f"; ctx.fillText(txt, mxp, myp);
      }
    }
    for (const [id, dashed] of [[pair.primary, false], [pair.secondary, true]] as const) {
      const q = id ? at5.get(id) : undefined;
      if (!q) continue;
      ctx.setLineDash(dashed ? [4, 3] : []); ctx.lineWidth = 2; ctx.strokeStyle = pt.amber;
      ctx.beginPath(); ctx.arc(q.px, q.py, q.sz * 0.72, 0, Math.PI * 2); ctx.stroke(); ctx.setLineDash([]);
    }
    objAt.current = at5;

    // 6. scale bar and attribution (every map provider asks for it) - on a layer of their own over a turned map
    const top = topRef.current;
    if (up && top) {
      const tw = Math.round(size.w * r), th = Math.round(size.h * r);
      if (top.width !== tw || top.height !== th) { top.width = tw; top.height = th; }
      ctx = top.getContext("2d")!;
      ctx.setTransform(r, 0, 0, r, 0, 0);
      ctx.clearRect(0, 0, size.w, size.h);
    }
    ((W: number, H: number) => {
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
    })(up ? size.w : W, up ? size.h : H);
   };
   drawRef.current = draw;
   draw();
  }, [tracks, view, size.w, size.h, plot.mapUp, plot.followObject, plot.primaryObject, plot.relatedObjects, plot.relLines, theme, scale, cvals, plot.signals, plot.xSignal, countries, places, base, tick, lang, playMode, windowSec, objTracks, objects, streaming, objColors, borders, pointerT]);
  // the time moves: follow the object (a new view, drawn by the effect above) or just draw again
  useEffect(() => useApp.subscribe((st, prev) => {
    if (st.cursor === prev.cursor) return;
    const g = followRef.current();
    if (g) { userView.current = true; setView((v) => (v ? { ...v, cx: g.cx, cy: g.cy } : v)); }
    else drawRef.current();
  }), []);

  /* ------------------------- zoom / pan / readout ------------------------ */
  /* N6 (Tacview-like): the map follows the pointer at once while dragged, glides a little after a
     quick drag, zooms smoothly (animated, around the pointer) by the wheel, the + / − buttons and the
     keys; a drag while following moves the map around the followed object. No glide or animation
     when the system asks for reduced motion. */
  const viewRef = useRef(view);
  viewRef.current = view;
  const anim = useRef(0);
  const zoomGoal = useRef<View | null>(null);
  const stopAnim = () => { cancelAnimationFrame(anim.current); anim.current = 0; zoomGoal.current = null; };
  useEffect(() => () => cancelAnimationFrame(anim.current), []);
  /** Move the view to `to` over `ms` (at once when reduced motion is asked for). */
  const animateTo = (to: View, ms = 140) => {
    const from = viewRef.current;
    cancelAnimationFrame(anim.current);
    userView.current = true;
    if (!from || reducedMotion() || ms <= 0) { zoomGoal.current = null; setView(to); return; }
    zoomGoal.current = to;
    const t0 = performance.now();
    const step = (now: number) => {
      const f = Math.min(1, (now - t0) / ms), e = 1 - (1 - f) ** 3;          // ease out
      setView({ z: from.z + (to.z - from.z) * e, cx: from.cx + (to.cx - from.cx) * e, cy: from.cy + (to.cy - from.cy) * e });
      if (f < 1) anim.current = requestAnimationFrame(step); else { anim.current = 0; zoomGoal.current = null; }
    };
    anim.current = requestAnimationFrame(step);
  };
  /** Zoom by `dz` keeping the world point under (bx, by) - pixels from the map's middle - where it is. */
  const zoomBy = (dz: number, bx = 0, by = 0) => {
    const v = zoomGoal.current ?? viewRef.current;
    if (!v) return;
    const S0 = 256 * 2 ** v.z, wx = v.cx + bx / S0, wy = v.cy + by / S0;
    const z = Math.max(1, Math.min(22, v.z + dz)), S = 256 * 2 ** z;
    const to = { z, cx: wx - bx / S, cy: Math.max(0, Math.min(1, wy - by / S)) };
    if (plot.followObject && followOff.current === null) { to.cx = v.cx; to.cy = v.cy; }   // following: around the object
    animateTo(to);
  };
  /** Pan by (dx, dy) pixels; while following, the offset from the object changes instead. */
  /** A screen offset (px) in the map's own (turned) frame - Track up turns the canvas by -rot. */
  const toCanvas = (x: number, y: number) => {
    const a = (rotRef.current * Math.PI) / 180, c = Math.cos(a), sn = Math.sin(a);
    return { bx: x * c - y * sn, by: x * sn + y * c };
  };
  const panBy = (sx: number, sy: number) => {
    const v = viewRef.current;
    if (!v) return;
    const { bx: dx, by: dy } = toCanvas(sx, sy);
    const S = 256 * 2 ** v.z;
    userView.current = true;
    if (plot.followObject) {
      const o = followOff.current ?? { x: 0, y: 0 };
      followOff.current = { x: o.x - dx / S, y: o.y - dy / S };
      setOffFollow(true);
    }
    setView({ z: v.z, cx: v.cx - dx / S, cy: Math.max(0, Math.min(1, v.cy - dy / S)) });
  };
  const fitAll = () => { stopAnim(); userView.current = false; const f = fitView(allTracksRef.current(), size.w, size.h); if (f) animateTo(f, 220); };
  const panRef = useRef(panBy); panRef.current = panBy;
  const zoomRef = useRef(zoomBy); zoomRef.current = zoomBy;
  const fitRef = useRef(fitAll); fitRef.current = fitAll;
  useEffect(() => {
    const cv = cvRef.current;
    if (!cv) return;
    const rel = (e: { clientX: number; clientY: number }) => {
      const b = (rotRef.current && wrapRef.current ? wrapRef.current : cv).getBoundingClientRect();   // Track up: the canvas is bigger and turned
      return toCanvas(e.clientX - b.left - b.width / 2, e.clientY - b.top - b.height / 2);
    };
    const at = (e: { clientX: number; clientY: number }, v: View) => {
      const { bx, by } = rel(e), S = 256 * 2 ** v.z;
      return { wx: v.cx + bx / S, wy: v.cy + by / S };
    };
    const onWheel = (e: WheelEvent) => {
      if (!viewRef.current) return;
      e.preventDefault();
      const f = wheelZoom(e);                 // F27: in proportion to the step (a trackpad sends many small ones)
      if (f === null) return;
      const { bx, by } = rel(e);
      zoomRef.current(-Math.log2(f) * 1.09, bx, by);                    // a mouse notch: 0.35, as before
      markHintSeen();
    };
    const onDown = (e: MouseEvent) => {
      actions.setActivePlot(index);
      if (!viewRef.current || e.button > 1) return;
      e.preventDefault();
      stopAnim();
      wrapRef.current?.focus({ preventScroll: true });
      let lx = e.clientX, ly = e.clientY;
      const trail: [number, number, number][] = [[performance.now(), lx, ly]];
      cv.style.cursor = "grabbing";
      const move = (ev: MouseEvent) => {
        panRef.current(ev.clientX - lx, ev.clientY - ly);
        lx = ev.clientX; ly = ev.clientY;
        trail.push([performance.now(), lx, ly]);
        if (trail.length > 8) trail.shift();
      };
      const x0 = e.clientX, y0 = e.clientY, shift = e.shiftKey;
      const up = () => {
        cv.style.cursor = "grab"; window.removeEventListener("mousemove", move); window.removeEventListener("mouseup", up);
        // N7: a click (no drag) on an object makes it the primary; with Shift the secondary
        if (Math.hypot(lx - x0, ly - y0) < 4) { pickRef.current(x0, y0, shift); return; }
        // a quick drag glides on, slowing down (px / ms from the last ~80 ms of the drag)
        const now = performance.now(), old = trail.find(([tt]) => now - tt <= 80) ?? trail[trail.length - 1];
        const dt = now - old[0];
        let vx = dt > 0 ? (lx - old[1]) / dt : 0, vy = dt > 0 ? (ly - old[2]) / dt : 0;
        if (reducedMotion() || Math.hypot(vx, vy) < 0.3 || now - trail[trail.length - 1][0] > 60) return;
        let last = now;
        const glide = (tt: number) => {
          const d = tt - last; last = tt;
          panRef.current(vx * d, vy * d);
          const k = Math.exp(-d / 260); vx *= k; vy *= k;
          anim.current = Math.hypot(vx, vy) > 0.02 ? requestAnimationFrame(glide) : 0;
        };
        anim.current = requestAnimationFrame(glide);
        markHintSeen();
      };
      window.addEventListener("mousemove", move); window.addEventListener("mouseup", up);
    };
    const onMove = (e: MouseEvent) => { const v = viewRef.current; if (v) { const g = at(e, v); setMouse({ lon: lonOf(g.wx), lat: latOf(g.wy) }); } hoverRef.current(e); };
    const onLeave = () => { setMouse(null); setRingTip(null); };
    const onDbl = () => fitRef.current();
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [index, tracks, size.w, size.h]);

  /** N7: the object under a click (screen point), made the primary - or with Shift the secondary. */
  const pick = (cx: number, cy: number, secondary: boolean) => {
    const best = objUnder(cx, cy);           // the canvas's own pixels: the click turned back (Track up)
    if (!best) return;
    const cur = pairOf(plot);
    if (secondary) { if (best !== cur.primary) actions.setObjectPair(plot.id, cur.primary, best); }
    else if (best !== cur.primary) actions.setObjectPair(plot.id, best, best === cur.secondary ? cur.primary : cur.secondary);
  };
  const pickRef = useRef(pick); pickRef.current = pick;
  /** The object under a screen point (the one an icon click picks), or null. */
  const objUnder = (cx: number, cy: number): string | null => {
    const cv = cvRef.current;
    if (!cv) return null;
    const b = cv.getBoundingClientRect();
    const { bx, by } = toCanvas(cx - b.left - b.width / 2, cy - b.top - b.height / 2);
    const w = cv.clientWidth, h = cv.clientHeight;
    let best: string | null = null, dmin = Infinity;
    for (const [id, q] of objAt.current) {
      const d = Math.hypot(q.px - (w / 2 + bx), q.py - (h / 2 + by));
      if (d < q.sz * 0.75 && d < dmin) { dmin = d; best = id; }
    }
    return best;
  };
  /** L7: hovering an object of a pair says what its ring means (a tooltip that follows the mouse). */
  const hover = (e: MouseEvent) => {
    const id = objects.length > 1 ? objUnder(e.clientX, e.clientY) : null;
    const wb = wrapRef.current?.getBoundingClientRect();
    const o = id ? objects.find((x) => x.id === id) : undefined;
    if (!o || !wb) { setRingTip(null); return; }
    const pr = pairOf(plot);
    const kind = o.id === pr.primary ? "primary" : o.id === pr.secondary ? "secondary" : "none";
    const x = e.clientX - wb.left, y = e.clientY - wb.top;
    setRingTip((p) => (p && p.kind === kind && p.name === o.name && Math.abs(p.x - x) < 3 && Math.abs(p.y - y) < 3 ? p : { kind, name: o.name, x, y }));
  };
  const hoverRef = useRef(hover); hoverRef.current = hover;
  /** Q / Shift+Q: the next / previous object as the primary; X: swap the primary and the secondary. */
  const cyclePrimary = (dir: 1 | -1) => {
    if (objects.length < 2) return;
    const cur = pairOf(plot);
    const i = objects.findIndex((o) => o.id === cur.primary);
    const next = objects[(i + dir + objects.length) % objects.length].id;
    actions.setObjectPair(plot.id, next, next === cur.secondary ? cur.primary : cur.secondary);
  };

  /* the map's own keys, only while it has the focus: arrows pan (Shift+arrows still step the cursor),
     + / − zoom, F follows (the primary object, else the first), 0 fits everything */
  const toggleFollow = () => {
    const id = plot.followObject ? null : (plot.primaryObject && objects.some((o) => o.id === plot.primaryObject) ? plot.primaryObject : objects[0]?.id ?? null);
    actions.updatePlot(plot.id, { followObject: id });
  };
  const onKey = (e: React.KeyboardEvent) => {
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    const step = 120;
    const k = e.key;
    const done = () => { e.preventDefault(); e.stopPropagation(); markHintSeen(); };
    if (!e.shiftKey && (k === "ArrowLeft" || k === "ArrowRight" || k === "ArrowUp" || k === "ArrowDown")) {
      stopAnim();
      panBy(k === "ArrowLeft" ? step : k === "ArrowRight" ? -step : 0, k === "ArrowUp" ? step : k === "ArrowDown" ? -step : 0);
      done();
    } else if (k === "+" || k === "=") { zoomBy(1); done(); }
    else if (k === "-" || k === "_") { zoomBy(-1); done(); }
    else if (k === "0") { fitAll(); done(); }
    else if (k.toLowerCase() === "f" && objects.length) { toggleFollow(); done(); }
    else if (k.toLowerCase() === "q" && objects.length > 1) { cyclePrimary(e.shiftKey ? -1 : 1); done(); }
    else if (k.toLowerCase() === "x" && objects.length > 1) { const c = pairOf(plot); if (c.secondary) actions.setObjectPair(plot.id, c.secondary, c.primary); done(); }
  };

  /* the one-line hint, until the map is first moved or the hint closed (remembered) */
  const [hint, setHint] = useState(() => !getPrefValue<boolean>(HINT_PREF));
  const markHintSeen = () => { if (!getPrefValue<boolean>(HINT_PREF)) setPref(HINT_PREF, true); setHint(false); };
  const backToFollow = () => {
    followOff.current = null; setOffFollow(false);
    const g = followRef.current();
    if (g) animateTo({ ...viewRef.current!, cx: g.cx, cy: g.cy }, 220);
  };

  const prec = view ? Math.max(1, Math.min(8, Math.round(view.z * 0.3 + 1))) : 2;
  return (
    <div className="plot-canvas geo" ref={wrapRef} style={{ position: "relative" }} tabIndex={0} onKeyDown={onKey}
      aria-label={t("mapKeysHint")} data-view={view ? `${view.z.toFixed(4)},${view.cx.toFixed(9)},${view.cy.toFixed(9)}` : undefined}>
      {(() => {
        const D = plot.mapUp === "track" ? Math.ceil(Math.hypot(size.w, size.h)) : 0;
        return <canvas ref={cvRef} style={D ? { width: D, height: D, display: "block", cursor: "grab", position: "absolute", left: (size.w - D) / 2, top: (size.h - D) / 2 }
          : { width: size.w, height: size.h, display: "block", cursor: "grab" }} />;
      })()}
      {plot.mapUp === "track" && <canvas ref={topRef} className="geo-top" style={{ width: size.w, height: size.h }} />}
      {view && (
        <div className="geo-ctrl" role="toolbar" aria-label={t("mapControls")} onMouseDown={(e) => e.stopPropagation()}>
          <button className="geo-zoom-in" onClick={() => zoomBy(1)} title={`${t("mapZoomIn")} (+)`} aria-label={t("mapZoomIn")}>+</button>
          <button className="geo-zoom-out" onClick={() => zoomBy(-1)} title={`${t("mapZoomOut")} (−)`} aria-label={t("mapZoomOut")}>−</button>
          <button className="geo-fit" onClick={fitAll} title={`${t("mapFitAll")} (0)`} aria-label={t("mapFitAll")}>
            <svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true"><path d="M2 6V2h4M10 2h4v4M14 10v4h-4M6 14H2v-4" /></svg></button>
          {objects.length > 0 && (
            <select className="geo-follow" value={plot.followObject ?? ""} title={`${t("objFollow")} (F)`} aria-label={t("objFollow")}
              onChange={(e) => actions.updatePlot(plot.id, { followObject: e.target.value || null })}>
              <option value="">{t("mapFollowOff")}</option>
              {objects.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
            </select>
          )}
          {objects.length > 0 && (
            <button className={`geo-up${plot.mapUp === "track" ? " on" : ""}`} aria-pressed={plot.mapUp === "track"}
              title={t(plot.mapUp === "track" ? "mapTrackUpHint" : "mapNorthUpHint")} aria-label={t(plot.mapUp === "track" ? "mapTrackUp" : "mapNorthUp")}
              onClick={() => actions.updatePlot(plot.id, { mapUp: plot.mapUp === "track" ? undefined : "track" })}>
              <span ref={northRef} className="geo-north" aria-hidden="true">N</span></button>
          )}
          {offFollow && plot.followObject && <button className="geo-back" onClick={backToFollow}>{t("mapBackToFollow")}</button>}
        </div>
      )}
      {view && hint && (
        <div className="geo-hint" role="note">{t("mapHint")}
          <button className="iconbtn sm" onClick={markHintSeen} aria-label={t("close")} title={t("close")}>×</button></div>
      )}
      {mouse && <div className="geo-readout">{mouse.lat.toFixed(prec)}°, {mouse.lon.toFixed(prec)}°</div>}
      <TrackKeys objects={objects} colors={objColors} />
      {objects.length > 1 && <RelationPanel plot={plot} objects={objects} tracks={objTracks} />}
      {ringTip && (
        <div className="ring-tip" role="tooltip" style={{ left: ringTip.x + 14, top: ringTip.y + 14 }}>
          {ringTip.kind !== "none" && <RingIcon kind={ringTip.kind} />}<b>{ringTip.name}</b>
          <span>{t(ringTip.kind === "primary" ? "relRingTip_primary" : ringTip.kind === "secondary" ? "relRingTip_secondary" : "relRingTipNone")}</span>
        </div>
      )}
      {(!plot.xSignal || !ys.length) && !objects.length && <div className="plot-empty">{emptyText}</div>}
      {badRange && <div className="plot-empty">{notDegrees}</div>}
    </div>
  );
}

