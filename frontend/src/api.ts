import type { Structure } from "./store/model";
import { translate } from "./i18n";
import type { GlanceItem, GlanceStat, MapObject, PinnedSearch } from "./store";

export type StorageKind = "cache" | "uploads" | "tiles" | "memory";
/** memory (P2): not on disk - the results kept in memory to be fast, with its limit and per kind */
export type StorageInfo = Record<StorageKind, { path: string; bytes: number; limit?: number; kinds?: Record<string, { bytes: number; entries: number }> }>;
/** The welcome screen's examples (backend routes/fs.py EXAMPLE_SETS). */
export type ExampleId = "servoStep" | "processPlant" | "monteCarlo" | "cruiseSimVsTest" | "flight" | "twoFlights" | "car" | "bench" | "ardupilot" | "simVsFlight" | "investigate" | "folderOfFlights" | "commonGains" | "smartSweepDemo" | "sweepTable" | "reportDemo" | "serialLink" | "linkStructure" | "channel" | "gpsNmea" | "automations";
/** P1: what an export of a map's objects reports: the rate used (lowered for a long recording) and the
 *  objects left out because they have no position (P2). */
export interface FlightExport { path: string; objects: number; size?: number; rate: number; lowered: boolean; leftOut: string[] }

/** P3: a message type the firmware wrote with another length than its FMT (written), or unreadable. */
export interface FaultyMessage {
  name: string;
  declared?: number;          // the length its FMT says
  written?: number;           // the length really written (or a type with no FMT: its length)
  names?: number; fields?: number;   // its FMT lists `names` column names for `fields` values
  noFormat?: boolean;         // no usable FMT at all: "#<type number>"
}

export interface SignalTransform { expr?: string; scale?: number; offset?: number; dt?: number;
  unit?: string }                          // the unit shown after a unit conversion (units.ts)
export interface SignalInfo {
  id: string; name: string; discrete?: boolean;
  n?: number; rate?: number;            // T22: samples and mean sample rate (Hz), from the describe
  labels?: Record<string, string>;      // text values: code -> text (states, flight modes)
  transform?: SignalTransform;          // a change made on the signal itself
  // derived signals only
  op?: string; sources?: string[]; params?: Record<string, unknown>; formula?: string; valid?: boolean; samples?: number;
  quality?: DerivedQuality;             // C3: what was done about missing / infinite values (only when something was)
  version?: string;                     // F34: changes whenever the derived signal's data does
}
/** C3: a derived signal's missing-data report - samples where a missing input was left out ("skip"),
 *  an integral's gaps bridged ("skip") or where it became unknown ("propagate"), infinite values. */
export interface DerivedQuality {
  nan?: string; skipped?: number; bridged?: [number, number][]; missing?: [number, number][]; infinite?: number;
  /** 26.A3 / 26.U6: a filter run on each stretch between gaps, or on an even grid (uneven samples) */
  filter?: { gaps?: number; resampled?: boolean; fs?: number | null; gapTime?: number };
  /** 26.U6: sources read between their samples (another signal's sample times), and how */
  interpolated?: { method: string; sources: number[] };
}
/** LINK1: a byte link (serial / UDP / TCP) recorded to `path` (.svraw, its structure beside it), followed live. */
/** MSG3: a structure in the library - NMEA built in, a file of the structures folder, an ICD layout of the readers folder. */
export interface LibraryItem { key: string; name: string; kind?: "binary" | "text"; source: "builtin" | "folder" | "readers";
  path?: string; file?: string; messages?: number; error?: string }
/** MSG3: a byte stream of an open file (one direction), its messages at a glance. `key`: its definition's sources. */
export interface StreamRow { key: string; name: string; rid: string; file: string; ids: string[]; params: Record<string, unknown>;
  error?: string; count?: number; bytes?: number; header?: string; framing?: string; checksum?: string | null; errors?: number;
  duration?: number; typed?: boolean; types?: { type: number; count: number; rate: number | null }[];
  /** CH7: this direction's anomalies (svcore/channel.py; a definition's two directions read together) */
  anomalies?: { total: number; counts: Partial<Record<AnomalyKind, number>>; capture?: number } }
/** CH1 / CH8: two streams that look like one link's two directions - by their names, or one answers the other */
export interface StreamLink { tx: string; rx: string; why: "names" | "replies" | "clock";
  /** CH9: "clock" - how far RX's clock looks ahead of TX's (s; the fastest reply read as 1 ms) */
  shift?: number }
/** CH2: one direction of a channel (a definition's stream), the type ids its structure describes */
export interface ChannelSide { label: string; sources: string[]; params: Record<string, unknown>; known?: number[] }
/** CH12: the link shows it / the link shows the bytes were fine (the capture's) / nothing reacted */
export type AnomalyCause = "link" | "capture" | "none";
export type AnomalyKind = "checksum" | "broken" | "length" | "unknown" | "counter" | "gap" | "unanswered" | "retry" | "late" | "reconnect" | "handshake";
/** CH2: a channel's anomalies in time order (columns), counted per kind and direction, and the patterns found */
export interface ChannelInfo { kinds: AnomalyKind[]; counts: Record<AnomalyKind, number>; byDir: Record<string, Partial<Record<AnomalyKind, number>>>;
  total: number; span: [number, number]; timeout: number;
  events: { t: number[]; kind: AnomalyKind[]; dir: string[]; type: (number | null)[]; detail: string[]; cause: AnomalyCause[]; why: string[] };
  /** CH12: per kind, how many are the link's, likely the capture's (a sniffer's glitch), or had no effect seen */
  causes: Record<AnomalyKind, Record<AnomalyCause, number>>; byCause: Record<AnomalyCause, number>;
  sides: { name: string; count: number; header: string; framing: string; typeOffset: number | null; checksum: string | null;
    types: { type: number; count: number; rate: number | null }[] }[];
  /** CH9: nearly nothing answered in time, yet the echoed ids pair them at a steady delay: two clocks apart */
  clock: { shift: number; pairs: number; of: number; request: number; reply: number } | null;
  pairs: { from: string; to: string; request: number; reply: number; how: "id" | "next"; requests: number; replies: number; mean: number | null; max: number | null }[];
  handshake: { t: number; steps: { dir: string; type: number; t: number }[] }[] }
/** CH10: the same channel in several files (svcore/channel.compare_files) */
export interface ChannelCompare {
  files: { name: string; error?: string; total?: number; counts?: Record<AnomalyKind, number>; byCause?: Record<AnomalyCause, number>;
    span?: [number, number]; events?: { t: number[]; kind: AnomalyKind[]; cause: AnomalyCause[] } }[];
  standsOut: { file: string; kind: AnomalyKind; value: number; others: number }[];
  patterns: { file: string; what: "header" | "checksum" | "framing" | "type" | "notype" | "rate" | "latency"; dir: string;
    type?: number; reply?: number; count?: number; value?: number | string; others?: number | string }[] }
/** MSG4: the guided view of a byte stream (svcore/msginspect.py) - the patterns that recur, the structure (given or
 *  proposed), the first messages byte by byte (binary) or part by part (text) with their fields' values, the counts. */
export interface InspectFrame { t: number; at: number; len?: number; id?: number | string; message: string; status: "ok" | "bad" | "unknown";
  bytes?: number[]; roles?: string[]; fields?: (number | null)[]; values: (number | string | null)[]; text?: string; parts?: string[];
  /** filled in the page: the frame's message's field names, and (text) which field each part is */
  fieldNames?: string[]; fieldAt?: (number | null)[] }
/** CP4: the Confluence settings the page may see */
export interface ConfluenceInfo { url: string; user: string; hasToken: boolean; recent: { url: string; title: string }[] }
export interface InspectPattern { hex: string; bytes: number; count: number; every: number; regular: number; first: number; role?: string;
  /** MSG6: with pauses in the stream - how often right after one / right before one, and what that makes it */
  afterPause?: number; beforePause?: number; time?: "start" | "end" | null }
export interface MessagesInspect { bytes: number; head: number[]; text: boolean; patterns: InspectPattern[]; frames: InspectFrame[];
  /** MSG6: the stream has pauses between messages - they tell a message's start from its end */
  pauses?: boolean;
  structure?: Structure; suggested?: boolean; error?: string;
  summary: { messages: number; bad: number; outside: number; unknown: Record<string, number>; byMessage: Record<string, number>; bytes: number } | null }
/** RE3: the LaTeX on this computer (svcore/latex.py) - nothing is fetched */
export interface TexStatus { engines: Record<string, string | null>; tools: Record<string, string | null>; best: string | null;
  snippets: boolean; folder: string | null; hint: string | null }
