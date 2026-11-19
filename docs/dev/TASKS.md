# Work queue and handoff

The **active work queue**: what is open, the specs waiting for the owner, and a short log, so any developer or agent
can pick up cold. Every rule and practice (how to work, test, release, and the prompt to start a session) is in
`/CLAUDE.md`; `ROADMAP.md` is the catalogue (every task ID, ticked `[x]` when done).

History: the log and the notes of earlier rounds are in git - `git show 4f514f27:docs/dev/TASKS.md` (1.29.1 - 1.32.0:
CL2, CP1, CP2, RE1, RE2), `git show 7b16eef:docs/dev/TASKS.md` (up to 1.29.0 and the README / docs-site work),
`git show 6477fd8:docs/dev/TASKS.md` (up to 1.28.0). The removed planning files (the 2026-11-16 review, the modeFRONTIER research, the navigation sketch, the
e2e map, the outreach steps): `git show 7b16eef:docs/dev/<name>`.

**Keep this file current** after every finished task (or when you stop in the middle): "Current state", the
task ticked in `ROADMAP.md`, the user-facing line in `CHANGELOG.md`, and a line in the Log.

---

## Current state

| Task | Status | Next step |
|---|---|---|
| M34 FR9 - quick_check + the short e2e list in CI on every push | owner: not now | - |
| SW2 (b) - Run again with recording | spec agreed in parts | the owner's final yes on "Open specs" below - do not implement before |
| BR1 - the app as one process (README, docs home, welcome groups) | proposed | the owner's yes on the wording below |
| Stability on Windows with a GPU (Out of Memory, the 3D shader) | waiting for numbers | the owner runs `tools/measure_maps.py --gpu`; the e2e suite's memory |
| Films in Hebrew + a narration script; GitHub About texts | offered / with the owner (About texts proposed 2026-11-17) | his choice; he pastes the About texts |
| Known gap - the 2D double-click on a map object has no e2e test | open | add one when the Map is next touched |
| Release 1.32.0 - RE2 ready reports made of parts (owner, 2026-11-19) | in main; version, CHANGELOG, README, docs, pictures 48-51, the agent's cleanup and skills | the owner checks, deletes the old branches and tags v1.32.0 (the commands were given) |
| Reports - open work | see `docs/dev/REPORTS.md` "Open" | the CLI making the written report; RE2.6 block editor; RE2.7 |
| MSG1 - byte-stream messages: a dedicated plot and a report (owner, 2026-11-19) | built 2026-11-19 (pushed before the checks, owner's word); + the owner's TX / RX demos | checks / e2e, then fix |
| CLR1 - Clear and the report (owner, 2026-11-19: "when the recording is cleared, what happens to the report? how is it cleared?") | done (2026-11-19): the proposal below built | the owner looks |
| README review for 1.32 (owner, 2026-11-19: "update the README") | the RE2 lines are in; a full pass not done | do the full pass before the owner tags v1.32.0 |
| Load: the e2e under heavy parallel load (5 browsers on 4 cores) still time out now and then (open_files > 30 s) | known | only under that load; the suite one file at a time is green |

## Open specs (waiting for the owner)

- **MSG1 - messages in a byte stream (owner, 2026-11-19, Hebrew, translated):** *"Say we put in signals of messages that
  repeat: header1, header2, sometimes the next byte is the message size or type, then more details, and at the end
  sometimes a checksum. If such signals of a message, byte by byte over time, are recognised - make the app produce a
  dedicated plot for it, and a report that characterises what happens: the number of messages, the order of the
  messages, the packet size, etc. A report for that too."* The agent's design (2026-11-19, the owner left the details):
  - `backend/svcore/bytestream.py` (pure, tested): input a byte stream (t, y: integers 0..255) - one signal byte by
    byte, or several column signals `byte_0..byte_N` / `b[0]..` / `data0..` (one message per row, NaN = no byte) joined
    row by row into one stream. **Framing found by itself:** the header = the 2-byte pair that recurs (top ~20 pairs by
    count, scored by how well it frames: a length byte at offset 2-4 that equals the frame length minus a constant in
    >= 70 % of frames, else frames whose type byte decides their length); walk with the length field and resync to the
    next header after a bad frame (count resyncs, bytes outside frames). **Type** = the byte at offset 2-4 (not the
    length) with few values (<= 32) that best decides the length. **Checksum** = the last 1 or 2 bytes, schemes tried:
    sum8, xor8, -sum8, ~sum8 over the frame with / without the header, CRC-16 CCITT-FALSE / Modbus, Fletcher-16 (UBX);
    the one that matches >= 80 % is reported, its failures counted. Options to force any of it (`header AA55`,
    `length 2`, `type 3`, `checksum sum8`). Output: messages [{t (first byte), i, len, type, ok}], per type: count,
    share, lengths, rate (Hz), period and jitter, first / last time, checksum errors; the order - the smallest period p
    with types[i] == types[i+p] for >= 90 % (the repeating sequence), else the commonest transitions; the largest gaps.
    Every number on every byte (CLAUDE.md).
  - **The dedicated plot:** a derived operation `messages` (svcore/analysis.py, beside `relate`: params `{what: type |
    length | ok | interval | count, header?, ...}`, one derived signal per what, at the messages' times) - so it is in
    the session and Undo like any made signal; the signal list's right-click **Decode as messages...**
    (components/DataPanel.tsx sigMenu1; for several selected column signals too) makes them and a tab "Messages: <sig>"
    with one plot each: the raw bytes, the type (a state), the length, the interval, the checksum errors
    (`plotActions.plotTabs`; relation.ts makeGroup is the pattern). Not a byte stream: an error saying why.
  - **The report part** `[[messages]]` / `[[messages <signal>]]` (skill `sv-report-part`): the framing found, a table per
    type, the order, gaps, highlights (checksum errors, gaps -> warn), the plots one per quantity; `scan()` lists the
    streams found (prefilter: int 0..255, >= 8 distinct values, framing succeeds); the library's category *Messages
    (byte streams)*; a ready report includes it when found; `[[overview]]` should not list a byte stream's statistics
    as if it were a measurement (say "a byte stream - see Messages").
  - **Demo:** a serial link recording in `examples/report_demo/` (skill `sv-example`): header AA 55, a length byte, a
    type byte, payload, sum8 checksum; types at 50 / 10 / 1 Hz; a few corrupted bytes and a dropout; and the same as
    columns (one message per row). Help -> Examples. Docs: `docs/reports.md`, a feature line, CHANGELOG (1.32.0 is not
    tagged yet - it may go into 1.32.0 if the owner agrees, else `## Next`).
- **CLR1 - Clear and the report (studied 2026-11-19):** the Clear menu (`frontend/src/clearing.ts clearMenuItems`:
  this tab / other tabs / all tabs / the work / everything) never touches `ws.report` except *Clear everything* (a new
  workspace: the report gone too). So after *Clear all tabs* the report keeps `[[tab.plot]]` references to tabs that
  are gone (red ⚠ in the preview) and there is no way to empty only the report but select-all + delete in the editor
  (the Report screen's ↺ goes back to the report made from the open tabs). Proposed: the Clear menu gets **The report**
  (empties `ws.report.doc` and its pictures, one Undo, asks first when it has text); *Clear all tabs* says in its
  toast that the report's references to those tabs are now broken, with *Clear the report too*; the Report screen's
  ↺ menu: *Empty* / *Back to the report from the tabs*. **Built 2026-11-19** as proposed (`clearing.ts clearReport`,
  `reportTabRefs`; also *All tabs, notes, derived signals* says it; Ctrl+K "Clear: The report"); e2e
  test_report_doc::test_clear_and_the_report.
- **Reports (RE1 1.31.0, RE2 1.32.0)** - how they work, every decision and what is open: `docs/dev/REPORTS.md`.
- **SW2 - the owner (2026-11-16): investigate chosen scenarios from Sweeps without loading everything.** "Many
  scenarios are run without recording, only a summary row each; to investigate, the interesting ones are run again
  with recording." Two ways from a set / selected rows of a Sweeps table, both on demand only (never load all):
  (a) open their recordings directly when they exist (exists: *Where are the runs' recordings?* / a `recording`
  column - make it one click for several rows: open them together in Recordings, Compare); (b) **Run again with
  recording**: the same inputs, written to one JSON file per run with `"record": "<path>"` added (a time-series
  file to write besides the summary row), run through the study's own way to run (this PC / the wrapper / the farm),
  then the recordings opened together in Recordings. Contract (document it in sweep_wrapper.py, the README,
  docs/launcher.md): a simulation that sees "record" writes its full time series there (CSV or any format the app
  reads); the wrapper gets `--record DIR` (record = DIR/<run_id>.csv) for hand runs; in a study the record path is a
  placeholder `{{record}}` the params template may use (the auto template adds it only for a recording run). The
  demo: sim.py writes a time series when asked (the closed-form attitude step response: t, roll command, roll,
  motor), so in the smart-sweep demo the best set -> *Run again with recording* -> its runs open in Recordings
  (one per scenario, compared). One home for the button: the set's details (SetDetail) and the re-run list
  (RerunList: today only Export) - not a third place. en + he, RTL; backend tests for the contract, e2e for the demo.
  **SW2 status:** (a) done by FL1 (the Sweeps data table's ticks + *Open n in Recordings*). **The owner's answers (2026-11-16, chat) for (b):** (1) which runs record is a **rule set in advance**, default *no recording*; (2) a simulation file takes **one run**, the wrapper **a parameter set** - choose accordingly; (3) the re-runs are **chained**, then a notice says a run is **ready to load** (not opened by itself); (4) a re-run whose summary row differs from the original is **loaded as another layer of results**.
- **SW2 (b) - the proposal, waiting for the owner's final yes (2026-11-16):**
  - A run = one row (inputs + summary outputs); a recording = its full time series. Default: **no recording**.
  - **When to record = a rule set in advance** (Set up, beside *How to run*): none (default) / a rule on inputs or
    outputs (`wind >= 10`, `overshoot > 8`, *every failed run*) / always. Runs the rule picks are **chained**: after the
    summary run they run again with recording by themselves.
  - **What is sent:** the same inputs + `"record": "<path>"`. A simulation file takes **one run** per call; a wrapper takes
    **a parameter set** (its runs in one list). Through the study's own way to run (this PC / wrapper / farm).
  - **Files (the owner's contract):** each run writes `statistic_<id>` (its summary row) and `record_<id>` (its
    recording); one common prefix per kind; both in one folder or each in its own (configurable). At the end the
    wrapper merges every `statistic_<id>` into ONE statistics table - deleting the single-row files by default (an
    option keeps them). Today's results glob (`results/{{table}}/{{run_id}}.csv`) and the demo keep working.
  - **When done:** a notice *N recordings ready* with *Open* - nothing opens by itself; each recording is linked to its
    row (same inputs), a row with a recording shows an icon; rows -> *Open in Recordings* together (FL1's ticks).
  - **A re-run's summary row that differs from the original** (noise, another sim version) is **loaded as another layer
    of results** (rounds already accumulate as layers: next/round_*/collected_<table>.csv) - the original kept.
  - Also by hand: rows / a group / a set (scenarios removable in its details) into the existing re-run list (RerunList),
    which shows the count, an estimate and where the files go - not a new place.
  Touches: study.Launcher (+ optional `record` rule, statistic / record prefixes and folders, keep singles), launcher.py
  (write_params `{{record}}`, chained record round, merge), sweep_wrapper.py (`--record DIR`, the merge), sim.py (a time
  series when asked), SetDetail / RerunList / Set up UI, README, docs/launcher.md.
- **BR1 - the owner's idea (2026-11-16): brand the tool as one process.** Proposed (in Hebrew to him): "Signal Viewer -
  from one run to a whole sweep, in one place, offline": 1. a run (open, look, find what went wrong); 2. runs (a folder
  of recordings or simulations -> one table, a row each, back to the recording); 3. a sweep (which parameters hold in
  every scenario, the next runs, a re-run with recording for the interesting ones). Waits for his yes; then README,
  docs/index.md and the welcome screen's groups.

## Log

- 2026-11-19 · MSG1: svcore/bytestream.py (framing found by itself, resync, a direction column), the op `messages`, *Decode as
  messages…* (a tab: bytes, type, length, interval, checksum ok), `[[messages]]` + *Link review*, `[[overview]]` leaves byte
  streams out, demo examples/serial_link (owner, mid-task: TX and RX as two signals; one signal mixed with a dir column; a report
  with plots). Decisions: the demo is its own example (not in report_demo, whose automatic report would get a link section);
  Fletcher-16 is UBX's (wraps at 256); a heartbeat breaking the order still lets the 6-message sequence stand (>= 90 %);
  CHANGELOG lines in 1.32.0 (not tagged yet - move to Next if the owner prefers). Pushed first, checks after (owner's word).
  The owner then asked how a signal is defined as messages - only TX, only RX, or both with a direction column: the dialog
  *Decode as messages* (components/MessagesDialog.tsx) keeps `ws.messageStreams` (sources, carries, dir, txValue, header,
  checksum; optional field, old sessions unchanged), sent with [[messages]] and the library's scan. And (owner): the
  packet's make-up as a table (fixed header, length / type byte and its kinds, payload per kind, checksum or none) and the
  messages in order (the first 40 + a plot of the type over the first 2 s).
- 2026-11-19 · CLR1: Clear → *The report* (text + pictures, asks when written, one Undo), the clear-tabs toasts say when the
  written report points at the cleared tabs (+ *Clear the report too*), the Report screen's ↺ menu (*Empty* / *Back to the
  report from the tabs*). e2e: test_report_doc (3), test_features -k clear (5).
- 2026-11-19 · RE2 (1.32.0): ready reports made of ready-made parts - tracking, navigation, states, trajectory (a map), moments,
  differences (overall / in its region, the central region, first divergence), overview (any recording), summary, toc; the library
  (categories, guessed reference / baseline, my report templates, my parts); paste tables / pictures; a template carries its report;
  the demo (examples/report_demo, Help -> Examples). Whole e2e one file at a time: 512 passed (two Sweeps files failed while the UI
  was rebuilt during the run; alone green). Merged into main on the owner's word. Details: `git show 4f514f27:docs/dev/TASKS.md`.
- 2026-11-19 · Cleanup (owner, before the release): the two report plans merged into `docs/dev/REPORTS.md`, this file trimmed,
  the PR template's i18n path fixed; project skills in `.claude/skills/` (checks, release, report part, media); README reviewed.
