/* RE2 (owner, 2026-11-19): the report's ready-made parts as a library - categories of parts (commanded vs actual,
   navigation, the scenario, comparing files, what to look at), each part one click into the text, and ready
   reports made of them: the app looks at what the open files have (backend/app/reportparts.py scan) and proposes
   the parts that fit; the user edits the result like any text. The user's own reports are kept as report
   templates (the app's settings: they belong to the user, not to one session) and as part of a session template
   (templates.ts: `report`). Nothing here knows a log format. */
import { api, type ReportScan } from "./api";
import { useApp } from "./store";
import { getPrefValue, setPref } from "./prefs";
import { translate, type TKey } from "./i18n";

type Lang = "en" | "he";
export interface PartEntry { label: string; insert: string; title?: string }
export interface PartCategory { id: "tracking" | "navigation" | "scenario" | "compare" | "summary"; title: string; found: string; empty?: string; parts: PartEntry[] }
export interface Choice { reference?: string; base?: string }

/** The library's categories for what was found. A category with nothing found says so and has no parts. */
export function partCategories(scan: ReportScan, lang: Lang, choice: Choice = {}): PartCategory[] {
  const t = (k: TKey, p?: Record<string, string | number>) => translate(lang, k, p);
  const refOpt = choice.reference && choice.reference !== scan.reference ? ` | ref ${choice.reference}` : "";
  const baseOpt = choice.base && choice.base !== (scan.base ?? scan.files[0]?.name) ? ` | base ${choice.base}` : "";
  const pairs = [...new Map(scan.pairs.map((p) => [p.measured, p])).values()];
  const out: PartCategory[] = [
    { id: "tracking", title: t("rpCatTracking"), found: t("rpFoundPairs", { n: scan.pairs.length }), empty: scan.pairs.length ? undefined : t("rpNoPairs"),
      parts: scan.pairs.length ? [
        { label: t("rpTrackAll"), insert: "[[tracking]]" },
        { label: t("rpTrackTable"), insert: "[[tracking | table]]" },
        { label: t("rpTrackTol"), insert: "[[tracking | tol 2, outside 1%]]", title: t("rpTrackTolHint") },
        ...pairs.map((p) => ({ label: `${p.measured} ← ${p.setpoint}`, insert: `[[tracking ${p.measured.replace(/ \[[^\]]*\]$/, "")} | top 1]]` })),
      ] : [] },
    { id: "navigation", title: t("rpCatNav"), found: t("rpFoundObjects", { n: scan.objects.length }), empty: scan.objects.length >= 2 ? undefined : t("rpNoObjects"),
      parts: scan.objects.length >= 2 ? [
        { label: t("rpNavAll"), insert: `[[navigation${refOpt}]]` },
        { label: t("rpNavPos"), insert: `[[navigation${refOpt ? refOpt + ", position" : " | position"}]]` },
        { label: t("rpNavVel"), insert: `[[navigation${refOpt ? refOpt + ", velocity" : " | velocity"}]]` },
        { label: t("rpNavAtt"), insert: `[[navigation${refOpt ? refOpt + ", attitude" : " | attitude"}]]` },
        { label: t("rpNavTable"), insert: `[[navigation${refOpt ? refOpt + ", table" : " | table"}]]` },
      ] : [] },
    { id: "scenario", title: t("rpCatScenario"), found: t("rpFoundScenario", { s: scan.states.length, t: scan.tracks }),
      parts: [
        { label: t("rpOverview"), insert: "[[overview]]", title: t("rpOverviewHint") },
        ...(scan.states.length ? [{ label: t("rpStatesAll"), insert: "[[states]]" }] : []),
        ...[...new Set(scan.states.map((s) => s.name))].map((n) => ({ label: t("rpStatesOne", { name: n }), insert: `[[states ${n}]]` })),
        ...(scan.tracks ? [{ label: t("rpTrajectory"), insert: "[[trajectory]]" }] : []),
        { label: t("rpMoments"), insert: "[[moments]]", title: t("rpMomentsHint") },
      ] },
    { id: "compare", title: t("rpCatCompare"), found: t("rpFoundFiles", { n: scan.files.length }), empty: scan.files.length >= 2 ? undefined : t("rpNoFiles"),
      parts: scan.files.length >= 2 ? [
        { label: t("rpDiffMain"), insert: `[[differences${baseOpt}]]`, title: t("rpDiffHint") },
        { label: t("rpDiffTable"), insert: `[[differences${baseOpt ? baseOpt + ", table" : " | table"}]]` },
        { label: t("rpDiffTop"), insert: `[[differences${baseOpt ? baseOpt + ", top 12" : " | top 12"}]]` },
      ] : [] },
    { id: "summary", title: t("rpCatSummary"), found: "", parts: [{ label: t("rpSummary"), insert: "[[summary]]", title: t("rpSummaryHint") },
      { label: t("rpToc"), insert: "[[toc]]", title: t("rpTocHint") }] },
  ];
  return out;
}

export type ReadyId = "auto" | "control" | "navigation" | "compare";

