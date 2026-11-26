# Name your signals

Signal Viewer finds several things in a recording **by the signal names alone** and offers each as one click: in
the file panel's **Found in this file** line (newest file first), in the file's right-click menu (*Found in this
file ▸*) and in the command palette (Ctrl+K, group *Found*). *Why?* on the line names the signals each find matched.

Record (or export) your signals with names like these and the app does the rest. The same table is in the app:
**Help → Name your signals**.

| What the app does | Names it recognises | For example |
|---|---|---|
| **Command and response** - a plot per pair, the command dashed beside what it got; Checks' tracking metrics; the report's `[[tracking]]` | the same name with a command word before or after it (after `_` `-` `.` or in camel case), in the same file: commanded, reference, setpoint, command, desired, demand, target, des, dem, cmd, tgt, ref, set, sp | `ctrl.roll_cmd` / `ctrl.roll`, `DesRoll` / `Roll`, `alt.target` / `alt` |
| **Objects on the map** | a group with a latitude and a longitude (`lat`, `latitude` / `lon`, `lng`, `long`, `longitude`), with `alt` and `roll` / `pitch` / `yaw` (or a quaternion) when you have them; or north / east / down in metres with an origin | `uav.lat`, `uav.lon`, `uav.alt`, `uav.att.roll` |
| **Truth vs navigation errors** - both on a map and *Compare objects…* opened on them: position, velocity and attitude errors with their statistics; the report's `[[navigation]]` | two such groups of the same platform: one named as the truth (`truth`, `true`, `6dof`, `physics`, `phys`, `groundtruth`, `sim`, `model`, `plant`, `dyn`), one as the navigation system (`nav`, `navigation`, `ins`, `ekf`, `ahrs`, `est`, `kf`, `filter`, `fusion`). Same platform: the same name once those words are taken out (`uav1.truth` / `uav1.nav`), or one truth in the file. Add `vel.n` / `vel.e` / `vel.d` and `att.roll` / `pitch` / `yaw` to both for velocity and attitude errors | `6dof.lat` / `ins.lat`, `physics.lat` / `nav.lat` |
| **Modes as bands** over the time plots | a column of text values (or a signal whose values have names) | `mode` = TAKEOFF, CLIMB, CRUISE |
| **Sensors in several copies** - a plot per field with every copy, so the one that disagrees shows | the same fields under a group with a number: `[0]` / `[1]`, or `1` / `2` when most of the fields are the same | `imu[0].ax` / `imu[1].ax`, `baro1.alt` / `baro2.alt` |
| **Actuators and saturation** | `u`, `effort`, `actuator`, `motor`, `servo`, `valve`, `throttle`, `pwm`, `duty`, `torque`, `output` | `act.servo_elevator`, `act.throttle` |
| **Byte columns → messages** | columns `byte_0` … `byte_N` (one message per row) | `byte_0`, `byte_1`, … |
| **Many runs as an envelope** | three or more open files with the same signal names | `run_001.csv`, `run_002.csv`, `run_003.csv` |

## A header that unlocks all of them

```
time,mode,6dof.lat,6dof.lon,6dof.alt,6dof.att.roll,6dof.att.pitch,6dof.att.yaw,6dof.vel.n,6dof.vel.e,6dof.vel.d,
ins.lat,ins.lon,ins.alt,ins.att.roll,ins.att.pitch,ins.att.yaw,ins.vel.n,ins.vel.e,ins.vel.d,
ctrl.roll_cmd,ctrl.roll,ctrl.alt_cmd,ctrl.alt,ctrl.speed_cmd,ctrl.speed,
imu[0].ax,imu[0].ay,imu[0].az,imu[1].ax,imu[1].ay,imu[1].az,act.servo_elevator,act.throttle
```

The example recording made this way: **Help → Examples → what the app finds by itself** (or *Open the example
recording* in *Name your signals*) - `examples/automations/platform_run.csv`, written by
`tools/make_automations_example.py`: a 6-DOF truth and an INS of the same platform (the INS drifts), three commands
and their responses, the flight phase as a text column, an accelerometer in two copies (the second drifts away after
150 s) and two actuators (the throttle saturates in the climb).
