/* The tool rail (A3: moved out of App.tsx): the side panels' buttons, in order. */
import type { Icon } from "../icons";
import type { PanelId } from "../store";
import type { TKey } from "../i18n";

/** the tool rail's width: an icon with its short name under it (the names made Investigate findable) */
export const RAIL_W = 64;
export const RAIL: { id: PanelId; icon: keyof typeof Icon; key: "data" | "analysis" | "compare" | "report" | "chkTitle" | "investigate" | "msgPanel"; short: TKey }[] = [
  { id: "data", icon: "Data", key: "data", short: "railData" },
  { id: "analysis", icon: "Analysis", key: "analysis", short: "railAnalysis" },
  { id: "compare", icon: "Compare", key: "compare", short: "railCompare" },
  { id: "investigate", icon: "Search", key: "investigate", short: "railInvestigate" },  // investigation step 2: named conditions
  { id: "messages", icon: "Messages", key: "msgPanel", short: "railMessages" },  // MSG3: byte streams, links, structures
  { id: "report", icon: "Report", key: "report", short: "railReport" },
  { id: "log", icon: "Log", key: "chkTitle", short: "railChecks" },     // D7: Checks for any open file (a log adds its events)
];
