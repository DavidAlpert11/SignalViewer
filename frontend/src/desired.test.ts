// P: the one detector of commanded / measured pairs - on real ArduPilot (examples/copter_flight.bin) and PX4 names
import { expect, test } from "vitest";
import { actualNames, setpointPairs, setpointsIn } from "./desired";
import { actions, useApp } from "./store";
import { reset, run } from "./test/fixtures";

const COPTER: string[] = ["ATT.DesRoll [deg]", "ATT.Roll [deg]", "ATT.DesPitch [deg]", "ATT.Pitch [deg]", "ATT.DesYaw [deg]", "ATT.Yaw [deg]", "ATT.AEKF", "BARO[0].Alt [m]", "BARO[0].Press [Pa]", "BARO[0].Temp [degC]", "BAT[0].Volt [V]", "BAT[0].VoltR [V]", "BAT[0].Curr [A]", "BAT[0].CurrTot [Ah]", "BAT[0].EnrgTot [Wh]", "CTUN.ThI", "CTUN.ThO", "CTUN.ThH", "CTUN.DAlt [m]", "CTUN.Alt [m]", "CTUN.BAlt [m]", "CTUN.DCRt [m/s]", "CTUN.CRt [m/s]", "EV.Id", "GPS[0].Status", "GPS[0].GMS [s]", "GPS[0].GWk", "GPS[0].NSats [satellites]", "GPS[0].HDop", "GPS[0].Lat [deg]", "GPS[0].Lng [deg]", "GPS[0].Alt [m]", "GPS[0].Spd [m/s]", "GPS[0].GCrs [deg]", "GPS[0].VZ [m/s]", "GPS[0].U", "IMU[0].GyrX [rad/s]", "IMU[0].GyrY [rad/s]", "IMU[0].GyrZ [rad/s]", "IMU[0].AccX [m/s/s]", "IMU[0].AccY [m/s/s]", "IMU[0].AccZ [m/s/s]", "MODE.Mode", "MODE.ModeNum", "MODE.Rsn", "MSG.Message", "POWR.Vcc [V]", "POWR.VServo [V]", "RATE.RDes [deg/s]", "RATE.R [deg/s]", "RATE.PDes [deg/s]", "RATE.P [deg/s]", "RATE.YDes [deg/s]", "RATE.Y [deg/s]", "RCIN.C1 [PWM]", "RCIN.C2 [PWM]", "RCIN.C3 [PWM]", "RCIN.C4 [PWM]", "RCOU.C1 [PWM]", "RCOU.C2 [PWM]", "RCOU.C3 [PWM]", "RCOU.C4 [PWM]", "VIBE[0].VibeX [m/s/s]", "VIBE[0].VibeY [m/s/s]", "VIBE[0].VibeZ [m/s/s]", "VIBE[0].Clip", "XKF3[0].IVN [m/s]", "XKF3[0].IVE [m/s]", "XKF3[0].IVD [m/s]", "XKF4[0].SV", "XKF4[0].SP", "XKF4[0].SH", "XKF4[0].SM"];
const ids = (names: string[], run = "a") => names.map((n) => `${run}/${n}`);
const pairs = (names: string[]) => setpointPairs(ids(names)).map((p) => [p.setpoint.slice(2), p.measured.slice(2)]);

test("ArduPilot copter: attitude and rate setpoints, nothing else", () => {
  expect(pairs(COPTER)).toEqual([
    ["ATT.DesRoll [deg]", "ATT.Roll [deg]"], ["ATT.DesPitch [deg]", "ATT.Pitch [deg]"], ["ATT.DesYaw [deg]", "ATT.Yaw [deg]"],
    ["RATE.RDes [deg/s]", "RATE.R [deg/s]"], ["RATE.PDes [deg/s]", "RATE.P [deg/s]"], ["RATE.YDes [deg/s]", "RATE.Y [deg/s]"],
  ]);
});

test("PX4 and the owner's words: prefix or suffix, separator or camel case", () => {
  expect(pairs(["vehicle_attitude_setpoint.roll_body", "vehicle_attitude.roll_body", "rate.roll_sp", "rate.roll",
    "vehicle_local_position_setpoint.x", "vehicle_local_position.x"])).toEqual([
    ["vehicle_attitude_setpoint.roll_body", "vehicle_attitude.roll_body"], ["rate.roll_sp", "rate.roll"],
    ["vehicle_local_position_setpoint.x", "vehicle_local_position.x"]]);
  for (const [sp, m] of [["roll_cmd", "roll"], ["ROLL_CMD", "ROLL"], ["cmd_roll", "roll"], ["RollCommanded", "Roll"], ["desiredRoll", "roll"],
    ["TargetAlt", "Alt"], ["alt_tgt", "alt"], ["speed-ref", "speed"], ["PitchReference", "Pitch"], ["yaw setpoint", "yaw"],
    ["SetPointYaw", "Yaw"], ["thrust_demand", "thrust"], ["TECS.hdem", "TECS.h"], ["TECS.spdem", "TECS.sp"], ["pos_set", "pos"]])
    expect(pairs([sp, m])).toEqual([[sp, m]]);
});

test("no pair without the measured partner, in another file, or from look-alike names", () => {
  expect(pairs(["ATT.DesRoll", "RATE.Roll"])).toEqual([]);
  expect(setpointPairs([...ids(["ATT.DesRoll"], "a"), ...ids(["ATT.Roll"], "b")])).toEqual([]);
  expect(pairs(["ARSP.Offset", "ARSP.Off", "GPS.Spd", "GPS.S", "XKF4.SP", "XKF4.S", "modes", "mo"])).toEqual([]);
  expect(actualNames("ATT.Roll")).toEqual([]);
});

test("a plot draws its setpoints dashed only beside their measured value", () => {
  const sig = (s: string) => ({ sig: s, color: "#000000", width: 1, scale: 1, offset: 0 });
  expect([...setpointsIn([sig("a/ATT.DesRoll [deg]"), sig("a/ATT.Roll [deg]"), sig("a/RATE.RDes [deg/s]")])]).toEqual(["a/ATT.DesRoll [deg]"]);
});

test("Plot the commanded / measured pairs: a new tab, a plot per pair, one Undo; none: no step", () => {
  reset([run("a", COPTER)]);
  const tabs = useApp.getState().ws.tabs.length;
  expect(actions.plotSetpointPairs()).toBe(6);
  const tab = useApp.getState().ws.tabs.at(-1)!;
  expect(useApp.getState().ws.tabs.length).toBe(tabs + 1);
  expect(tab.plots.map((p) => p.signals.map((s) => s.sig))[0]).toEqual(["a/ATT.Roll [deg]", "a/ATT.DesRoll [deg]"]);
  expect(tab.plots.length).toBe(6);
  useApp.getState().undo();
  expect(useApp.getState().ws.tabs.length).toBe(tabs);
  reset([run("b", ["IMU.GyrX", "IMU.GyrY"])]);
  const past = useApp.getState().past?.length;
  expect(actions.plotSetpointPairs("b")).toBe(0);
  expect(useApp.getState().past?.length).toBe(past);
});

// RE2: the same cases as the Python twin (backend/svcore/reportparts.py, backend/tests/test_report_parts.py)
import CASES from "../../backend/tests/data/setpoint_cases.json";
test("the shared cases: desired.ts and svcore/reportparts.py find the same pairs", () => {
  for (const c of CASES.cases) expect(pairs(c.names), c.why).toEqual(c.pairs);
});
