/* CC16: the examples by task, for Help -> Examples (generic first, the flight logs last). */
import type { ExampleId } from "./api";
import type { TKey } from "./i18n";

/** CC16: Help -> Examples by what the user wants to do (a task each, the flight logs last). */
export const EXAMPLE_TASKS: { label: TKey; ids: ExampleId[] }[] = [
  { label: "exTaskVerify", ids: ["servoStep", "processPlant", "bench"] },
  { label: "exTaskSimVsTest", ids: ["cruiseSimVsTest", "simVsFlight"] },
  { label: "exTaskManyRuns", ids: ["monteCarlo", "sweepTable", "commonGains", "smartSweepDemo", "folderOfFlights"] },
  { label: "exTaskLook", ids: ["automations", "car", "investigate", "reportDemo"] },
  { label: "exTaskBytes", ids: ["serialLink", "linkStructure", "channel", "gpsNmea"] },
  { label: "exTaskFlight", ids: ["ardupilot", "flight", "twoFlights"] },
];
