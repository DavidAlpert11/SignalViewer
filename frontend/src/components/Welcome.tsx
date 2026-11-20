/* The welcome screen with no file open: what the app is for, open files, the examples (A3: moved
   out of App.tsx with the examples' labels). */
import { useEffect, useState } from "react";
import { api, type ExampleId } from "../api";
import { useApp } from "../store";
import { useT, type TKey } from "../i18n";
import { Icon } from "../icons";
import { addDataExts } from "../values";
import { applyState, openPaths, startRetarget } from "../files";
import { requestStudy } from "../sweeps/studyOpen";
import { requestAreaExample } from "../areaExample";
import { summarizeFolder } from "../folderSummary";
import { startDemoGuide } from "../demoGuide";
import { openAutoReport } from "../reportReady";
import { makeRecording, streamFor } from "../messages";

export const EXAMPLE_LABEL = { flight: "exampleFlight", twoFlights: "exampleTwoFlights", car: "exampleCar", bench: "exampleBench", ardupilot: "exampleArdupilot", simVsFlight: "exampleSimVsFlight", investigate: "exampleInvestigate", folderOfFlights: "exampleFolderOfFlights", commonGains: "exampleCommonGains", smartSweepDemo: "exampleSmartSweepDemo", sweepTable: "exampleSweepTable", reportDemo: "exampleReportDemo", serialLink: "exampleSerialLink", linkStructure: "exampleLinkStructure", gpsNmea: "exampleGpsNmea" } as const satisfies Record<ExampleId, string>;
const EXAMPLE_DESC = { flight: "exampleFlightDesc", twoFlights: "exampleTwoFlightsDesc", car: "exampleCarDesc", bench: "exampleBenchDesc", ardupilot: "exampleArdupilotDesc", simVsFlight: "exampleSimVsFlightDesc", investigate: "exampleInvestigateDesc", folderOfFlights: "exampleFolderOfFlightsDesc", commonGains: "exampleCommonGainsDesc", smartSweepDemo: "exampleSmartSweepDemoDesc", sweepTable: "exampleSweepTableDesc", reportDemo: "exampleReportDemoDesc", serialLink: "exampleSerialLinkDesc", linkStructure: "exampleLinkStructureDesc", gpsNmea: "exampleGpsNmeaDesc" } as const satisfies Record<ExampleId, string>;
const EXAMPLE_ICON = { flight: Icon.Globe, twoFlights: Icon.Compare, car: Icon.Table, bench: Icon.Analysis, ardupilot: Icon.Log, simVsFlight: Icon.Analysis, investigate: Icon.Search, folderOfFlights: Icon.Table, commonGains: Icon.Merge, smartSweepDemo: Icon.Reload, sweepTable: Icon.Table, reportDemo: Icon.Report, serialLink: Icon.Log, linkStructure: Icon.Table, gpsNmea: Icon.Globe } satisfies Record<ExampleId, unknown>;

/** FR11 (owner, 2026-11-16): six cards on the welcome screen, one of them a Sweeps example; every example (these
 *  and the others) is in Help -> Examples. */
export const FEATURED: ExampleId[] = ["ardupilot", "investigate", "simVsFlight", "twoFlights", "folderOfFlights", "smartSweepDemo"];

const EXAMPLE_GROUPS = [
  { area: "recordings", label: "areaRecordings", hint: "exampleGroupRecordings" },
  { area: "sweeps", label: "areaSweeps", hint: "exampleGroupSweeps" },
] as const;

type Example = { id: ExampleId; paths: string[]; open?: "study" | "sweep" | "summary" | "report" | "messages" | "structure" };

/** An example opened as a new user would: recordings with their suggested view, a study in Sweeps. */
export function openExample(example: Example): void {
  useApp.setState({ startOpen: false, demoGuide: null });
  // the packages write the example's recordings on first use (a second or two): its paths once they are there
  void api.prepareExample(example.id).then(openPrepared,
    (e) => useApp.getState().toast({ kind: "error", text: String((e as Error).message) }));
}

