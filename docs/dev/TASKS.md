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
| Release 1.34.0 - CP4 Send to Confluence, CP3 the user macro, HL1 linked zoom, RE4 the built-in LaTeX, MSG5-MSG9 messages (owner, 2026-11-22: "yes - then release") | PREPARING 2026-11-22: version in the five files + install.md, CHANGELOG 1.34.0 with highlights, README (English + Hebrew), limitations, validation page; the whole e2e running | the owner tags v1.34.0 |
| CP4 - Send to Confluence straight from the app (owner, 2026-11-22: "the most important now") | built 2026-11-22 (against a stand-in of Confluence's REST API; not yet against the owner's Confluence 10.2) | the owner: Settings -> Confluence (address + personal access token), Save and test, then a plot's ⋯ -> Send to Confluence…; if his Data Center keeps the HTML macro off, the Signal Viewer macro (CP3) |
| MSG8 - hex / numbers / ASCII, double, text fields, a conversion formula (owner, 2026-11-22) | built 2026-11-22 | the owner looks |
| MSG9 - the proposal (16-bit counter, double, text; no slow type byte, no 00 footer), *Not the type byte*, a wider panel (owner, 2026-11-22) | built 2026-11-22 | the owner looks |
| MSG7 - what passed in order, how often, and one message's variables (owner, 2026-11-22) | built 2026-11-22 | the owner looks (Messages → step 4) |
| MSG6 - the pauses in the stream tell a header from a footer (owner, 2026-11-22) | built 2026-11-22 (automatic when the stream has pauses; no switch) | the owner tries his stream that showed it; if his recording has no pauses (bytes back to back), say so - then only a checksum or his click tells them apart |
| MSG5 - any column with several values is the direction; the user picks TX and RX (owner, 2026-11-22) | built 2026-11-22 | the owner tries it on his own stream |
| CP3 - Copy for Confluence through the Signal Viewer user macro (owner, 2026-11-22: Confluence 10.2) | built 2026-11-22 (tested against a stand-in page; not against a real Confluence 10.2) | the owner's Confluence administrator installs the macro (Settings → Save the macro…); the owner tries a copy |
| HL1 - one zoom and one cursor for the HTML page's time plots (owner, 2026-11-22) | built 2026-11-22 | the owner looks (any report / tab saved as HTML, the 🔗 button) |
| Release 1.33.0 - MSG4 guided messages, RE3 LaTeX, the agent skills (owner, 2026-11-21: "a patch ready for a version") | READY 2026-11-21: version in the five files, CHANGELOG 1.33.0 with highlights, README (English + Hebrew) and docs (features, limitations, reports + reports.he LaTeX, messages, GUIDE.he messages), validation page, pictures 42 48-51 55-57, the whole e2e one file at a time (97 files, 526 passed, 1 failed: test_study_loop - fixed, then 18 / 18 green), quick_check, mkdocs --strict | the owner applies the patch, pushes, tags v1.33.0 |
| RE3 - LaTeX in the report, as in Overleaf, offline (owner, 2026-11-21) | built 2026-11-21 (tested with TeX Live 2023: XeLaTeX / pdfLaTeX; Hebrew in LaTeX not tested here - this container has no bidi.sty) | the owner tries a Hebrew report in LaTeX with his MiKTeX / TeX Live; next: SyncTeX, syntax colours, the CLI |
| MSG4 - from raw bytes to variables in four guided steps (owner, 2026-11-21) | built 2026-11-21 | the owner tries it on his own stream (Messages → open a stream); next: a field's bits from the byte menu, a checksum chosen by a click |
| M34 FR9 - quick_check + the short e2e list in CI on every push | owner: not now | - |
| SW2 (b) - Run again with recording | spec agreed in parts | the owner's final yes on "Open specs" below - do not implement before |
| BR1 - the app as one process (README, docs home, welcome groups) | proposed | the owner's yes on the wording below |
| Stability on Windows with a GPU (Out of Memory, the 3D shader) | waiting for numbers | the owner runs `tools/measure_maps.py --gpu`; the e2e suite's memory |
| Films in Hebrew + a narration script; GitHub About texts | the English training film is narrated (2026-11-20); a Hebrew voice is possible (Piper he_IL) | his choice; he pastes the About texts |
| Known gap - the 2D double-click on a map object has no e2e test | open | add one when the Map is next touched |
| Release 1.32.0 - RE2 ready reports + CLR1, MSG1, MSG2, LINK1, MSG3 (owner, 2026-11-20: "prepare a release") | READY 2026-11-20 except one e2e (MSG3 in, every picture refreshed, the whole e2e 96/97 files green, quick_check, mkdocs --strict); earlier: CHANGELOG 1.32.0 – 2026-11-20 with new highlights, CITATION date, README (bytes to signals: why, tour with pictures 52 / 53, formats, Hebrew), docs (messages.md, features, limitations, install counts, reports.he.md with the ready parts), pictures 52-54 | the owner tags v1.32.0 (commands given); the old claude/* branches are already gone from GitHub |
| Reports - open work | see `docs/dev/REPORTS.md` "Open" | the CLI making the written report; RE2.6 block editor; RE2.7 |
| MSG1 - byte-stream messages: a dedicated plot and a report (owner, 2026-11-19) | built and checked 2026-11-20 (+ the owner's additions: TX / RX, direction column, packet make-up, order, requests / replies, handshake) | the owner looks; left: matching a command with its effect in another signal |
| MSG2 - messages to signals: a structure (proposed or written) turns messages into a recording; NMEA (owner, 2026-11-20) | built 2026-11-20 (pushed before the e2e, owner's word) | the owner looks; next: bit fields in the form, arrays / repeated groups (GSV's satellites), a CLI |
| LINK1 - listen to a serial port / UDP / TCP, decoded live by a structure, recorded to a file (owner, 2026-11-20) | built 2026-11-20 | the owner tries it (tools/send_link_demo.py); next: a session that re-listens, a hex view of the raw bytes |
| MSG3 - one home for messages: the Messages panel + the structure library (owner, 2026-11-20) | built 2026-11-20 (see Open specs) | the owner looks |
| CLR1 - Clear and the report (owner, 2026-11-19: "when the recording is cleared, what happens to the report? how is it cleared?") | done (2026-11-19): the proposal below built | the owner looks |
| README review for 1.32 (owner, 2026-11-19 / 20: "update the README") | done 2026-11-20 | - |
| test_study_loop - a copy of the demo runs the loop: after a round, Results did not open (found 2026-11-20) | fixed 2026-11-21 (studyStore firstResultsIn put the screen back over the user's click; flowAsked) | - |
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
- **MSG1 - the owner's additions (2026-11-19, via another session; built the same day):** *"Sometimes part of the
  packet is TX / RX, or there is a column for the message's direction. Then there is a structure of a handshake,
  answers, reply packets... and maybe matching between different columns."* Built: direction (a direction column,
  or two signals TX / RX - the dialog's *only TX / only RX / both with a direction column / TX and RX one each*,
  `ws.messageStreams`); request / reply (`bytestream.exchange`: a reply type in the other direction within 0.5 s,
  0.5..1.5 per request, echoing a byte of the request >= 80 % - or a rare type (<= 10, a handshake's) always answered;
  streaming types have none; a type that answers is not a request the other way; a request sent again before its
  reply is a retry and the reply is the later copy's): answered / unanswered (times), retries, orphans, latency mean /
  95 % / max and when; the handshake: the rare messages of both directions grouped (<= 1 s apart), the first group
  the opening, later ones reconnects; the op `messages` what=latency (the tab's *Reply latency* plot). Demo: a
  handshake at 0 s and after the dropout, COMMAND / ACK with an echoed seq, 3 lost, 1 retry. **Left (not built):**
  matching between columns beyond the two directions (a command on the link and its effect in another signal -
  firstchange.lag), a direction lane / unanswered marks in the tab, a timeout option.
- **MSG3 - one home for messages and links (owner, 2026-11-20: "organise all the message data - MAVLink, NMEA, general
  messages - in one central place... a good design for everything") - BUILT 2026-11-20.** What was decided and why:
  1. **One side panel "Messages"** on the rail between Investigate and Report (a tool that needs room - CLAUDE.md §3).
     Sections: *Running now* (a link / MAVLink with their numbers - read-only: starting and stopping a live source stays
     in Live ▾, the one place for live sources), *Byte streams* (the open files' streams found by themselves or defined,
     each with count / header / checksum / types and rates; a click opens the stream editor in place: what it carries,
     the framing, the structure, *Plot the messages* / *Make the recording* / *Add to the report*), *Logs with messages*
     (MAVLink .tlog, .bin, .ulg, .mcap, link recordings and recordings made from messages: each message type's fields,
     count and rate - MAVLink in the same picture; a click plots a type) and *Structure library*.
  2. **The dialog is gone**: its contents (StreamEditor.tsx) live in the panel. The signal's right-click *Decode as
     messages…* stays as the second entry point and opens the panel on that signal (ui `msgFocus`); Ctrl+K → Messages.
  3. **One structure library** (app/routes/messages.py): NMEA built in + `~/.signalviewer/structures/*.svmsg.json`
     (Settings key `structuresDir` may move it) + the readers folder's ICD layouts read as structures. Offered in the
     stream editor (*From the library…*, *A structure file…*, *Save to the library* under a name) and in Live ▾ → Listen
     to a link. The old Load… / Save… / NMEA buttons became those two (one way to fetch, one way to keep).
  4. **A raw file**: a `.svraw` opened without its structure says so in a toast with a button to the panel on its bytes.
  5. Saved fields unchanged (`ws.messageStreams` as before); the report's `[[messages a, b]]` takes several names
     (*Add to the report* of a TX / RX pair). The panel scans only files that are not logs (a log's messages are decoded).
  Later (not built): a raw binary dump without times opened with a structure; a hex view around a broken message; a
  link pill in the top bar like MAVLink's.
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

- 2026-11-22 · MSG9: the proposal reads the MSG8 test stream right by itself; Not the type byte; Messages 520 px. backend all,
  e2e test_messages (13) green.
- 2026-11-22 · CP4 (owner: "the easiest way to throw an interactive plot straight to Confluence"): app/confluence.py, routes, Settings,
  Send to Confluence in the plot / tab / Ctrl+K. backend test_confluence (3), e2e test_confluence_copy (3), test_settings green.
- 2026-11-22 · MSG8 (owner: "hex to double and ascii"; "several bytes with a formula; is it clear"): byte view modes, reads-as, double /
  text in the menu, ascii fields, a field's formula. backend all (1512), e2e test_messages (12), Vitest, mypy green.
- 2026-11-22 · MSG7 (owner: "plot which messages passed in order, their histogram; choose one message and get its variables"): the
  recording's `message`, skip, the step 4 list and Plot. backend all (1511), e2e test_messages (11) green.
- 2026-11-22 · MSG6 (owner: "the footer was detected as the header too - maybe by time"): reproduced - a recording that starts inside a
  message framed from the footer in 22 of 24 cases; with the pauses 0 of 24. backend all (1511 passed), e2e test_messages (10),
  test_report_parts green.
- 2026-11-22 · MSG5 (owner: "any column with several values, the user says which is TX and which RX"): direction_values + route,
  rxValue, StreamEditor pickers. backend test_bytestream (14), e2e test_messages (9) green.
- 2026-11-22 · build run 45055081958: the AppData fix worked (Tectonic found its folders); next on Windows: "texbundle.zip doesn't
  specify a valid bundle" - Tectonic reads -b as a URL first and D:\... is the scheme "d". svcore/latex.bundle_arg: a drive path
  as file:///D:/... (make_tex_bundle.py too); test_report_latex::test_tectonic_bundle_argument_on_windows_is_a_file_url.
- 2026-11-22 · CP3 (owner: Confluence 10.2, interactive): the user macro (Velocity template, the same script as the HTML macro),
  the markup copy, the setting and the save button. backend test_clip (4), e2e test_confluence_copy (2), test_settings,
  test_space_and_settings green.
- 2026-11-22 · HL1 (owner: "can all the plots in the HTML export be linked when zooming"): viewer.js linked() - a tab's time plots
  share zoom and cursor, the 🔗 button in the header (report.py, reportdoc.py strings en / he). test_report_doc's LaTeX test: the
  ```latex block's picture checked only with a computer TeX (the built-in typesets documents) - the rest of it now passes here with
  the built-in Tectonic alone (bundle from build run 45053658269). e2e test_report_linked_zoom (new), test_report_xy_zoom,
  test_report_doc, test_confluence_copy, test_live_report, test_report_parts green.
- 2026-11-22 · build run 45053658269 (manual, after RE4): tex-bundle green with Hebrew (552 files, 13.2 MB); Linux, macOS green;
  Windows backend: the built-in Tectonic failed in the tests ("Unable to find standard directories") - conftest's temporary
  USERPROFILE had no AppData, from which Windows resolves its known folders; conftest makes them. test_rawlink UDP failed
  once on Windows (same length, other bytes; green in every earlier run, untouched by RE4) - watched, not changed.
- 2026-11-22 · test_report_doc failed now and then (a formula missing from the preview): two previews drew the same formula in
  two threads - mathtext is not thread-safe; the failure was cached. reportdoc._MATH_LOCK; backend
  test_formulas_drawn_at_once_by_several_previews (32 threads: 145 / 160 failed without the lock); e2e test_report_doc 4 / 4 runs green.
- 2026-11-22 · RE4 the built-in LaTeX (owner: "a light solution like that we can bundle - yes"): Tectonic 0.17.0 pinned with its
  SHA-256 (tools/get_tectonic.py: Windows 51 MB unpacked / 21 MB zip, Linux 26 MB) + a bundle of the TeX Live 2023 files the
  samples read (tools/make_tex_bundle.py: xelatex -recorder on the app's own LaTeX - Markdown report, LaTeX document with the
  usual packages, Hebrew report with --hebrew, formula picture - + the format's files + the fonts opened by name; 471 files,
  9.3 MB zipped; --check typesets every sample with Tectonic from the zip alone, -C). svcore/latex.py: the computer's TeX
  first, then the built-in (engine "tectonic", TECTONIC_CACHE_DIR ~/.signalviewer/tectonic: the format is made once, ~6 s,
  then ~1 s a report); a missing package named as not in the built-in. reportdoc: MathML (latex2mathml, MIT, 79 kB) when
  neither mathtext nor a TeX can draw a formula; align / aligned as arrays. build.yml: job tex-bundle (ubuntu-24.04,
  TeX Live + polyglossia/bidi + FreeSerif, --hebrew --check) -> every build downloads it and gets Tectonic for its OS;
  SignalViewer.spec carries app/tex; the PyPI package does not. Hebrew in the bundle is checked only in CI (no bidi.sty
  here; the download of its source was not run). Tests: test_report_latex (7: built-in typesets, errors at the line, a
  missing package; MathML with no TeX), full backend 1505.
- 2026-11-22 · HTML page, XY plot (owner: "in the HTML export the zoom is only on x, not in XY"): viewer.js - a box zooms both axes
  (the selection was read after uPlot cleared it, and an auto y re-ranged after x), the wheel zooms both around the pointer (Shift x,
  Alt y), double click resets; window.__svPage for tests. e2e test_report_xy_zoom (new), test_report_doc, test_confluence_copy,
  test_live_report green.
- 2026-11-21 · Release 1.33.0 prepared (owner: "I only apply the patch, ready for a version"): version 1.33.0 (build.bat, version.py,
  CITATION 2026-11-21, installer .iss / version_info, install.md), CHANGELOG with highlights, README + Hebrew, features, limitations,
  reports(.he) LaTeX, GUIDE.he messages steps, validation page, pictures 42 48 49 50 51 55 56 and the new 57 (LaTeX; media scene
  img_57 needs TeX and SV_CHROMIUM). The WHOLE e2e one file at a time: 97 files, 526 passed, 1 failed - test_study_loop (the known
  one): a step clicked while a round's first results were read was put back by firstResultsIn (sweeps/studyStore.ts) - it now keeps
  where the click went (goFlow counts the clicks: flowAsked); 18 / 18 runs green after, test_study_* and test_sweeps_flow green.
  quick_check green, mkdocs --strict green. Hebrew in LaTeX not compiled here (no bidi.sty in this container).
- 2026-11-21 · RE3 (owner: "the app should support full LaTeX like Overleaf, but everything must work offline"): the computer's own
  TeX (svcore/latex.py), the LaTeX project and the LaTeX document (app/reportlatex.py), ```latex blocks and formulas mathtext
  cannot read drawn by TeX in the page / PDF / Word, *Written in: Markdown / LaTeX*, *PDF (LaTeX)*, *LaTeX (.zip)*; a value's `{{`
  is the last pair of a brace run (prepareDoc), so `\textbf{{{ max(Speed) }}}` works. Checks: quick_check green; backend
  test_report_latex (5); e2e test_report_doc (4), test_report_parts, test_messages, test_live_report, test_findings_report,
  test_confluence_copy, test_less_clutter, test_fresh_user - green. Decisions: docs/dev/REPORTS.md RE3.
- 2026-11-21 · MSG4 (owner: "identical patterns that can be the header or the footer, propose the template, the user defines it and
  it is clear how; then the variables into the recordings, saved to CSV like any input; an automatic report"): the stream editor
  as four numbered steps; svcore/msginspect.py (patterns, frames with roles and values, the whole stream counted) and
  /api/messages/inspect; protocol.frames_binary (parse_binary uses it); ByteView.tsx - a click on a byte says what it is
  (messages.ts applyRole); the template proposed when a stream is opened (*Propose again* replaces *Propose a structure*);
  step 4 *Save as a file*; FileBrowser: a recording with no file behind it ("python:…") is not a start folder (it opened
  "Folder not found"). docs/messages.md rewritten as the four steps, picture 56 (media scene img_56). Checks: backend
  test_msginspect test_protocol test_bytestream, Vitest messagesRole, e2e test_messages (8 green).
- 2026-11-20 · The training film narrated (owner: "a training film with a narrating voice that explains the capabilities and how
  to use them"): tools/narration.py (Piper, en_US-lessac-medium, offline once fetched; clips laid at the film's moments, the cut
  waits taken out), make_training_video.py - every chapter spoken, a new chapter 6 Messages (the panel, propose, make the
  recording, live links), chapter 7 Reports on the report made for you; the script brought up to date (examples without a
  welcome card through Help -> Examples). README: picture 55, the film's line. A Hebrew voice exists in Piper (he_IL) - offered.
- 2026-11-20 · Release 1.32.0 ready (with MSG3): CHANGELOG (MSG3 bullet, highlights), README (English + Hebrew), docs (messages.md
  with picture 55, features, limitations, reports), every README / docs picture made again (the rail's new button; 53 in the
  panel; 55 new) and the welcome cards; the media script's fixes (two helpers named `_example`, the MAVLink selector meeting
  the link section - also in test_features). Checks: the WHOLE e2e one file at a time - 97 files: 96 green; test_less_clutter
  failed on its button budget (the new Messages rail button: 55 -> 56, then green); **test_study_loop::test_a_copy_of_the_demo_runs_the_loop
  fails - also on d2edd52, before MSG3** (after the loop's round, *Results* in the step bar leaves the screen on Next runs; no
  `[data-shot=study]`) - pre-existing, open, the owner decides whether it blocks the tag; quick_check green; mkdocs --strict green; the validation page unchanged. Pushed to main (owner's word, [ci] in the release
  commit); the owner tags v1.32.0.
- 2026-11-20 · MSG3 (owner: "one central place for all the message data - MAVLink, NMEA, general messages"): the Messages
  panel (MessagesPanel.tsx, StreamEditor.tsx - the dialog removed), app/routes/messages.py (the /api/messages/* routes moved
  there from analysis.py; library list / get / save / reveal; streams), Live ▾ → Listen to a link from the library, the .svraw
  toast, `[[messages a, b]]`. Tests: backend test_messages_library (2); e2e test_messages (7: the panel replaces the dialog,
  a new one for the panel, the running link in it). quick_check green.
- 2026-11-20 · MSG2 footer (owner: "a footer"): `footer` hex - a message without length / size ends at it, a checksum before it,
  proposed when every message ends the same; text `end`. Sturdier guesses: byte order by which byte changes less, signed when
  just below zero, 32-bit when the top bytes hardly move. Example: serial_link/sensor_uart.csv + sensor.svmsg.json.
- 2026-11-20 · LINK1 (owner: "listen to a UART, parse the variables; or UDP; save it to a file and show it"): as Live MAVLink -
  svcore/rawlink.Receiver records serial (pyserial) / udp / tcp / tcpin to `.svraw` ("SVRAW1\n" + per chunk >QI receive time
  µs, length, bytes) with the structure beside it (.svmsg.json); load_svraw decodes by it (else a `byte` signal); livewatch
  reads an .svraw again whole on growth; /api/link/{start,stop,status,ports}; Live ▾ → Listen to a link (connection, the
  messages: NMEA / a file / a kept structure / bytes); tools/send_link_demo.py plays the examples over UDP / TCP.
- 2026-11-20 · MSG2 (owner: "define the message structure - the variables' types and the messages - and the app turns it into
  a recording's signals; or it finds the repeating pattern and proposes header1, header2, length, checksum; NMEA with commas,
  numbers as text; LSB / MSB"): svcore/protocol.py - binary (header, length / size / per-message size, type, checksum, fields:
  u8..f64, le / be, scale, add, bits, labels) and text (start, sep, *HH, fields by index: number / int / text / lat / lon /
  hhmmss / ddmmyy; a message id matches the sentence with or without its talker); parse -> a pushed run "python:messages/<name>"
  (session: not saved as a file, re-made from ws.messageStreams[].made with the same id); suggest - NMEA when the bytes are
  `$…` text (unknown sentences by place), else the framing found + fields guessed by smoothness between messages (f32, i32
  with sign-only top bytes, i16 / u16 le / be - signed when it crosses zero, two bytes when the high one hardly moves and the
  low one never wraps, counter, flags, b<n>); the .nmea reader; the dialog's structure part (Propose / NMEA / Load / Save,
  form or JSON, per direction, Make the recording); examples linkStructure (link_tx/rx.svmsg.json, the demo's payloads now
  real values) and gpsNmea (receiver.nmea, receiver_uart.csv); docs/messages.md. Decisions: a recording, not derived signals
  (many fields, each message its own times - a file's shape); fields named by place when proposed (value_4, b10) - the user
  names them.
- 2026-11-20 · MSG1 checked: quick_check green; e2e test_messages (2, new), test_report_parts (3), test_report_doc (3; one
  failure under load, green again alone), test_welcome_cards (10; Help → Examples now 13), test_fresh_user (6),
  test_live_report (6), test_findings_report (2), test_confluence_copy (1). The whole suite not run yet (end of round).
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
  messages in order (the first 40 + a plot of the type over the first 2 s). Then the owner's addition (requests /
  replies, handshake - spec above): built, the demo regenerated with a protocol (known answers in test_bytestream).
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
