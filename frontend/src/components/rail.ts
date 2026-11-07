/* The tool rail (A3: moved out of App.tsx): the side panels' buttons, in order. */
import type { Icon } from "../icons";
import type { PanelId } from "../store";
import type { TKey } from "../i18n";

/** the tool rail's width: an icon with its short name under it (the names made Investigate and Fleet findable) */
export const RAIL_W = 64;
export const RAIL: { id: PanelId; icon: keyof typeof Icon; key: "data" | "analysis" | "compare" | "report" | "flightLog" | "investigate"; short: TKey }[] = [
  { id: "data", icon: "Data", key: "data", short: "railData" },
  { id: "analysis", icon: "Analysis", key: "analysis", short: "railAnalysis" },
  { id: "compare", icon: "Compare", key: "compare", short: "railCompare" },
  { id: "investigate", icon: "Search", key: "investigate", short: "railInvestigate" },  // investigation step 2: named conditions
  { id: "report", icon: "Report", key: "report", short: "railReport" },
  { id: "log", icon: "Log", key: "flightLog", short: "railLog" },       // only while a file with a flight log is open
];