function openPrepared(ex: Example): void {
  if (ex.open === "study") requestStudy(ex.paths[ex.paths.length - 1], ex.id === "smartSweepDemo");
  else if (ex.open === "sweep") requestAreaExample("sweeps", ex.paths[ex.paths.length - 1]);   // its .svsweep: the table and its question
  // FL1: a folder of recordings (its measures.json beside them) summed up, a row per recording in Sweeps
  else if (ex.open === "summary") void summarizeFolder(ex.paths[0].replace(/[\\/][^\\/]*$/, "")).then((ok) => { if (ok) void startDemoGuide(ex.id, []); });
  // RE2: the two runs, then the Report screen with the automatic report made of the parts that fit them
  else if (ex.open === "report") void openPaths(ex.paths).then(() => openAutoReport());
  else if (ex.open === "messages") void openPaths(ex.paths).then(() => openAutoReport("messages"));
  // MSG2: the recording, then its two structure files: TX and RX messages -> two recordings of their own, plotted
  else if (ex.open === "structure") void openPaths(ex.paths.slice(0, 1)).then(async (ids) => {
    const rid = ids?.[0] ?? useApp.getState().runs.find((r) => r.path === ex.paths[0])?.id;
    if (!rid) return;
    const [tx, rx] = await Promise.all(ex.paths.slice(1, 3).map((p) => api.messagesStructure(p).then((r) => r.structure)));
    const def = { ...streamFor([`${rid}/tx_byte`, `${rid}/rx_byte`]), structures: { TX: tx, RX: rx } };
    for (const side of ["TX", "RX"]) await makeRecording(useApp.getState().ws.messageStreams?.find((m) => m.id === def.id) ?? def, side);
  });
  // RV5: once its view is open, the demo's own setup and its line of what to do next
  else void openPaths(ex.paths, undefined, { autoView: true }).then((ids) => startDemoGuide(ex.id, ids));
}

/** W1: an example as a card with its picture (made by tools/make_readme_media.py --only examples, one per
 *  theme, language-neutral); a missing picture leaves the card as it was - the icon, the title, the line. */
function ExampleCard({ ex }: { ex: Example }) {
  const t = useT();
  const theme = useApp((s) => s.theme);
  const [broken, setBroken] = useState<string | null>(null);
  const src = `examples/${ex.id}.${theme}.webp`;
  const Ico = EXAMPLE_ICON[ex.id];
  const open = () => openExample(ex);
  const pic = broken !== src;
  return (
    <button className={`ex-card${pic ? " pic" : ""}`} data-example={ex.id} onClick={open}>
      {pic ? (
        <span className="ex-pic"><img src={src} alt={t(`exampleAlt_${ex.id}` as TKey)} loading="lazy" decoding="async"
          width={480} height={270} onError={() => setBroken(src)} /></span>
      ) : <Ico width={18} height={18} />}
      <span className="ex-text"><span className="ex-title">{t(EXAMPLE_LABEL[ex.id])}</span>
        <span className="ex-desc">{t(EXAMPLE_DESC[ex.id])}</span></span>
    </button>
  );
}