export interface LinkStatus { running: boolean; conn?: string; path?: string; bytes?: number; chunks?: number; written?: number;
  rate?: number; sinceData?: number | null; peer?: string | null; error?: string | null }
/** Live MAVLink receiver (T12): the link is recorded to `path` (.tlog), which live mode follows. */
export interface MavStatus {
  running: boolean; conn?: string; path?: string; frames?: number; bytes?: number; written?: number; rate?: number;
  request?: boolean; sinceData?: number | null; sinceHeartbeat?: number | null; vehicle?: number[] | null; error?: string | null;
}
export interface RunInfo {
  id: string;
  version?: string;                      // F34: changes whenever the file's data does (reload, live)
  name: string;
  path: string;
  format: "csv" | "mat" | "bin" | "tlog" | "ulg" | "mcap" | "hdf5" | "parquet" | "derived";
  tag?: string;                          // T46: the file's short tag (A, B... or the user's); not for derived
  color?: string;                        // T46: the file's colour
  /** Only for files that carry a flight log's parameters / events (ArduPilot .bin). */
  log?: { params: number; events: number; errors: number; warnings: number };
  samples: number;
  start: number;
  end: number;
  timeOffset: number;
  importSettings: Record<string, unknown>;
  /** What the Time axis dialog may change, and how it is set now (not for derived signals). */
  timeAxis?: TimeAxisInfo;
  signals: SignalInfo[];
  report?: { skipped?: string[]; skippedColumns?: string[]; droppedRows?: number; sorted?: boolean; fromCache?: boolean; rememberedSettings?: boolean;
    textColumns?: string[]; tooManyTexts?: string[]; timePairs?: number; vehicle?: string | null; corruptBytes?: number; damaged?: boolean; droppedMessages?: number; phantomInstances?: string[]; faultyMessages?: FaultyMessage[]; readableShare?: number; badTimestamps?: number; damagedParams?: number; damagedTexts?: number; cutOff?: boolean; matObjects?: string[]; damagedText?: boolean; damagedObjects?: number; noTime?: boolean; params?: number;
    paramValues?: Record<string, number>; logMessages?: { t: number; text: string }[] };
  description?: string;
  copy?: boolean;                        // opened from a dragged-in copy, not the original file
  fileTime?: number;                     // Q123: when the version shown was saved to the disk (epoch s)
  readAt?: number;                       // Q123: when the app read it (epoch s)
}
/** Investigation step 4: one signal around a moment (svcore/firstchange.py). */
export interface FirstChange { id: string; name: string; status: "changed" | "same" | "nodata"; t?: number; rel?: number; up?: boolean;
  base?: [number, number];                // the usual level was read here (the default one fits each signal's data)
  strength?: number; rate?: number; spark?: (number | null)[];
  /** Q131: the usual level and noise (the cluster's plot puts every signal on one axis by them) */
  level?: number; noise?: number; stay?: number;
  /** Q133: a signal that cannot tell anything: left out by default */
  skip?: "constant" | "counter" | "heartbeat";
  /** Q131: how likely a cause, 0..1, and its parts (WEIGHTS on the server) */
  score?: number; parts?: Record<string, number>; inRef?: string[]; isEvent?: boolean; leadsEvent?: number }
/** Q130: changes close in time, the likeliest first. */
export interface ChangeCluster { t0: number; t1: number; ids: string[]; first: string; best: number }
/** Q134: who leads whom - nodes in time order, an edge when B clearly follows A. */
export interface ChangeChain { nodes: { id: string; t: number; cluster: string | null }[]; edges: { a: string; b: string; lag: number; r: number }[] }
export interface LagResult { status: "ok" | "nooverlap" | "short" | "flat"; lag?: number; r?: number; ambiguous?: boolean; weak?: boolean;
  resolution?: number; curve?: { lags: number[]; r: number[] } }
/** Investigation step 7: a run's phases and automatic flags (svcore/overview.py). */
export interface RunOverview { phaseSignal: string | null; phases: { a: number; b: number; label: string; v?: number }[];
  rows?: Record<string, { a: number; b: number; label: string; v?: number }[]>;
  flags: { kind: "stuck" | "saturated" | "gap" | "spike"; signal: string; a: number; b: number; value?: number; edge?: "max" | "min" }[];
  start: number; end: number; scanned: number; partial: boolean }
export interface TimeAxisInfo {
  canColumn: boolean; canScale: boolean;
  column: string | null;                 // the time column, as the file names it
  columnUnit: string | null;             // the unit its name says (ms, us...)
  scale: number; ownScale: number; offset: number;
  ownTimes: number;                      // signals with a time column of their own
  candidates?: string[];                 // (check only) signals that can become the time
  sorted: boolean;                       // the rows were sorted by the time when read
}
export interface ColumnAsTime {
  n: number; missing: number; unit: string | null; min: number | null; max: number | null;
  order: "increasing" | "nondecreasing" | "decreasing" | "mixed" | "empty";
  repeats?: number; backSteps?: number; step?: number | null; gaps?: number; maxGap?: number | null;
}
export interface TimeAxisCheck {
  info: TimeAxisInfo; column?: ColumnAsTime; brokenDerived?: string[];
  timedDerived: string[]; timedEdits: string[];
}
export interface TimeAxisResult {
  run: RunInfo;
  before: { column: string | null; scale: number; ownScale: number; offset: number };
  times: (number | null)[];
}
export interface Series {
  id: string;
  missing?: boolean;
  n: number;
  total: number;
  decimated: boolean;
  x: Float64Array;
  y: Float64Array;              // P3: rebuilt from float32 differences around a float64 reference
}
export interface Stats { min: number; max: number; mean: number; std: number; rms: number; peak_to_peak: number; samples: number; duration: number; segments?: number;
  /** A3: "time" when the samples are unevenly spaced and mean / RMS / std are weighted by time; gaps: dropouts not weighted */
  weighting?: "time"; gaps?: number;
  /** L8: the largest |value|, its time (s, on the shown axis) and the 95th percentile of |value| */
  abs_max?: number; t_abs_max?: number; p95_abs?: number }
/** U5: a run's difference from the baseline over time (t, d), the tolerance band as an allowed
 *  difference (lo, hi; absent without a tolerance) and the stretches outside it */
/** 26.U7: a signal's data quality (svcore/quality.py) and a file's summary */
export interface SignalQuality { name: string; n: number; rate: number | null; missing: number; missingPct: number; allMissing: boolean;
  gaps: number; gapTime: number; firstGap: number | null; duplicates: number; backwards: number;
  rateChanges: { t: number; from: number; to: number }[]; issues: string[] }
export interface RunQuality { signals: SignalQuality[]; count: Record<"missing" | "gaps" | "duplicates" | "backwards" | "rateChanges", number>;
  checked: number; withIssues: number; sorted: boolean }
/** 26.U5: a tolerance (signalviewer-cli compare's --tolerances file): abs in the signal's unit, pct of the
 *  baseline's value, time in seconds, outside_pct the share of samples allowed outside; `as` (the run's
 *  name) and keys of later versions are kept as written */
export interface TolEntry { abs?: number; pct?: number; time?: number; outside_pct?: number; skip?: boolean; [key: string]: unknown }
export interface Tolerances { default: TolEntry; signals: Record<string, TolEntry> }
export interface DiffTrace { t: number[]; d: (number | null)[]; lo?: (number | null)[]; hi?: (number | null)[]; out: [number, number][] }
export interface CompareRow { id: string; valid: boolean; matchPct?: number; samples?: number; rmsDiff?: number; maxAbsDiff?: number; meanDiff?: number; rmsPct?: number; correlation?: number; withinPct?: number; pass?: boolean; outsidePct?: number; trace?: DiffTrace;
  /** CC20: the RMS difference over the baseline's own sample-to-sample noise (none for a noiseless signal) */
  noiseRatio?: number }