/** The ready reports that fit what was found (the automatic one always). */
export function readyReports(scan: ReportScan, lang: Lang): { id: ReadyId; label: string; hint: string }[] {
  const t = (k: TKey) => translate(lang, k);
  return [
    { id: "auto" as const, label: t("rpReadyAuto"), hint: t("rpReadyAutoHint") },
    ...(scan.pairs.length ? [{ id: "control" as const, label: t("rpReadyControl"), hint: t("rpReadyControlHint") }] : []),
    ...(scan.objects.length >= 2 ? [{ id: "navigation" as const, label: t("rpReadyNav"), hint: t("rpReadyNavHint") }] : []),
    ...(scan.files.length >= 2 ? [{ id: "compare" as const, label: t("rpReadyCompare"), hint: t("rpReadyCompareHint") }] : []),
  ];
}

/** A ready report's text: a title, what to look at, then the parts that fit, each under its heading, and a place
 *  for the conclusion. Only parts that have something to find are written. */
export function readyText(id: ReadyId, scan: ReportScan, lang: Lang, choice: Choice = {}, notes = false): string {
  const t = (k: TKey, p?: Record<string, string | number>) => translate(lang, k, p);
  const ref = choice.reference && choice.reference !== scan.reference ? ` | ref ${choice.reference}` : "";
  const base = choice.base && choice.base !== (scan.base ?? scan.files[0]?.name) ? ` | base ${choice.base}` : "";
  const files = scan.files.map((f) => f.name).join(", ");
  const has = { pairs: scan.pairs.length > 0, nav: scan.objects.length >= 2, states: scan.states.length > 0, tracks: scan.tracks > 0, many: scan.files.length >= 2 };
  const want = {
    auto: { scenario: true, tracking: has.pairs, nav: has.nav, compare: has.many },
    control: { scenario: has.states, tracking: true, nav: false, compare: has.many },
    navigation: { scenario: has.tracks, tracking: false, nav: true, compare: false },
    compare: { scenario: false, tracking: false, nav: false, compare: true },
  }[id];
  const title = { auto: "rpTitleAuto", control: "rpTitleControl", navigation: "rpTitleNav", compare: "rpTitleCompare" }[id] as TKey;
  const out = [`# ${t(title)}${files ? ` - ${files}` : ""}`, t("rpIntro"), "[[toc]]", "[[summary]]"];
  if (id === "compare") out.push(`## ${t("rpHCompare")}`, `[[differences${base}]]`);
  if (id === "auto") out.push(`## ${t("rpHRecording")}`, "[[overview]]");
  if (want.scenario) {
    out.push(`## ${t("rpHScenario")}`);
    if (has.states) out.push("[[states]]");
    if (has.tracks) out.push("[[trajectory]]");
    out.push(`### ${t("rpHMoments")}`, "[[moments]]");
  }
  if (want.tracking && has.pairs) out.push(`## ${t("rpHTracking")}`, "[[tracking]]");
  if (want.nav && has.nav) out.push(`## ${t("rpHNav")}`, `[[navigation${ref}]]`);
  if (want.compare && id !== "compare" && has.many) out.push(`## ${t("rpHCompare")}`, `[[differences${base}]]`);
  if (notes) out.push(`## ${t("rpHNotes")}`, "[[notes]]");
  out.push(`## ${t("rpHConclusion")}`, t("rdSummaryHint"));
  return out.join("\n\n") + "\n";
}

// ------------------------------------------------------------------------------------------------ the user's own

export interface MyReport { name: string; text: string; at: number }
const KEY = "sv.reportTemplates";

export const myReports = (): MyReport[] => getPrefValue<MyReport[]>(KEY) ?? [];

/** Keep the report's text under a name (the same name replaces it). */
export function saveMyReport(name: string, text: string): MyReport[] {
  const list = myReports().filter((r) => r.name !== name);
  list.unshift({ name, text, at: Date.now() });
  setPref(KEY, list);
  return list;
}

export function deleteMyReport(name: string): MyReport[] {
  const list = myReports().filter((r) => r.name !== name);
  setPref(KEY, list);
  return list;
}

/** A whole report put into the editor: it replaces a report nobody wrote yet; else it goes in at the caret
 *  without its title (a report has one title). */
export function readyInsert(text: string, untouched: boolean): { replace: boolean; text: string } {
  return untouched ? { replace: true, text } : { replace: false, text: text.replace(/^#\s+[^\n]*\n+/, "") };
}

// the user's own parts: any piece of a report kept under a name, offered in the library's *My parts*
export interface MyPart { name: string; text: string; at: number }
const PKEY = "sv.reportMyParts";
export const myParts = (): MyPart[] => getPrefValue<MyPart[]>(PKEY) ?? [];
export function saveMyPart(name: string, text: string): MyPart[] {
  const list = myParts().filter((r) => r.name !== name);
  list.push({ name, text, at: Date.now() });
  setPref(PKEY, list);
  return list;
}
export function deleteMyPart(name: string): MyPart[] {
  const list = myParts().filter((r) => r.name !== name);
  setPref(PKEY, list);
  return list;
}

/** The Report screen with the automatic report of the open files (the report demo example; a report already
 *  written is kept - the screen only opens). One Undo step. */
export async function openAutoReport(): Promise<void> {
  const scan = await api.reportParts();
  const st = useApp.getState();
  const lang = st.ws.report?.lang ?? st.lang;
  if (!st.ws.report?.doc) {
    const text = readyText("auto", scan, lang, {}, (st.ws.notes ?? []).length > 0);
    st.commit((w) => { w.report = { title: "", intro: "", summary: "", lang, theme: "light", scope: "tab", ...(w.report ?? {}), doc: { v: 1, text } }; return w; });
  }
  useApp.setState({ panel: "report" });
}