export default function Welcome() {
  const t = useT();
  const items = useApp((s) => s.recent);
  useEffect(() => { api.recent().then((r) => useApp.setState({ recent: r.items })).catch(() => {}); }, []);
  // T09: ready examples (a drone flight; three car runs to compare) - a first look in one click
  const [examples, setExamples] = useState<Example[]>([]);
  useEffect(() => { api.examples().then(setExamples).catch(() => setExamples([])); }, []);
  // T60: files of the user's own readers can be chosen and dropped like the built-in types
  useEffect(() => { api.readers().then((r) => addDataExts(r.readers.flatMap((x) => x.extensions))).catch(() => {}); }, []);
  const files = items.filter((x) => x.kind === "file").slice(0, 6);
  const sessions = items.filter((x) => x.kind === "session").slice(0, 4);
  const openRecent = async (x: (typeof items)[number]) => {
    if (!x.exists) return;
    useApp.setState({ startOpen: false });
    if (x.kind === "file") openPaths([x.path]);
    else {
      try { const r = await api.loadSession(x.path); await applyState(r.state, { announce: true }); }
      catch (e) { useApp.getState().toast({ kind: "error", text: String((e as Error).message) }); }
    }
  };
  const forget = async (path: string) => useApp.setState({ recent: (await api.forgetRecent(path)).items });
  const list = (title: string, xs: typeof items, icon: React.ReactNode) => xs.length > 0 && (
    <div className="recent-col">
      <h3 className="eyebrow">{title}</h3>
      {xs.map((x) => (
        <div key={x.path} className={`recent-row${x.exists ? "" : " gone"}`}>
          <button className="recent-open" disabled={!x.exists} onClick={() => openRecent(x)} title={x.path}>
            {icon}<span className="recent-name">{x.name}</span><span className="recent-folder">{x.exists ? x.folder : t("notFound")}</span>
          </button>
          {x.kind === "session" && x.exists && (
            <button className="iconbtn sm" onClick={() => startRetarget(x.path)} aria-label={t("withNewFiles")} title={t("withNewFiles")}><Icon.Replace /></button>
          )}
          <button className="iconbtn sm" onClick={() => forget(x.path)} aria-label={t("forget")} title={t("forget")}><Icon.X /></button>
        </div>
      ))}
    </div>
  );
  const hasRuns = useApp((s) => s.runs.length > 0);
  return (
    <div className="welcome">
      {hasRuns && <button className="btn outline welcome-back" onClick={() => useApp.setState({ startOpen: false })}>
        <span aria-hidden="true">{"\u2190"}</span> {t("startBack")}</button>}
      <div className={`welcome-card${examples.length ? " with-examples" : ""}`}>
        <svg className="trace" viewBox="0 0 220 64" aria-hidden="true">
          <path d="M0 40 C 18 40, 22 14, 40 14 S 62 54, 80 54 S 102 22, 120 22 S 142 46, 160 46 S 190 30, 220 30"
            fill="none" stroke="var(--muted)" strokeWidth="2" strokeLinecap="round" />
          <line x1="132" y1="2" x2="132" y2="62" stroke="var(--amber)" strokeWidth="1.6" />
          <rect x="133" y="2" width="34" height="13" fill="var(--amber)" />
        </svg>
        <h1>{t("dropTitle")}</h1>
        <p className="tagline">{t("welcomeTagline")}</p>
        <p>{t("dropHint")}</p>
        <button className="btn primary lg" onClick={() => useApp.setState({ browserOpen: true })}>
          <Icon.Folder /> {t("openFiles")}
        </button>
        {/* D11: where you left off comes before the examples - a returning user's first need */}
        {(files.length > 0 || sessions.length > 0) && (
          <div className="recent">
            {list(t("recentFiles"), files, <Icon.File />)}
            {list(t("recentSessions"), sessions, <Icon.Open />)}
          </div>
        )}
        {examples.length > 0 && (
          <>
            {/* cards, not a line of links: the line did not wrap and its last example (the
                Investigate one) ran off the screen below 1920 px */}
            <h2 className="examples-title eyebrow">{t("startFromExample")}</h2>
            {/* review (owner, 2026-11-13: a clear demo for everything): grouped by the area each one shows */}
            {EXAMPLE_GROUPS.map((g) => {
              const xs = examples.filter((ex) => FEATURED.includes(ex.id) && (ex.open === "sweep" || ex.open === "study" ? "sweeps" : "recordings") === g.area)
                .sort((a, b) => FEATURED.indexOf(a.id) - FEATURED.indexOf(b.id));
              return xs.length > 0 && (
                <section key={g.area} className="examples-group" aria-label={t(g.label)}>
                  <h3 className="examples-group-title"><span className="eyebrow">{t(g.label)}</span><span className="hint">{t(g.hint)}</span></h3>
                  <div className="examples-line">{xs.map((ex) => <ExampleCard key={ex.id} ex={ex} />)}</div>
                </section>
              );
            })}
            <p className="hint examples-more">{t("examplesMore")}</p>
          </>
        )}
      </div>
    </div>
  );
}
