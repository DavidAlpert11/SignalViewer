# Outreach - the owner's steps (Q84 / T67)

Signal Viewer works; what holds adoption back now is that people do not find it (0 stars, the
repository page has no description, Google shows "Contribute to DavidAlpert11/SignalViewer
development…"). None of this can be done from a patch - it needs the owner's account.

## Once, on GitHub (10 minutes)

```bash
gh repo edit DavidAlpert11/SignalViewer \
  --description "Offline desktop app to plot, compare and report on flight logs, test runs and simulation data - ArduPilot, PX4, MAVLink, MATLAB, CSV, CAN; pass / fail in CI" \
  --homepage https://davidalpert11.github.io/SignalViewer/ \
  --enable-discussions \
  --add-topic ardupilot,px4,mavlink,flight-test,flight-log,drone,uav,telemetry,time-series,data-visualization,signal-processing,can-bus,simulink,matlab,ros2,log-analysis,offline
```

- **Social preview:** Settings → General → Social preview → upload `docs/images/social-preview.png`
  (tools/make_social_preview.py). Without it a shared link shows GitHub's generic card.
- **Private vulnerability reporting:** Settings → Code security → *Private vulnerability
  reporting* → Enable (SECURITY.md and the issue chooser link to it).
- **Labels** used by the issue forms: `bug`, `enhancement` exist by default; add `good first issue`
  and put it on two or three small issues (a reader for a format someone asked for is a good one).
- **Release notes:** the 1.10.0 release body could open with the GIF of comparing runs
  (`docs/media/03_compare_runs.gif`) - the release page is where the Download button leads.

## Where the users are (one post each, spread over a few weeks)

Lead with one concrete problem and one picture, not the feature list. Answer every reply in the
first two days. Order by fit:

1. **ArduPilot Discourse** (*Blog* or *Ground Control Software*) - draft below.
2. **PX4 Discuss** (*Flight Testing* / *Log analysis*) - the same draft with a .ulg picture.
3. **r/diydrones**, **r/ardupilot** - the short draft.
4. **ROS Discourse** (*General*): reading .mcap with no ROS install, comparing bag recordings.
5. **Show HN** - when the CI badge has been green for a while: *"Show HN: Signal Viewer - offline
   viewer to compare flight logs and test runs, with pass/fail for CI"*.
6. **Documentation PRs:** the ArduPilot wiki and the PX4 user guide each have a page that lists
   log-analysis tools - a one-line PR adding Signal Viewer (offline, several flights side by side)
   is a permanent link from where people look.
7. **awesome-lists** for drones / robotics / ROS 2 / time-series visualisation (search GitHub for
   them; add a line where Signal Viewer fits, never as spam).
8. Hebrew: the local drone / UAV engineering groups (WhatsApp, Facebook, LinkedIn), with the
   Hebrew guide - the app is one of very few with a full Hebrew UI.

### Draft - ArduPilot Discourse

> **Signal Viewer: compare flights side by side, offline, with pass / fail for CI**
>
> I fly the same test card again and again and wanted one thing UAV Log Viewer and Mission Planner
> don't do: open five flights at once and see which signal changed. So I built Signal Viewer
> (MIT, Windows / Linux / macOS, `pip install signalviewer`).
>
> - Open .bin, .tlog, .ulg directly; flight modes, events, parameters and a health check
>   (vibration, clipping, EKF, battery, motors) on the first open.
> - Compare runs: every shared signal ranked by how different it is, aligned in time, also per
>   flight-mode segment ("the 2nd AUTO of every flight").
> - Simulation vs flight: a SITL / Simulink .mat next to the .bin, aligned automatically.
> - Offline map and 3D globe - works on a closed network.
> - `signalviewer-cli check` / `compare` give exit codes and JUnit XML, so the same limits run in CI.
>
> [GIF: docs/media/03_compare_runs.gif]
>
> Download / docs: https://github.com/DavidAlpert11/SignalViewer - I'd love logs that it reads
> wrongly (Help → Report a problem).

### Draft - short (Reddit)

> I made a free offline app to compare ArduPilot / PX4 flight logs side by side - it ranks every
> signal by how much it changed between flights and aligns them in time. Also reads .tlog, .mat,
> CSV and CAN. [GIF] https://github.com/DavidAlpert11/SignalViewer - feedback welcome.

## Later (needs money or time, not code)

- **Code signing** (Q24): SignPath.io signs open-source Windows builds for free; an Apple
  Developer ID (paid) removes the macOS warning. docs/install.md says what to do until then.
- **A 60-90 s video** of sim vs flight (Q60) on YouTube, linked at the top of the README.
- **winget / Homebrew cask / conda-forge** packages, once the downloads show demand.
