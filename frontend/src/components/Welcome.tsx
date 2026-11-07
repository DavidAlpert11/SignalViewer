/* The welcome screen with no file open: what the app is for, open files, the examples (A3: moved
   out of App.tsx with the examples' labels). */
import { useEffect, useState } from "react";
import { api, type ExampleId } from "../api";
import { useApp } from "../store";
import { useT } from "../i18n";
import { Icon } from "../icons";
import { addDataExts } from "../values";
import { applyState, openPaths, startRetarget } from "../files";

const EXAMPLE_LABEL = { flight: "exampleFlight", twoFlights: "exampleTwoFlights", car: "exampleCar", ardupilot: "exampleArdupilot", simVsFlight: "exampleSimVsFlight", investigate: "exampleInvestigate" } as const satisfies Record<ExampleId, string>;
const EXAMPLE_DESC = { flight: "exampleFlightDesc", twoFlights: "exampleTwoFlightsDesc", car: "exampleCarDesc", ardupilot: "exampleArdupilotDesc", simVsFlight: "exampleSimVsFlightDesc", investigate: "exampleInvestigateDesc" } as const satisfies Record<ExampleId, string>;
const EXAMPLE_ICON = { flight: Icon.Globe, twoFlights: Icon.Compare, car: Icon.Table, ardupilot: Icon.Log, simVsFlight: Icon.Analysis, investigate: Icon.Search } satisfies Record<ExampleId, unknown>;


export default function Welcome() {
  const t = useT();
  const items = useApp((s) => s.recent);
  useEffect(() => { api.recent().then((r) => useApp.setState({ recent: r.items })).catch(() => {}); }, []);
  // T09: ready examples (a drone flight; three car runs to compare) - a first look in one click
  const [examples, setExamples] = useState<{ id: ExampleId; paths: string[] }[]>([]);
  useEffect(() => { api.examples().then(setExamples).catch(() => setExamples([])); }, []);
  // T60: files of the user's own readers can be chosen and dropped like the built-in types
  useEffect(() => { api.readers().then((r) => addDataExts(r.readers.flatMap((x) => x.extensions))).catch(() => {}); }, []);
  const files = items.filter((x) => x.kind === "file").slice(0, 6);
  const sessions = items.filter((x) => x.kind === "session").slice(0, 4);
  const openRecent = async (x: (typeof items)[number]) => {
    if (!x.exists) return;
    if (x.kind === "file") openPaths([x.path]);
    else {
      try { const r = await api.loadSession(x.path); await applyState(r.state, { announce: true }); }
      catch (e) { useApp.getState().toast({ kind: "error", text: String((e as Error).message) }); }
    }
  };
  const forget = async (path: string) => useApp.setState({ recent: (await api.forgetRecent(path)).items });
  const list = (title: string, xs: typeof items, icon: React.ReactNode) => xs.length > 0 && (
    <div className="recent-col">
      <h3>{title}</h3>
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
  return (
    <div className="welcome">
      <div className="welcome-card">
        <svg className="trace" viewBox="0 0 220 64" aria-hidden="true">
          <path d="M0 40 C 18 40, 22 14, 40 14 S 62 54, 80 54 S 102 22, 120 22 S 142 46, 160 46 S 190 30, 220 30"
            fill="none" stroke="var(--muted)" strokeWidth="2" strokeLinecap="round" />
          <line x1="132" y1="2" x2="132" y2="62" stroke="var(--amber)" strokeWidth="1.6" />
          <rect x="133" y="2" width="34" height="13" fill="var(--amber)" />
        </svg>
        <h1>{t("dropTitle")}</h1>
        <p className="tagline">{t("welcomeTagline")}</p>
        <p>{t("dropHint")}</p>
        <button className="btn primary" style={{ height: 36, paddingInline: 16 }} onClick={() => useApp.setState({ browserOpen: true })}>
          <Icon.Folder /> {t("openFiles")}
        </button>
        {examples.length > 0 && (
          <>
            {/* cards, not a line of links: the line did not wrap and its last example (the
                Investigate one) ran off the screen below 1920 px */}
            <h2 className="examples-title">{t("startFromExample")}</h2>
            <div className="examples-line">
              {examples.map((ex) => {
                const Ico = EXAMPLE_ICON[ex.id];
                return (
                  <button key={ex.id} className="ex-card" onClick={() => openPaths(ex.paths, undefined, { autoView: true })}>
                    <Ico width={18} height={18} />
                    <span className="ex-text"><span className="ex-title">{t(EXAMPLE_LABEL[ex.id])}</span>
                      <span className="ex-desc">{t(EXAMPLE_DESC[ex.id])}</span></span>
                  </button>
                );
              })}
            </div>
          </>
        )}
        {(files.length > 0 || sessions.length > 0) && (
          <div className="recent">
            {list(t("recentFiles"), files, <Icon.File />)}
            {list(t("recentSessions"), sessions, <Icon.Open />)}
          </div>
        )}
      </div>
    </div>
  );
}