export interface CompareFileStats { run: string; mean: number | null; std: number | null; min: number | null; max: number | null; rms: number | null }
export interface CompareDiff { run: string; rmsDiff: number; rmsPct: number; maxAbsDiff: number; meanDiff: number; stdDiff: number; correlation: number; withinPct?: number | null; pass?: boolean | null; outsidePct?: number | null }
/** RE2: what the report's ready-made parts would find in the open files (backend/app/reportparts.py scan) */
export interface ReportScan {
  files: { id: string; name: string }[];
  pairs: { setpoint: string; measured: string; file: string }[];
  objects: { name: string; cls: string; pos: string }[];
  reference: string | null;
  /** the baseline file guessed (its name says ref / baseline / golden..., else the first) */
  base: string | null;
  states: { name: string; file: string }[];
  tracks: number;
  /** MSG1: the byte streams with messages found (a direction split: "rx_byte RX") */
  streams?: { name: string; file: string; count: number }[];
  /** CC15: how many of the files have a checks file beside them ([[requirements]]) */
  checks?: number;
}
export interface CompareAllRow {
  name: string; runs?: string[]; baseline?: string; error?: string;
  /** C13: the signal of each file in this row (run id -> name), when names differ by their unit */
  sigs?: Record<string, string>;
  meanSpread?: number | null; stdSpread?: number | null; worstRmsDiff?: number | null; worstRmsPct?: number | null;
  worstMaxAbs?: number | null; minCorrelation?: number | null; pass?: boolean | null;
  matchPct?: number | null; profile?: (number | null)[] | null;
  /** 26.U5: the tolerance it is judged by, its own entry's key (null: every signal's), left out */
  tol?: TolEntry; tolKey?: string | null; skipped?: boolean;
  files?: CompareFileStats[]; diffs?: CompareDiff[];
}
export interface JobInfo { id: string; kind: string; label: string; state: "running" | "done" | "error" | "cancelled"; progress: number; phase: string; error: string | null; result: any; elapsed: number }
/** Why a file could not be opened: `code` (+ params) is translated by the UI; `message` is the English fallback. */
export interface LoadErrorInfo { path: string; message: string; code?: string; params?: Record<string, string | number> }
/** Where templates are kept (the user can choose the folder). */
export interface TemplateFolderInfo { folder: string; default: boolean; exists: boolean; defaultFolder: string }
/** T24: the file dialog's side column. */
export interface FsPlaces {
  open: string[];                                         // folders of the open files
  favourites: { path: string; exists: boolean }[];        // pinned, in the user's order
  recent: { path: string; exists: boolean }[];            // folders of recent files / sessions
  standard: { id: "home" | "desktop" | "documents" | "downloads"; path: string }[];
  drives: string[];
}

export interface RecentItem { path: string; kind: "file" | "session"; time: number; name: string; folder: string; exists: boolean }
export interface FsEntry { name: string; path: string; dir: boolean; size?: number | null; mtime?: number }

/* Templates (version 2): a set of tabs whose signals are stored by NAME, each from a file SLOT;
   when a template is opened, every slot is given an open file (or "all files that fit"). A template
   can also include other templates (a collection). One JSON file per template in the templates folder. */
export interface LimitResult { lo: number | null; hi: number | null; samples: number; pass: boolean; violations: number;
  timeOutside: number; first: number | null; worst: number | null; worstT: number | null; spans: [number, number][] }
export interface TplSignal { limits?: { lo?: number | null; hi?: number | null }; name: string; slot?: string; color?: string; width?: number; scale?: number; offset?: number;
  state?: boolean; tOffset?: number; label?: string }
export interface TplPlot { title: string; mode?: string; xSignal?: string | null; xSlot?: string; xyAlign?: string; fftWindow?: string; fftMethod?: string;
  fftLog?: boolean; fftFilters?: boolean; specN?: number; caption?: string; ylim?: [number, number] | null; signals: TplSignal[]; objects?: TplObject[] }
/** A map object in a template: each of its signals by name (alternatives "a|b" allowed) and file slot. */
export type TplObjectRole = "lat" | "lon" | "alt" | "yaw" | "pitch" | "roll" | "qw" | "qx" | "qy" | "qz";
export interface TplObject { name: string; kind: string; color?: string; roles: Partial<Record<TplObjectRole, { name: string; slot?: string }>>;
  angleUnit?: string; altRef?: string; trail?: boolean; size?: number;
  /** N5: the class, the track's look and a motion attitude (a borrowed one names an object: not kept) */
  cls?: "truth" | "navigation" | "receiver" | "other"; track?: "line" | "dash" | "points"; attitudeSource?: "motion"; minSpeed?: number }
export interface TplTab { name: string; rows: number; cols: number; rowSizes?: number[]; colSizes?: number[]; linkX?: boolean;
  linkY?: boolean; lanes?: { name: string; slot?: string }[]; plots: TplPlot[] }
/** A file the template takes. file / path: the file it was saved from (to find the same file again when opened). */
export interface TplSlot { id: string; name: string; formats?: string[]; file?: string; path?: string }
/** A template tab with real signal ids for the open files (/api/templates/resolve). */
export interface ResolvedTab {
  name: string; rows: number; cols: number; rowSizes?: number[] | null; colSizes?: number[] | null; linkX?: boolean; linkY?: boolean | null;
  sharedStates?: string[] | null;
  plots: { title: string; mode?: string; xSignal?: string | null; xyAlign?: string; fftWindow?: string; fftMethod?: string; fftLog?: boolean; fftFilters?: boolean;
    specN?: number; caption?: string; ylim?: [number, number] | null;
    signals: { sig: string; color: string | null; width?: number; scale?: number; offset?: number; state?: boolean | null; tOffset?: number | null;
      label?: string | null; limits?: { lo?: number | null; hi?: number | null } }[];
    objects?: { name: string; kind?: string; color?: string | null; lat: string; lon: string; alt?: string | null; yaw?: string | null; pitch?: string | null;
      roll?: string | null; qw?: string | null; qx?: string | null; qy?: string | null; qz?: string | null; angleUnit?: string; altRef?: string;
      trail?: boolean; size?: number; cls?: MapObject["cls"]; track?: MapObject["track"]; attitudeSource?: "motion"; minSpeed?: number }[] }[];
}
/** A condition kept in a template (by signal NAME, so it holds in any file that has the names). */
export interface TplCondition { id: string; name: string; color: string; text: string; exit?: string; minDur?: number; mergeGap?: number;
  combine?: { op: "and" | "or"; ids: string[] } }
/** P10: one moment of a Story (svcore/story.py) */
export interface StoryMoment { t: number; kind: string; title: string; text: string; object: string | null; level: string }

export interface Template {
  version: 2; id: string; name: string; description?: string; group?: string;
  slots: TplSlot[]; tabs: TplTab[]; includes?: string[];
  /** U1: the tabs (by name, over the included templates too) opened without asking; absent = all */
  defaultTabs?: string[];
  conditions?: TplCondition[];       // the investigation's conditions: added (by name) when the template opens
  places?: import("./store").Place[];   // P7: the session's places: added (by name and position) when the template opens
  /** D14 (a profile): its run-at-a-glance numbers and its pinned searches - added when the template opens (optional) */
  glance?: GlanceItem[]; searches?: PinnedSearch[]; instruments?: string[];   // + F4
  /** RE2: the written report (Markdown, signals by name - the same text fits the next recording) - set when the
   *  template opens on a session that has no written report yet */
  report?: { v: 1; text: string; assets?: Record<string, import("./store").ReportAsset> };
  generator?: "quicklook" | "compare" | "objects" | "pairs" | "effort" | "spectrum" | "envelope";   // built-in templates whose tabs are made from the files themselves
  builtin?: boolean; saved?: number; file?: string; broken?: boolean;
}

/** P3: a request given up on purpose (a newer one replaced it: the plot moved on) - not an error to show. */
export const isAborted = (e: unknown) => (e as { name?: string } | null)?.name === "AbortError";

async function send(url: string, body: unknown, method: string, signal?: AbortSignal): Promise<Response> {
  let res: Response;
  try {
    res = await fetch(url, {
      method,
      headers: body === undefined ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal,
    });
  } catch (e) {
    if (isAborted(e)) throw e;
    // no answer at all ("Failed to fetch"): the app's local server is not running any more -
    // say that and what to do, instead of the browser's bare words
    const lang = document.documentElement.lang === "he" ? "he" : "en";
    throw new Error(translate(lang, "serverGone"));
  }
  if (!res.ok) {
    let msg = res.statusText;
    try { msg = (await res.json()).detail ?? msg; } catch { /* keep status text */ }
    throw new Error(msg);
  }
  return res;
}

export async function call<T>(url: string, body?: unknown, method = body === undefined ? "GET" : "POST", signal?: AbortSignal): Promise<T> {
  return (await send(url, body, method, signal)).json() as Promise<T>;
}

/** P3: the binary /api/data answer (backend routes/data.py pack_series): a uint32 header length, the JSON
 *  header, then each series' x (float64) and y - yRef (float32) at the offsets it gives. x is viewed in
 *  place; y is rebuilt in float64 around its reference (float32 alone rounds 1.7e9 to steps of 128). */
export function unpackSeries(buf: ArrayBuffer): Series[] {
  const n = new DataView(buf).getUint32(0, true);
  const head = JSON.parse(new TextDecoder().decode(new Uint8Array(buf, 4, n))) as { series: any[] };
  const base = 4 + n;
  return head.series.map((s) => {
    if (s.missing) return { id: s.id, missing: true, n: 0, total: 0, decimated: false, x: new Float64Array(), y: new Float64Array() };
    const x = new Float64Array(buf, base + s.xAt, s.n);
    const rel = new Float32Array(buf, base + s.yAt, s.n);
    const y = new Float64Array(s.n);
    const ref = Number(s.yRef) || 0;
    for (let i = 0; i < s.n; i++) y[i] = ref + rel[i];
    return { id: s.id, n: s.n, total: s.total, decimated: s.decimated, x, y };
  });
}

function decode<T extends Float64Array | Float32Array>(b64: string, Ctor: { new (buf: ArrayBuffer): T }): T {
  const bin = atob(b64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return new Ctor(bytes.buffer);
}

/** T31: the user's own Python operations (backend app/pyops.py). */
export interface PyOp { id: string; name: string; inputs: number; doc: string; params: Record<string, number | string | boolean> }
export interface PyOpsInfo { folder: string; default: boolean; exists: boolean; ops: PyOp[]; errors: { file: string; error: string }[] }

export const api = {
  listRuns: () => call<RunInfo[]>("/api/runs"),
  clientError: (b: { message: string; stack: string; where: string }) => call<{ logged: boolean }>("/api/client-error", b),
  pyops: () => call<PyOpsInfo>("/api/pyops"),
  readers: () => call<{ folder: string; readers: { id: string; name: string; extensions: string[]; file: string }[];
    errors: { file: string; error: string }[] }>("/api/readers"),
  pyopsReload: () => call<PyOpsInfo>("/api/pyops/reload", {}),
  pyopsFolder: (path: string | null) => call<PyOpsInfo>("/api/pyops/folder", { path }),
  pyopsExample: () => call<PyOpsInfo & { example: string }>("/api/pyops/example", {}),
  pyopsReveal: () => call<{ folder: string }>("/api/pyops/reveal", {}),
  pushEvents: (since: number, opens = false) => call<{ seq: number; events: { seq: number; kind?: "open"; paths?: string[]; run?: string; name?: string; plot?: boolean; new?: boolean; age: number }[] }>(`/api/push/events?since=${since}${opens ? "&opens=1" : ""}`),
  pushSaveClient: (path: string) => call<{ path: string }>("/api/push/save-client", { path }),
  diagnostics: () => call<{ text: string; logFile: string; version: string }>("/api/diagnostics"),
  reportProblem: () => call<{ url: string; opened: boolean }>("/api/report-problem", {}),
  runLog: (id: string) => call<LogInfo>(`/api/runs/${encodeURIComponent(id)}/log`),
  syncSuggest: (ref: string, other: string, refSignal?: string | null, otherSignal?: string | null,
    opts: { feature?: { kind: string; levelPct?: number; occurrence?: number }; maxLag?: number | null } = {}) =>
    call<{ candidates: SyncCandidate[] }>("/api/sync/suggest", { ref, other, refSignal: refSignal ?? null, otherSignal: otherSignal ?? null,
      feature: opts.feature ?? null, maxLag: opts.maxLag ?? null }),
  runHealth: (id: string) => call<HealthReport>(`/api/runs/${encodeURIComponent(id)}/health`),
  runChecksFile: (id: string) => call<ChecksFile>(`/api/runs/${encodeURIComponent(id)}/checks-file`),
  spectrogram: (signal: string, x0: number | null, x1: number | null, nfft: number, width: number, height: number, fmax: number | null) =>
    call<SpecData>("/api/spectrogram", { signal, x0, x1, nfft, width, height, fmax }),
  open: (paths: string[], settings?: Record<string, unknown>) =>
    call<{ opened: RunInfo[]; errors: LoadErrorInfo[] }>("/api/files/open", { paths, settings }),
  suggestFiles: (path: string) => call<{ candidates: { path: string; name: string; mtime: number; similar: boolean }[]; best: string | null }>("/api/files/suggest", { path }),
  fileSignals: (path: string, settings?: unknown) => call<{ signals: string[] }>("/api/files/signals", { path, settings }),
  locate: (files: { name: string; size: number; mtime: number }[]) => call<{ paths: (string | null)[] }>("/api/files/locate", { files }),
  upload: async (files: File[]) => {
    const fd = new FormData();
    files.forEach((f) => fd.append("files", f));
    const res = await fetch("/api/files/upload", { method: "POST", body: fd });
    if (!res.ok) throw new Error(res.statusText);
    return (await res.json()) as { paths: string[]; skipped?: string[] };
  },
  preview: (path: string, settings?: Record<string, unknown>) => call<any>("/api/files/preview", { path, settings }),
  remove: (id: string) => call<{ ok: boolean }>(`/api/runs/${id}`, undefined, "DELETE"),
  patchRun: (id: string, patch: { name?: string; timeOffset?: number; description?: string; tag?: string; color?: string }) => call<RunInfo>(`/api/runs/${id}`, patch, "PATCH"),
  replace: (id: string, path: string) => call<RunInfo>(`/api/runs/${id}/replace`, { path }),
  previewDerived: async (op: string, sources: string[], params: Record<string, unknown>, x0: number | null, x1: number | null) => {
    const r = await call<{ n: number; x: string; y: string }>("/api/derived/preview", { op, sources, params, x0, x1 });
    return { x: decode(r.x, Float64Array), y: decode(r.y, Float32Array) };
  },
  /** MSG2: a structure proposed from a byte stream / the stream's messages by a structure, as a new recording */
  messagesSuggest: (sources: string[], params: Record<string, unknown>) =>
    call<{ structure: Structure }>("/api/messages/suggest", { sources, params }),
  messagesParse: (sources: string[], params: Record<string, unknown>, structure: Structure, name: string, id?: string) =>
    call<{ run: string; new: boolean; signals: string[]; runs: RunInfo[]; report: Record<string, unknown> }>("/api/messages/parse", { sources, params, structure, name, id: id ?? null }),
  messagesInspect: (sources: string[], params: Record<string, unknown>, structure: Structure | null, n = 12) =>
    call<MessagesInspect>("/api/messages/inspect", { sources, params, structure, n }),
  /** CH2: a channel's patterns beyond the content and its anomalies (svcore/channel.py) - one direction or two */
  messagesChannel: (sides: ChannelSide[]) => call<ChannelInfo>("/api/messages/channel", { sides }),
  /** CH10: the same channel in several files - each file's anomalies and what differs between them */
  messagesChannelCompare: (files: { name: string; sides: ChannelSide[] }[]) => call<ChannelCompare>("/api/messages/channel-compare", { files }),
  messagesStructure: (path: string) => call<{ structure: Structure }>("/api/messages/structure", { path }),
  messagesNmea: () => call<{ structure: Structure }>("/api/messages/nmea"),
  // MSG3: the structure library and the open files' byte streams (the Messages panel)
  messagesLibrary: () => call<{ folder: string; items: LibraryItem[] }>("/api/messages/library"),
  messagesLibraryGet: (key: string) => call<{ structure: Structure }>("/api/messages/library/get", { key }),
  messagesLibrarySave: (structure: Structure, name?: string, overwrite = false) =>
    call<{ path: string; key: string }>("/api/messages/library/save", { structure, name, overwrite }),
  messagesLibraryReveal: () => call<{ folder: string }>("/api/messages/library/reveal", {}),
  /** MSG5: a direction column's values (2..most), each with its count and its text */
  directionValues: (id: string) => call<{ values: { v: number; n: number; label: string | null }[]; distinct: number; most: number }>("/api/messages/direction-values", { id }),
  messagesStreams: (streams: unknown[], runs?: string[]) => call<{ streams: StreamRow[]; links: StreamLink[] }>("/api/messages/streams", { streams, runs: runs ?? null }),
  reportParts: (runs?: string[], streams?: unknown[]) => call<ReportScan>("/api/report/parts", { runs: runs ?? null, streams: streams ?? null }),
  /** the page (Markdown) - or, for a report written in LaTeX (RE3), the PDF this computer's TeX made (a token) / its error */
  reportPreview: (body: Record<string, unknown>) =>
    call<{ html?: string; tex?: boolean; pdf?: string | null; error?: string | null; line?: number | null }>("/api/report/preview", body),
  reportTexStatus: () => call<TexStatus>("/api/report/tex"),
  reportToLatex: (text: string, lang: string, words: Record<string, string>, title: string) =>
    call<{ text: string }>("/api/report/tolatex", { text, lang, words, title }),
  reportTexOpen: (token: string) => call<{ opened: boolean }>("/api/report/tex/open", { path: token }),
  reload: (id: string) => call<RunInfo>(`/api/runs/${id}/reload`, {}),
  /** Q123: open files saved again since they were read -> when (epoch s). A stat each, nothing read. */
  newerOnDisk: () => call<Record<string, number>>("/api/runs/newer-on-disk"),
  /** Why the app opened in the browser instead of its own window ("" = it did not). */
  windowNote: () => call<{ browserReason: string; mode?: string }>("/api/window_note"),
  /** What the app keeps on disk (CSV cache, copies of dropped files, map tiles) and clearing it. */
  storage: () => call<StorageInfo>("/api/storage"),
  clearStorage: (what: StorageKind[]) => call<StorageInfo & { result: Partial<Record<StorageKind, { freed: number; kept: number }>> }>("/api/storage/clear", { what }),
  poll: () => call<{ changed: string[]; runs: RunInfo[] | null; errors?: Record<string, string>;
    activity?: Record<string, number>; newFiles?: { path: string; name: string; size: number; mtime: number }[]; writing?: string[] }>("/api/stream/poll", {}),
  streamStart: (lookBack = 0) => call<{ ok: boolean }>("/api/stream/start", { lookBack }),
  streamStop: () => call<{ ok: boolean }>("/api/stream/stop", {}),
  mavlinkStart: (body: { conn: string; baud?: number; request?: boolean; rate?: number }) => call<MavStatus>("/api/mavlink/start", body),
  mavlinkStop: () => call<MavStatus>("/api/mavlink/stop", {}),
  linkStart: (body: { conn: string; baud?: number; structure?: Structure | null }) => call<LinkStatus>("/api/link/start", body),
  linkStop: () => call<LinkStatus>("/api/link/stop", {}),
  linkStatus: () => call<LinkStatus>("/api/link/status"),
  linkPorts: () => call<{ ports: { device: string; description: string }[]; presets: string[]; folder: string }>("/api/link/ports"),
  mavlinkStatus: () => call<MavStatus>("/api/mavlink/status"),
  mavlinkPorts: () => call<{ ports: { device: string; description: string }[]; presets: string[]; folder: string }>("/api/mavlink/ports"),
  /** P3: binary (no base64), cancellable (a plot that moved on aborts its older requests) */
  data: async (signals: string[], x0: number | null, x1: number | null, points: number, signal?: AbortSignal): Promise<Series[]> =>
    unpackSeries(await (await send("/api/data", { signals, x0, x1, points, format: "bin" }, "POST", signal)).arrayBuffer()),
  createDerived: (op: string, sources: string[], params: Record<string, unknown>, name?: string) =>
    call<{ id: string; name: string; runs: RunInfo[] }>("/api/derived", { op, sources, params, name: name || null }),
  restoreDerived: (items: { op: string; sources: string[]; params?: unknown; name?: string }[]) =>
    call<{ restored: string[]; failed: { name: string; message: string }[]; runs: RunInfo[] }>("/api/derived/restore", { items }),
  renameDerived: (old: string, name: string) => call<{ id: string; name: string; runs: RunInfo[] }>("/api/derived/rename", { old, new: name }),
  deleteDerived: (name: string) => call<{ runs: RunInfo[] }>(`/api/derived/${encodeURIComponent(name)}`, undefined, "DELETE"),
  filters: async (signal: string, t0: number | null, t1: number | null, fs: number | null) => {
    const r = await call<{ setup: FilterSetup | null; f?: string; gain?: string; fs?: number }>("/api/filters", { signal, t0, t1, fs, points: 2000 });
    return { setup: r.setup, f: r.f ? decode(r.f, Float64Array) : null, gain: r.gain ? decode(r.gain, Float32Array) : null };
  },
  stepResp: async (pairs: [string, string][], t0: number | null, t1: number | null): Promise<StepSeries[]> => {
    const r = await call<{ series: any[] }>("/api/stepresp", { pairs, t0, t1, length: 0.5 });
    return r.series.map((s) => ({ ...s, t: s.t ? decode(s.t, Float64Array) : undefined, step: s.step ? decode(s.step, Float32Array) : undefined }));
  },
  fft: async (signals: string[], window: string, t0: number | null, t1: number | null, points: number, method: "fft" | "welch" = "fft") => {
    const r = await call<{ series: any[] }>("/api/fft", { signals, window, method, t0, t1, points });
    return r.series.map((s) => (s.missing ? { id: s.id, missing: true, n: 0, peak: NaN, x: new Float64Array(), y: new Float32Array() }
      : { ...s, x: decode(s.x, Float64Array), y: decode(s.y, Float32Array) })) as
      { id: string; missing?: boolean; n: number; peak: number; x: Float64Array; y: Float32Array; grid?: SpectrumGrid }[];
  },
  xy: async (x: string, ys: string[], alignment: string, t0: number | null, t1: number | null) => {
    const r = await call<{ series: any[] }>("/api/xy", { x, ys, alignment, t0, t1, relative: true });
    // t: the time of each point, so the timeline can draw the plot / map up to a time
    // P3: y around its float64 reference (a latitude in float32 is rounded by up to ~0.2 m)
    return r.series.map((s) => (s.missing ? { id: s.id, missing: true, n: 0, x: new Float64Array(), y: new Float64Array(), t: new Float64Array() }
      : { ...s, x: decode(s.x, Float64Array), y: Float64Array.from(decode(s.y, Float32Array), (v) => (Number(s.yRef) || 0) + v),
          t: s.t ? decode(s.t, Float64Array) : new Float64Array() })) as
      { id: string; missing?: boolean; n: number; x: Float64Array; y: Float64Array; t: Float64Array }[];
  },
  /** T17c plain 3D: each track's Y and Z on its X signal's samples. */
  xyz: async (tracks: { x: string; y: string; z: string }[], alignment: string) => {
    const r = await call<{ tracks: any[] }>("/api/xyz", { tracks, alignment });
    return r.tracks.map((s) => (s.missing || s.empty ? { id: s.id as string, missing: !!s.missing, empty: !!s.empty } as const
      : { id: s.id as string, t: decode(s.t, Float64Array), x: decode(s.x, Float32Array), y: decode(s.y, Float32Array), z: decode(s.z, Float32Array) }));
  },
  /** An object on the map: its signals on one time axis (see the server's object_track). */
  objectTrack: async (o: { lat: string; lon: string; alt?: string | null; yaw?: string | null; pitch?: string | null; roll?: string | null;
    qw?: string | null; qx?: string | null; qy?: string | null; qz?: string | null;
    trackColor?: "object" | "state" | "value"; colorSig?: string | null; attitude?: "motion" | null; minSpeed?: number }) => {
    const { trackColor, colorSig, attitude, minSpeed, ...rest } = o;
    const colored = trackColor && trackColor !== "object" && colorSig;
    const r = await call<{ n: number; t: string; lat: string; lon: string; alt?: string; yaw?: string; pitch?: string; roll?: string;
      course: string; ground?: string; color?: string; units: Record<string, "deg" | "rad">; derived?: "motion"; valid?: number }>("/api/object_track",
      { ...rest, ...(colored ? { color: colorSig, colorStep: trackColor === "state" } : {}),
        ...(attitude === "motion" ? { attitude, ...(minSpeed !== undefined ? { minSpeed } : {}) } : {}) });
    const f = (s?: string) => (s ? decode(s, Float32Array) : null);
    return { n: r.n, t: decode(r.t, Float64Array), lat: decode(r.lat, Float64Array), lon: decode(r.lon, Float64Array),
      alt: f(r.alt), yaw: f(r.yaw), pitch: f(r.pitch), roll: f(r.roll), course: decode(r.course, Float32Array), ground: f(r.ground), units: r.units,
      color: f(r.color), derived: r.derived ?? null, valid: r.valid ?? null };
  },
  states: (signals: string[], x0: number | null, x1: number | null, bins = 1500) =>
    call<{ states: Record<string, { points: [number, number | null][]; tooMany: boolean; end: number | null }> }>("/api/states", { signals, x0, x1, bins }),
  neighbor: async (signal: string, t: number, steps: number) => {
    const r = await call<{ t: number | null }>("/api/neighbor", { signal, t, steps });
    return r;
  },
  cursor: (signals: string[], t: number) => call<{ values: Record<string, number | null> }>("/api/cursor", { signals, t }),
  /** R1: a page the app saved (a replay) in the user's browser - HTML only */
  openPage: (path: string) => call<{ opened: boolean }>("/api/export/open", { path }),
  sparks: (signals: string[], points = 40) => call<{ sparks: Record<string, { lo: (number | null)[]; hi: (number | null)[] } | null> }>("/api/sparks", { signals, points }),
  stats: (signals: string[], t0: number | null, t1: number | null, where?: { state: string; values: number[]; offset?: number } | null) =>
    call<{ stats: Record<string, Stats> }>("/api/stats", { signals, t0, t1,
      ...(where ? { state: where.state, stateValues: where.values, stateOffset: where.offset ?? 0 } : {}) }),
  limits: (items: { id: string; lo: number | null; hi: number | null; scale: number; offset: number; tOffset: number }[], t0: number | null, t1: number | null) =>
    call<{ results: Record<string, LimitResult> }>("/api/limits", { items, t0, t1 }),
  envelope: async (signals: { id: string; scale: number; offset: number; tOffset: number }[], t0: number | null, t1: number | null, points: number) => {
    const r = await call<{ n: number; empty?: boolean; pct?: number; t?: string; min?: string; max?: string; lo?: string; hi?: string; median?: string;
      runs?: { id: string; deviation: number; outlier: boolean }[] }>("/api/envelope", { signals, t0, t1, points });
    if (r.empty) return { n: r.n, empty: true as const };
    const f = (k: "min" | "max" | "lo" | "hi" | "median") => decode(r[k]!, Float32Array);
    return { n: r.n, empty: false as const, pct: r.pct, runs: r.runs ?? [], t: decode(r.t!, Float64Array),
      min: f("min"), max: f("max"), lo: f("lo"), hi: f("hi"), median: f("median") };
  },
  segments: (signal: string) => call<{ total: number;
    segments: { t0: number; t1: number; value: number; label: string | null }[];
    byValue: { value: number; label: string | null; duration: number; count: number }[] }>("/api/segments", { signal }),
  examples: () => call<{ id: ExampleId; paths: string[]; open?: "study" | "sweep" | "summary" | "report" | "messages" | "structure" | "map" }[]>("/api/examples"),   // open "study": the last path is a .svstudy.json (W14 / W18)
  // the example's files ready to open (the packages write the recordings on first use): the same entry, its paths
  prepareExample: (id: string) => call<{ id: ExampleId; paths: string[]; open?: "study" | "sweep" | "summary" | "report" | "messages" | "structure" | "map" }>(`/api/examples/${encodeURIComponent(id)}/prepare`, undefined, "POST"),
  completePath: (text: string, base: string | null, exts?: string[]) =>
    call<{ dir: string | null; items: { name: string; path: string; dir: boolean }[]; common: string }>("/api/fs/complete", { text, base, exts }),
  listDir: (path?: string | null, exts?: string[]) => call<{ path: string; parent: string | null; entries: FsEntry[]; hidden?: number }>("/api/fs/list", { path, exts }),
  places: () => call<FsPlaces>("/api/fs/places"),
  // §7b: the file dialog as a browser - a new folder, a rename, to the recycle bin (only in the user's own folders)
  makeFolder: (parent: string, name: string) => call<{ path: string }>("/api/fs/mkdir", { parent, name }),
  renamePath: (path: string, name: string) => call<{ path: string }>("/api/fs/rename", { path, name }),
  trashPath: (path: string) => call<{ path: string; trash: string }>("/api/fs/delete", { path }),
  setFavourites: (paths: string[]) => call<{ favourites: { path: string; exists: boolean }[] }>("/api/fs/favourites", { paths }, "PUT"),
  compare: (signals: string[], baseline: string, alignment: string, tolerances: Tolerances,
    windows?: Record<string, [number, number]> | null, trace = 0) =>
    call<{ overlap: [number, number]; gridPoints: number; baseline: string; rows: CompareRow[]; tol: TolEntry }>("/api/compare", { signals, baseline, alignment, tolerances, windows: windows ?? null, trace }),
  runQuality: (id: string) => call<RunQuality>(`/api/runs/${id}/quality`),
  loadTolerances: (path: string) => call<{ path: string; tolerances: Tolerances }>("/api/compare/tolerances/load", { path }),
  saveTolerances: (path: string, tolerances: Tolerances) => call<{ path: string }>("/api/compare/tolerances/save", { path, tolerances }),
  segmentsAcross: (runs: string[], state: string, value: number, occurrence: number) =>
    call<{ windows: import("./segments").SegWindow[] }>("/api/segments/across", { runs, state, value, occurrence }),
  compareAll: (runs: string[], baselineRun: string, alignment: string, tolerances: Tolerances) =>
    call<{ signals: CompareAllRow[] }>("/api/compare/all", { runs, baselineRun, alignment, tolerances }),
  shift: (base: string, other: string) => call<{ shift: number }>("/api/compare/shift", { base, other }),
  /** N8: a map / 3D view's objects as a Tacview ACMI 2.2 text file */
  exportAcmi: (path: string, title: string, objects: object[], rate = 10, places: object[] = []) =>
    call<FlightExport>("/api/export/acmi", { path, title, objects, rate, places }),
  /** P2: how many samples of each candidate are positions (before it is added) */
  objectPositions: (objects: { lat: string; lon: string }[]) =>
    call<{ objects: { valid: number; total: number }[] }>("/api/object_positions", { objects }),
  /** P1: Tacview CSV files, one per object, into a folder */
  exportTacviewCsv: (folder: string, title: string, objects: object[], rate = 10) =>
    call<FlightExport & { files: string[] }>("/api/export/tacview_csv", { path: folder, title, objects, rate }),
  /** P7: My places (the app's places.json), import / export, a typed position, the ground at a point */
  myPlaces: () => call<{ places: import("./store").Place[]; path: string }>("/api/places"),
  putMyPlaces: (places: import("./store").Place[]) => call<{ places: import("./store").Place[] }>("/api/places", { places }, "PUT"),
  importPlaces: (path: string) => call<{ places: import("./store").Place[]; skipped: number }>("/api/places/import", { path }),
  exportPlaces: (path: string, places: import("./store").Place[], title = "") => call<{ path: string; places: number }>("/api/places/export", { path, places, title }),
  parsePlace: (q: string) => call<{ ok: boolean; lat?: number; lon?: number }>(`/api/places/parse?q=${encodeURIComponent(q)}`),
  groundAt: (lat: number, lon: number) => call<{ ground: number | null }>(`/api/ground?lat=${lat}&lon=${lon}`),
  /** P10: Story mode - the moments of a Map (its objects, the pair, places, the timeline's marks) */
  story: (body: { objects: object[]; places: object[]; primary: string | null; secondary: string | null; events: object[]; units: string; lang: string }) =>
    call<{ moments: StoryMoment[] }>("/api/story", body),
  /** P1: the objects (and places) as one KML file for Google Earth */
  exportKml: (path: string, title: string, objects: object[], rate = 10, places: object[] = []) =>
    call<FlightExport>("/api/export/kml", { path, title, objects, rate, places }),
  /** E1: a part of a recording as a new file (svcore/subset.py); the path's extension is the format. */
  exportRecording: (body: { path: string; signals: { id: string; label: string; unit?: string }[]; t0?: number | null; t1?: number | null;
    where?: string; margin?: number; rate?: number | null; antialias?: boolean; fromZero?: boolean; source?: string }) =>
    call<{ path: string; rows: number }>("/api/export/recording", body),
  exportCsv: (path: string, signals: { id: string; label: string; scale: number; offset: number; tOffset?: number }[], t0: number | null, t1: number | null) =>
    call<{ path: string; rows: number }>("/api/export/csv", { path, signals, t0, t1 }),
  /** CP1: a plot / a tab for a Confluence page - the page saved (every sample), the HTML macro's lines, the static copy */
  clip: (body: Record<string, unknown>) => call<{ path: string; name: string; size: number; macro: string; static: string }>("/api/export/clip", body),
  /** CP4: Send to Confluence - the settings (never the token), a test, the send, the page in the browser */
  confluence: () => call<ConfluenceInfo>("/api/confluence"),
  confluenceSet: (body: { url?: string; user?: string; token?: string }) => call<ConfluenceInfo>("/api/confluence", body),
  confluenceTest: () => call<{ user: string }>("/api/confluence/test", {}),
  confluenceSend: (body: Record<string, unknown>) => call<{ page: string; url: string; added: boolean; updated: boolean; name: string; size: number; link?: boolean }>("/api/export/confluence", body),
  /** CP7: the plot drawn again as a PNG at `scale` times the pixels, for the clipboard (Settings: Copied pictures) */
  imageBytes: async (plot: unknown, theme: string, scale: number, lang: string) =>
    (await send("/api/export/image-bytes", { plot, theme, scale, lang }, "POST")).blob(),
  /** CP5: a plot or tab dragged out of the window - what it is, for the link the system fetches at the drop */
  dragRegister: (body: Record<string, unknown>) => call<{ ok: boolean }>("/api/export/drag", body),
  confluenceOutline: (body: { page: string; title: string }) => call<{ page: string; shows: boolean; marker: string | null; headings: { level: number; text: string }[] }>("/api/confluence/outline", body),
  confluenceOpen: () => call<{ opened: boolean; url: string }>("/api/confluence/open", {}),
  /** CP3: the Signal Viewer user macro for Confluence (installed once by an administrator) */
  clipUserMacro: () => call<{ name: string; template: string }>("/api/export/clip/user-macro"),
  report: (body: Record<string, unknown>) => call<{ path: string; size: number }>("/api/report", body),
  /** a plot as PNG (scale 2: for a report, twice the pixels), SVG or an interactive HTML page */
  image: (path: string, format: "png" | "svg" | "html", theme: string, plot: unknown, scale = 1, lang = "en") =>
    call<{ path: string }>("/api/export/image", { path, format, theme, plot, scale, lang }),
  discrete: (sig: string) => call<{ discrete: boolean; detected?: boolean; levels?: number | null; readAs?: "state" | "value" | null }>(`/api/discrete?sig=${encodeURIComponent(sig)}`),
  /** 26.A5: the user's corrections (the workspace's whole map) -> the backend; the runs come back */
  readAs: (names: Record<string, "state" | "value">) => call<{ runs: RunInfo[] }>("/api/read_as", { names }),
  /** 26.A5: what "Automatic" takes an object's angles to be, and why */
  angleUnits: (roles: { yaw?: string | null; pitch?: string | null; roll?: string | null }) =>
    call<{ units: Record<string, { unit: "deg" | "rad"; why: "name" | "beyond" | "within" }> }>("/api/angle_units", roles),
  recent: () => call<{ items: RecentItem[] }>("/api/recent"),
  forgetRecent: (path: string) => call<{ items: RecentItem[] }>("/api/recent/forget", { path }),
  forgetImport: (path: string) => call<{ ok: boolean }>("/api/import/forget", { path }),
  templates: () => call<{ templates: Template[]; builtin: Template[] } & TemplateFolderInfo>("/api/templates"),
  // T11b: matching runs in the backend (svcore/templates.py) - the same code the batch reports use
  templateFits: (templates: Template[]) => call<{ fits: Record<string, number | null> }>("/api/templates/fit", { templates }),
  bindTemplate: (template: Template, all: Template[], prefer?: string | null) =>
    call<{ bind: Record<string, string>; slots: { id: string; names: number; counts: Record<string, number> }[] }>("/api/templates/bind", { template, all, prefer: prefer ?? null }),
  resolveTemplate: (template: Template, all: Template[], bind: Record<string, string>, chosen: number[] | null, extraTabs: TplTab[]) =>
    call<{ tabs: ResolvedTab[]; dropped: string[]; missing: string[] }>("/api/templates/resolve", { template, all, bind, chosen, extraTabs }),
  setTemplateFolder: (path: string | null) => call<TemplateFolderInfo & { copied: number }>("/api/templates/folder", { path }),
  saveTemplate: (template: Template, replace = true) => call<{ template: Template }>("/api/templates", { template, replace }),
  deleteTemplate: (id: string) => call<{ ok: boolean }>(`/api/templates/${encodeURIComponent(id)}`, undefined, "DELETE"),
  importTemplates: (path: string) => call<{ templates: Template[] }>("/api/templates/import", { path, ids: [] }),
  exportTemplates: (ids: string[], path: string) => call<{ path: string }>("/api/templates/export", { path, ids }),
  revealTemplates: () => call<{ folder: string }>("/api/templates/reveal", {}),
  setTransforms: (signals: string[], transform: SignalTransform | null) =>
    call<{ previous: Record<string, SignalTransform | null>; runs: RunInfo[] }>("/api/transforms", { signals, transform }),
  setTransformSpecs: (specs: Record<string, SignalTransform | null>) =>
    call<{ previous: Record<string, SignalTransform | null>; runs: RunInfo[] }>("/api/transforms", { specs }),
  startJob: (kind: string, body: unknown, label: string) => call<JobInfo>("/api/jobs", { kind, body, label }),
  evalCondition: (text: string, opts: { exit?: string; minDur?: number; mergeGap?: number; runs?: string[] }) =>
    call<{ results: Record<string, import("./store").CondResult> }>("/api/conditions/eval", { text, exit: opts.exit ?? "", minDur: opts.minDur ?? 0, mergeGap: opts.mergeGap ?? 0, runs: opts.runs }),
  occTable: (runs: Record<string, [number, number][]>, names: string[]) =>
    call<{ rows: { rid: string; a: number; b: number; values: Record<string, { max: number | null; min: number | null; mean: number | null; tMax: number | null }> }[] }>("/api/occurrences/table", { runs, names }),
  occWindows: (items: { sig: string; intervals: [number, number][] }[], align: string, pad: number) =>
    call<{ items: { sig: string; grid: number[]; curves: (number | null)[][]; mean: (number | null)[]; cut: boolean }[] }>("/api/occurrences/windows", { items, align, pad }),
  occDiffer: (runs: Record<string, [number, number][]>, top = 25) =>
    call<{ items: { name: string; effect: number; meanIn: number; meanOut: number; up: boolean; files: string[] }[] }>("/api/occurrences/differ", { runs, top }),
  firstChange: (a: number, b: number, sigs: string[], runs: string[], refs: string[] = [], event: string | null = null) =>
    call<{ items: FirstChange[]; base: [number, number]; noRoom?: boolean; clusters?: ChangeCluster[]; event?: string | null; chain?: ChangeChain;
      weights?: Record<string, number>; skipped?: Record<string, number> }>("/api/firstchange", { a, b, sigs, runs, refs, event }),
  /** "Find similar": the signal most unusual inside [a, b] and a condition like it (id null: none). */
  suggestCondition: (a: number, b: number, sigs: string[]) =>
    call<{ id: string | null; name?: string; text?: string; up?: boolean }>("/api/condition/suggest", { a, b, sigs }),
  lag: (a: string, b: string, t0: number, t1: number) => call<LagResult>("/api/lag", { a, b, t0, t1 }),
  /** M1: per open run, the measures' values and the name pattern's parameters (svcore/summary.py). */
  /** FL1: a folder of recordings before it is summarized - how many, the first, the measures.json kept with it */
  summaryFolder: (path: string) => call<{ folder: string; files: number; first: string | null;
    measures: { name: string; signal: string; op: string; where?: string; t?: number }[] | null; pattern: string | null }>(
    `/api/summary/folder?path=${encodeURIComponent(path)}`),
  runSummary: (measures: { name: string; signal: string; op: string; where?: string; t?: number }[], pattern: string) =>
    call<{ rows: Record<string, { params: Record<string, number | string>; values: Record<string, number | null> }> }>("/api/runs/summary", { measures, pattern }),
  runParams: (runs?: string[]) => call<{ params: Record<string, Record<string, number>> }>("/api/runs/params", { runs }),
  overview: (id: string, rows: string[] = []) =>
    call<RunOverview>(`/api/runs/${encodeURIComponent(id)}/overview${rows.length ? "?" + rows.map((r) => `rows=${encodeURIComponent(r)}`).join("&") : ""}`),
  checkTimeAxis: (id: string, column: string | null) => call<TimeAxisCheck>(`/api/runs/${id}/time-axis/check`, { column }),
  job: (id: string) => call<JobInfo>(`/api/jobs/${id}`),
  cancelJob: (id: string) => call<{ cancelled: boolean }>(`/api/jobs/${id}/cancel`, {}),
  saveImage: (path: string, dataUrl: string) => call<{ path: string }>("/api/save/image", { path, data: dataUrl }),
  saveText: (path: string, content: string, ext = ".csv", bom = true) => call<{ path: string }>("/api/save/text", { path, content, ext, bom }),
  saveSession: (path: string, state: unknown) => call<{ path: string }>("/api/session/save", { path, state }),
  loadSession: (path: string) => call<{ state: any; converted: boolean }>("/api/session/load", { path }),
  getAutosave: () => call<{ state: any; damaged?: string }>("/api/autosave"),
  errorSegments: (a: string, b: string, state: string | null, alignment: string, wrap?: 360 | "2pi") => call<{
    total: ErrStat; rows: (ErrStat & { t0: number; t1: number; value: number; label: string | null; occurrence: number })[] }>("/api/error-segments", { a, b, state, alignment, ...(wrap ? { wrap: String(wrap) } : {}) }),
  getSettings: () => call<{ settings: Record<string, unknown>; offlineForced?: boolean }>("/api/settings"),
  putSettings: (changes: Record<string, unknown>) => call<{ settings: Record<string, unknown> }>("/api/settings", { changes }, "PUT"),
  putAutosave: (state: unknown) => call<{ ok: boolean }>("/api/autosave", state),
  restore: (runs: unknown[]) => call<{ restored: RunInfo[]; missing: any[] }>("/api/session/restore", { runs }),
  // --- F1 / F2 / F3 (svcore/filestruct.py, windowstats.py, runinfo.py)
  runStructure: (id: string) => call<FileStructure>(`/api/runs/${encodeURIComponent(id)}/structure`),
  windowStats: (signals: string[], t0: number | null, t1: number | null) =>
    call<{ stats: Record<string, WindowStat> }>("/api/stats/window", { signals, t0, t1 }),
  runParameters: (id: string) => call<{ params: RunParam[] }>(`/api/runs/${encodeURIComponent(id)}/parameters`),
  compareParameters: (a: string, b: string) => call<ParamDiff>("/api/runs/parameters/compare", { a, b }),
  /** D14: the run-at-a-glance numbers (a profile's / pinned), by signal NAME over the whole run */
  glance: (id: string, items: GlanceItem[]) =>
    call<{ items: GlanceValue[] }>(`/api/runs/${encodeURIComponent(id)}/glance`, { items: items.map(({ name, stat }) => ({ name, stat })) }),
  /** F4: the live instruments - each name's value in force at t (never interpolated) and the object's attitude */
  instruments: (id: string, t: number, names: string[], object: InstrumentObject | null) =>
    call<{ t: number; items: InstrumentValue[]; object: InstrumentState | null }>(`/api/runs/${encodeURIComponent(id)}/instruments`,
      { t, items: names.map((name) => ({ name })), object }),
};

/** F1: one column of "The file" (a signal's samples, mean rate, unit, gaps). */
export interface FileColumn { name: string; field: string; n: number; rate?: number; gaps?: number; unit?: string; state?: boolean; ownTime?: boolean }
/** F1: a group - a log's message type, an MCAP topic, a MAT / HDF5 struct, a table's column prefix ("" = the rest). */
export interface FileGroup { name: string; kind: "message" | "topic" | "struct" | "prefix" | "columns"; columns: FileColumn[];
  n?: number; rate?: number; gaps?: number; longestGap?: number; t0?: number; t1?: number }
export interface FileStructure { format: string; columns: number; timeVectors: number; groups: FileGroup[];
  timeBase: { column?: string; index?: boolean; clock?: "log" | "index"; start?: number; end?: number } }
/** F2: the visible window's statistics - a plain mean of the samples (not time-weighted). */
export interface WindowStat { n: number; min: number; max: number; mean: number; t0: number; t1: number }
/** F3: one parameter of a run and where it comes from. */
export interface RunParam { name: string; value: number | string; source: "log" | "file" | "constant" | "name";
  last?: number; changes?: [number, number][]; default?: number }
export interface ParamDiff { differ: { name: string; a: number | string; b: number | string; source: RunParam["source"];
  aLast?: number; bLast?: number; delta?: number }[]; onlyA: RunParam[]; onlyB: RunParam[]; same: number }
/** D14: one at-a-glance number of a run. sig null: the file has no such signal (say so, do not hide it);
 *  value null: no finite sample, or a state. In the signal's own unit; t = where it is reached (shown time). */
export interface GlanceValue { name: string; stat: GlanceStat; sig: string | null; value: number | null; t: number | null; unit: string | null }
/** F4: a tile's reading. sig null: the file has no such signal; value null: no sample at or before t; text: a
 *  state's label; at: the sample's time (shown time), age = t - at (how long since the source sent it); step: the
 *  signal's typical interval there (what "late" means for it); a state's age is how long it has held, not lateness. */
export interface InstrumentValue { name: string; sig: string | null; unit: string | null; value: number | null; text: string | null; at: number | null; age: number | null;
  state: boolean; step: number | null }
/** F4: the signals of the object the map would draw (objectDetect's picks); angleUnit as the object sets it. */
export type InstrumentObject = Partial<Record<"roll" | "pitch" | "yaw" | "qw" | "qx" | "qy" | "qz" | "lat" | "lon" | "alt", string>> & { angleUnit?: "deg" | "rad" };
/** F4: its attitude in degrees, heading 0-360, altitude as stored, ground speed m/s (from positions); age as above. */
export interface InstrumentState { roll: number | null; pitch: number | null; yaw: number | null; alt: number | null; gs: number | null; age: number | null }

export type LogLevel = "info" | "warning" | "error";
export interface LogEvent { t: number; kind: "msg" | "mode" | "event" | "error"; text: string; level: LogLevel }
export interface LogParam { name: string; value: number; first: number; default: number | null; changes: [number, number][] }
export interface LogInfo {
  vehicle: string | null; firmware: string | null; hasDefaults: boolean; timeOffset: number;
  params: LogParam[]; events: LogEvent[];
  /** 1.21: what the log says about the hardware (ArduPilot) - backend svcore/hardware.py */
  hardware?: { sections: { name: string; rows: [string, string][] }[] };
}

export interface HealthFinding {
  code: string; level: "ok" | "warning" | "error"; vals: Record<string, any>; t: number | null;
  spans: [number, number][]; signals: string[];
}
/** CC12: the profiles that looked at the file - the flight log's, "any data", the user's (an unreadable one: its error) */
export interface HealthProfile { id: "flightlog" | "any" | "user"; name?: string; error?: string }
export interface HealthReport { findings: HealthFinding[]; errors: number; warnings: number; profiles?: HealthProfile[] }
/** RV2: the checks file kept with a recording, run on it (the CLI's verdict); file null = none beside it */
export interface ChecksFileResult { name: string; status: "pass" | "fail" | "error" | "skipped"; lo?: number | null; hi?: number | null;
  window?: string; violations?: number; first?: number; worstT?: number; message?: string;
  /** CC11: a requirement of another kind (settle, overshoot, rise, sserror, rate, track, order) - its measured value */
  kind?: string; value?: number | null; limit?: number }
export interface ChecksFile { file: string | null; error?: string; results: ChecksFileResult[] }
/** T25: the error A − B over some time. */
export interface ErrStat { n: number; rms?: number; mean?: number; maxAbs?: number; tMaxAbs?: number }
/** A1: how a spectrum's samples were put on an even time grid (gaps and NaN are bridged in time). */
export interface SpectrumGrid { resampled?: boolean; fs?: number | null; gaps?: number; gapTime?: number; error?: string; bursts?: number }

export interface SpecData {
  nf: number; nt: number; f0: number; f1: number; t0: number; t1: number; img: string;
  dbLo: number; dbHi: number; fs: number; nfft: number; df: number; dt: number;
  sigT0?: number; sigT1?: number;     // F24: the signal's own first / last time
}

/** ArduPilot's gyro filters from the log's parameters (backend svcore/filters.py) */
export interface FilterSetup {
  notches: { name: string; instance: number; mode: string; base: number[]; baseFrom: "log" | "parameter"; harmonics: number[];
    lines: number[]; ratio: number; att: number; composite: number }[];
  lpf: number | null;
}

/** 1.21: a control loop's step response (backend svcore/stepresp.py) */
export interface StepSeries {
  pair: [string, string]; error?: string; rate?: number; t?: Float64Array; step?: Float32Array; windows?: number; fs?: number;
  rise?: number; overshoot?: number; settle?: number | null; final?: number;
}

export interface SyncCandidate {
  method: "boot" | "events" | "signal" | "feature"; delta: number; error?: string; found?: [boolean, boolean]; kind?: string;
  at?: [number, number]; sameNames?: boolean; offset: number; current: number; quality: "high" | "medium" | "low";
  agrees?: boolean; spread?: number; pairs?: number; overlap?: number; reboots?: number; matched?: number; examples?: string[];
  corr?: number; pair?: [string, string]; scale?: number;
  /** boot / events: how well a pair of one quantity changes together at this offset, and which pair */
  confirm?: number; confirmPair?: [string, string];
  /** why the candidate was lowered to "low": different vehicle types, or the pair does not move together */
  unconfirmed?: "vehicle" | "signal";
  check?: { pair: [string, string] | null; scale: number; refMode: string | null; otherMode: string | null };
}
