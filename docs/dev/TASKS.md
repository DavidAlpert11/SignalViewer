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
| CH - a communication channel: patterns, anomalies, compare files (owner, 2026-11-26; plan in Open specs "CH"; ROADMAP "CH") | IN PROGRESS (push session, 2026-11-26) - plan, CH2 on main | CH1 one channel from separate TX + RX, CH2 the anomaly finder, CH3 anomalies on screen, CH4 the files compared, CH5 example, CH6 docs / e2e |
| AU - automatic finds made visible: one *Found in this file* line, truth vs navigation compared, more finds, *Name your signals* (owner, 2026-11-26; plan in Open specs "AU"; ROADMAP "AU") | IN PROGRESS (push session, 2026-11-26) - plan pushed | AU1 the line + the file menu, AU2 truth vs navigation, AU3 redundant copies, AU4 *Name your signals* + the example, AU5 docs / e2e |
| Release 1.38.0 - calm, clear, any data (owner, 2026-11-26; plan in Open specs; spec docs/dev/SPEC_1_38.md; ROADMAP "CC") | IN PROGRESS - on main (push session, 2026-11-26). Done: CC0, CC1, CC2, CC3, CC4, CC5, CC6, CC7, CC8, CC9, CC10, CC11, CC12, CC13, CC14, CC15, CC16, CC17, CC18, CC19, CC20, CC21, CC22, CC23 - Phase 2 done. Docs: GUIDE + GUIDE.he, features, limitations, command-line, README (en + he) updated for what is done. The welcome pictures of the three new cards made. quick_check green; e2e: every file each change touches (Log) | **Next:** (1) done - the patch is on main. (2) Phase 2 done (Settings keeps its descriptions on purpose - a dialog read once). (3) Phase 3 done (SPEC_1_38.md "Phase 3"). (4) Phase 4: version 1.38.0 in the five files + install.md, CHANGELOG heading + highlights, pictures (make_readme_media.py; 01 03 04 09 11 12 13 14 23 25 26 30 38-43 48-57 show changed screens) and the training film, mkdocs --strict, the whole e2e one file at a time, push; the owner tags. |
| Release 1.37.0 - RW1-RW12, the three-agent review of 1.36.0 (owner, 2026-11-25: "stay on the current version or release a new one") | READY 2026-11-26: the critic and the advocate both answered "READY FOR A NEW VERSION: YES" after round 4 (/home/claude/review in the session: critic_r1-r4, advocate_r1-r4, decision, judge_r1); version in the five files + install.md, CITATION date, CHANGELOG 1.37.0 with highlights, features + GUIDE + GUIDE.he (Open ▾, Checks' verdict, Compare's Similarity tab, the report's file names), validation page, pictures 01-04 07 09 10 12 15 20-24 42 43 48 49; the whole e2e one file at a time - 100 files, 555 passed, test_file_help_menus failed under load (the test read the Open menu before it was drawn - fixed, 3 / 3), test_file_browser_edit once under load (alone: green, as in 1.36.0); quick_check, mkdocs --strict | the owner tags v1.37.0 and publishes the Release; LATER from the review: C2, C7, C9, C12-C19, "1 limits" on a Sweeps step card, the neighbours-hold column with no goal, Hebrew time ranges in the health check |
| RW - the three-agent review of 1.36.0 (critic, advocate, judge; 2026-11-25): C1 no green verdict with nothing judged, C11 the report's paths / counts / What to look at, C5 What changed's counts, C3 a labelled Open, C4 Compare's own tab, C6 the demo's last line, C8 the similarity % and units, C10 the flag's target | built 2026-11-25 on the local branch `review-1125` (not pushed: the reviewers re-check it first); round 2 (RW9-RW12) answers the critic's and the advocate's blocking items; ROADMAP "RW"; quick_check, the e2e files of each change (see the Log) | the critic and the advocate re-review the branch; then the orchestrator pushes; later: C2 (panel widths, the Inspector on the first cursors), C7, C9, C12-C19 |
| Release 1.36.0 - UX1-UX5: one coherent app (pages in one frame: Investigate, Messages, Checks, Report; Sweeps' page head), Add a stream, examples built step by step, the big files split (owner, 2026-11-23/24) | READY 2026-11-24: the reviewer session (session_0146GPW2guKSxqJE46HkbNSn) said "APPROVED FOR RELEASE" after 18 points answered / fixed; version in the five files + install.md, CITATION date, CHANGELOG 1.36.0 with highlights, README (English + Hebrew), GUIDE + GUIDE.he, features, limitations, validation page, pictures 09 10 23 25 26 30 38-43 48-56 and the training film; the whole e2e one file at a time - 100 files, 550 passed, test_report_doc's LaTeX test failed for want of a TeX, test_file_browser_edit failed once under load and passed alone twice; quick_check, mkdocs --strict | the owner tags v1.36.0 and publishes the Release |
| UX1-UX4 - one coherent app: App.tsx split into shell/, workspaces as pages (PanelFrame), Messages *Add a stream* form, examples step by step (owner, 2026-11-23) | on main 2026-11-24 (owner: "approved, continue"; v1.35.0 was tagged first); quick_check, Vitest panelPlace, e2e test_messages, test_report_parts, test_features, the views that gain / lose room | UX5 below, item by item; then a reviewer session challenges the round until it approves a release (owner, 2026-11-24) |
| UX5 - the review's next steps 1-6 ("UX review 2026-11-23" in Open specs) | approved by the owner 2026-11-24 ("approved, continue"); 1-3 on main (the Inspector hidden beside a page; Checks in the one frame, a page with its ⤢; Sweeps' steps row as the page head; the demos in 2-3 steps; 5 the big files split - five of ten, the rest with reasons in ROADMAP) | 1-6 on main 2026-11-24 (6: pictures and the training film made again), the whole e2e green (but LaTeX, no TeX here). Reviewer session session_0146GPW2guKSxqJE46HkbNSn opened 2026-11-24 (builder: session_0146GPW2jrfxNS8wsEvtdLkF): answer its points, fix forward, until "APPROVED FOR RELEASE"; then release 1.36.0 prepared (the owner tags) |
| Release 1.35.0 - MSG10 messages (one field, streams forgotten / removed, Add a stream), WC5 earlier What changed spans, RE4 (editor) the report editor's undo / comments / line keys, FB1 the file dialog's lost click (owner, 2026-11-23: "update all the documents") | READY 2026-11-23: version in the five files + install.md, CITATION date, CHANGELOG 1.35.0 with highlights, README (English + Hebrew), GUIDE + GUIDE.he, features, limitations, validation page, pictures 42 48-53 55-57; the whole e2e one file at a time - 100 files, 545 passed, test_report_doc's LaTeX test failed only for want of a TeX (with TeX Live installed: 5 / 5); quick_check, mkdocs --strict, ci | the owner tags v1.35.0 and publishes the Release |
| CP5 - drag a plot or a tab out of the window (owner, 2026-11-22) | built 2026-11-22 (the drag's data and the link tested in Chromium; a real drop on the Windows desktop not tested here) | the owner drags a plot's ⠿ onto his desktop, into Word, into Outlook |
| Release 1.34.0 - CP4 Send to Confluence, CP3 the user macro, HL1 linked zoom, RE4 the built-in LaTeX, MSG5-MSG9 messages (owner, 2026-11-22: "yes - then release") | READY again 2026-11-22 (the tag moved: CP5-CP7, Z1 and the Confluence placement folded in): CHANGELOG 1.34.0 by topic with new highlights, README (English + Hebrew), features, limitations; the whole e2e one file at a time - 100 files, 541 passed, test_study_loop failed once under load and passed alone twice; backend, Vitest, mypy, mkdocs --strict | the owner moves the tag v1.34.0 to this commit and publishes the Release |
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

- **CH - a communication channel: patterns, anomalies, compare files (owner, 2026-11-26, Hebrew, translated):**
  *"Say I have a recording of a communication channel. I want the app to recognise repeating patterns that are beyond
  the message content (header, checksum, a handshake process). There are TX and RX in the same signal with another
  signal that sets the direction; and there are separate TX and RX, for which I want an option to define that they are
  one general channel of request and reply. Then I want the app to show graphically whether there are anomalies, to
  count them, and to compare the result with similar files."* Building without waiting (owner's word).

  **1. Inventory (2026-11-26, read in the code and run on `examples/serial_link/link_tx_rx.csv` and `link_mixed.csv`):**

  | The owner asked | Today | Clicks | Gap |
  |---|---|---|---|
  | Header, length, type, checksum found by themselves | `bytestream.decode`: the 2-byte header, a length byte / a length per type / fixed, the type byte, 7 checksum schemes; the panel's row says `AA 55 · sum8 2 bad · 5 types`, step 2 colours each byte's role | 1 (open Messages) | - |
  | The handshake | `bytestream.exchange` / `_sessions`: the rare messages of both directions grouped; the first group opens the link, a later one is a reconnect | report only (*Add to the report*, 3-4 clicks) | not on the Messages page at all; its order never compared (a step missing or out of order goes unseen) |
  | TX and RX in one signal + a direction column | found by itself: two rows *byte TX* / *byte RX* of one stream; step 1 says which value is TX and which RX (MSG5) | 1 | - |
  | Separate TX and RX as one request / reply channel | found as **two unrelated streams** (*tx_byte*, *rx_byte*); *Add a stream → TX and RX* (form: kind, two selects, Add) makes the pair, kept in the session only when *Plot the messages* / *Make the recording* is pressed | 5-6 | nothing says the two look like one link; the pair is lost if the user stops before step 4 |
  | Requests and replies, latency, unanswered, retries | `exchange`: pairs by an echoed byte or the next reply; mean / 95 % / max latency; unanswered, retries, orphans | report text; *Plot the messages* adds a *Reply latency* plot | not on the page; a late reply (a latency outlier) is not called one |
  | Anomalies shown graphically and counted | counted in the report's text and highlights: checksum errors, resyncs, gaps (> 5 × the median interval), unanswered, retries, reconnects; *Plot the messages* plots checksum good / interval per message | report: 3-4; plots: 2 | **no one picture of the anomalies over time, no count per kind in one place**; not found at all: a frame of a wrong length for its type, an unknown (rare, unexplained) type, a counter / sequence byte that skips or repeats, a type that stops (a rate drop), a handshake out of order |
  | Compare with similar files | `[[messages]]` over several files writes each file's sections one after the other | report: 4+ | **no table of the same channel across files** (a row per file, the differences marked) |

  **2. The plan (one coherent change per commit):**
  - **CH1 - one channel in one step.** The Messages list: two streams of one file, one TX-like and one RX-like (names;
    else two streams whose messages answer each other), not yet one definition -> a line *tx_byte and rx_byte look like
    the two directions of one link · Make one channel*. One click keeps the pair in the session (`ws.messageStreams`,
    carries "pair", one Undo) and opens it; *Add a stream → TX and RX* keeps it at once too (not only at step 4).
  - **CH2 - the anomaly finder** `backend/svcore/channel.py` (pure, on every message): per direction - bad checksum,
    broken frame (a resync: bytes lost between headers), wrong length for the type, unknown type (rare: <= 2 and not in
    the handshake), a counter that skips or repeats (a payload byte that steps by 1 in >= 90 % of a type's messages),
    a gap (a periodic type silent > 3 × its period); both ways - unanswered, a retry, a late reply (latency over the
    median + 6 × the MAD and over 2 × the median), a reconnect, a handshake whose steps differ from the first one.
    Each anomaly: kind, time, direction, type, a short detail; counts per kind. Route `POST /api/messages/channel`.
  - **CH3 - on screen.** The stream on the Messages page gets a *Channel* block above the four steps: what was found
    beyond the content (header, length, type, checksum, the handshake's steps, request -> reply pairs with latency) and
    *Anomalies*: a chip per kind with its count, and a time strip - one lane per kind, every anomaly counted (several
    in one pixel: a taller mark and the number in its tooltip); a click on a mark (or a chip's next ›) puts the cursor
    there on the plots (`goToTime`). *Plot the messages* adds an *Anomalies* plot: the count so far per direction (op
    `messages`, what `anomalies`: a step at each one) so they line up with the data on the timeline.
  - **CH4 - compare files.** In the Channel block, *Compare with similar files*: the other open files that have the
    same signals get the same definition; one table, a row per file, a column per kind, a cell that differs from this
    file's marked (more / fewer). The report: `[[messages]]` gets the anomaly counts per stream, and with several files a
    table of the files (the same rows) - one way: the panel and the report read the same `channel.py`.
  - **CH5 - an example** (`examples/channel/`, generator `make_channel.py`): two recordings of the same link (TX and RX
    in separate signals), every anomaly kind injected, the second with different counts; Help -> Examples.
  - **CH6 - docs** (`docs/messages.md`, GUIDE + GUIDE.he), Vitest / pytest for every detector, e2e
    `tests/e2e/test_channel.py` (one channel, the anomalies, the files compared), CHANGELOG Next.
- **AU - automatic finds made visible (owner, 2026-11-26, Hebrew, translated):** *"Plotting the command against
  the actual by words like des, cmd, command lets the user plot automatically - but it is found only through Ctrl+P and
  a search; the user cannot guess it exists. More automations like these; objects on the map by lat / long; comparing
  objects (position, velocity and angle errors). Make them accessible, add more, and suggest to the user what to
  record - e.g. a physical position (6dof.lat, physics.lat) and a navigation system of the same platform can be
  compared, so he knows it is worth producing such variables."* Building without waiting (owner's word).

  **1. Inventory (2026-11-26, read in the code):**

  | Automation | What it recognises (the exact rule) | Where it is offered today | How hidden |
  |---|---|---|---|
  | Command and response | `desired.ts` `actualNames` / `setpointPairs`: a leaf with a setpoint word as prefix / suffix (`_ - .` or camel case): commanded, reference, setpoint, command, desired, demand, target, des, dem, cmd, tgt, ref, set, sp (`roll_cmd`/`roll`, `DesRoll`/`Roll`, `RDes`/`R`, `hdem`/`h`, PX4 `x_setpoint.x`/`x.x`); same file. Python twin `svcore/reportparts.py setpoint_pairs` | palette *Plot commanded / measured pairs*; the file's right-click menu (always, even with none); the template chip *Command and response* (empty plot / file panel strip, one of three chips); Checks *Any data* tracking metrics; report `[[tracking]]`; the setpoint is drawn dashed by itself | the user must know the palette word or right-click a file; the chip competes with two others |
  | Objects on the map | `objectDetect.ts` (+ `svcore/objects.py`, one table `object_names.json`): a prefix with lat + lon (aliases), or N/E/D, E/N/U, ECEF x/y/z in metres; attitude roll/pitch/yaw or a quaternion under it or a sub-group; class by a whole prefix segment (truth: phys truth true sim model plant dyn; navigation: nav ins ekf ahrs est kf filter fusion; receiver: gps gnss ...); well-known flight-log groups | the file panel's line *N objects found · Add all · Choose… · Why?* (ObjectSuggestBar); a map's *+ Add object*; the *Position on the map* chip | visible - the model for the rest |
  | Compare objects (truth vs navigation: position / velocity / attitude errors) | `relation.ts defaultPair` (primary truth, secondary navigation); `CompareObjectsDialog` (`makeComparison`, `svcore/objcompare.py`); report `[[navigation]]` (`guess_reference`) | only AFTER objects are on a map: a one-time *Compare objects…* line in the file panel right after adding, the map's relation box (bar menu), an object chip's right-click, the palette | **lost in practice**: nothing says it exists before a map is made; the offer goes when closed |
  | State / mode bands | a signal with text values (`labels`) is a lane by itself | Quick look puts two as lanes; a signal's menu *Show as a state* | nothing says a file has modes |
  | Actuator effort and saturation | `templates.ts EFFORT`: u, u1, `*_u`, effort, actuat, motor, servo, valve, throttle, pwm, duty, torque, rc_out | template library / a chip when it ranks; Checks' saturation flags | library only |
  | Many runs as an envelope | ≥3 open files sharing a signal name | template library | library only |
  | Compare open files | ≥2 files | a chip; the start card (files opened together) | visible |
  | Byte streams | byte columns `byte_0..`, `b[0]`, `data0` (AddStream); a 0..255 signal (`svcore/bytestream.py`) | the Messages panel (rail), a signal's menu *Decode messages* | the user must open Messages |
  | Health / Any-data checks | `svcore/health.py` (flight-log rules), `svcore/autocheck.py` (steps, oscillation, non-finite, pairs) | Checks page; the start card's three findings | visible after opening |
  | What changed?, Find similar, sim vs flight alignment, Compare's similarity | structure-free (any signal) | Investigate, a span's menu, file menu *Align…*, Compare | not name-driven - out of scope here |

  **2. One mechanism - the *Found in this file* line (AU1).** `frontend/src/found.ts` (pure, unit-tested): one list of
  detectors, each `{id, n, why: matched names, run()}`; `FoundBar.tsx` takes the place of ObjectSuggestBar in the file
  panel (the same slot, one quiet line): *"Found in uav.csv: 4 command / response pairs · 2 objects with a position ·
  truth and navigation → errors · 2 mode signals · 3 sensors in two copies  [Why?] [×]"* - every chip one click;
  *Why?* unfolds the matched signal names per find and a link *Which names does the app recognise?*; × remembered per
  file name (Settings-like local memory; a file dismissed stays quiet next time). The file's right-click menu gets one
  submenu *Found in this file ▸* with the same items (the lone *Plot commanded / measured pairs* item moves in it);
  the palette lists the same finds (group *Found*). The objects' *Add all / Choose…* and the compare offer stay in the
  line (one line, not two). No new button elsewhere.

  **3. Truth vs navigation (AU2).** `platformPairs` in found.ts: candidates of class truth and navigation of the same
  platform - their prefixes equal once the class segment is taken out (`uav1.truth` / `uav1.nav`, `6dof` / `ins` in a
  file with one of each). New truth words `6dof`, `physics`, `groundtruth`; navigation `navigation`, `estimate`
  (`object_names.json`, Python reads the same table). One click: both objects on a map (added when missing), the truth
  the reference, the navigation the compared one, *Compare objects…* opened on them (position, velocity, attitude
  errors, the statistics).

  **4. More finds (AU3)** - built: *sensors in several copies* (`IMU[0].AccX` / `IMU[1].AccX`, `imu1.ax` / `imu2.ax`:
  the same field under a group that differs only by its number) → a tab, one plot per field with every copy, so a
  disagreeing sensor shows; *mode signals* → lanes on the tab; *effort / actuators* → the existing template;
  *several runs* (≥3) → the envelope template; *byte columns* → Messages. Proposed for later (not built now): a
  derivative pair (pos / vel) check, units consistency, events from a state change as marks, a periodic signal's
  frequency.

  **5. *Name your signals* (AU4).** Help → *Name your signals* (and every *Why?*): a page listing each find, the names
  it recognises with examples (`pos_cmd` / `pos`, `DesRoll` / `Roll`; `truth.lat` / `nav.lat`, `6dof.lat` /
  `ins.lat`; `imu[0].ax` / `imu[1].ax`; a text column `mode`), a CSV header to copy, and *Open the example*: a new
  example `examples/automations/platform_run.csv` (generator `svcore/example_data/make_automations_example.py`) that
  triggers every find. Docs: `docs/naming.md` (+ `naming.he.md`), GUIDE + GUIDE.he, features.

  **6. Tests (AU5):** Vitest for every name rule (found.test.ts), backend test for the new class words and the
  example, e2e `tests/e2e/test_found.py` (open the example → the line shows the finds → each click ends in its state:
  a pairs tab, objects on a map, the compare dialog on truth vs ins, lanes, a copies tab; × remembered).

- **1.38.0 - calm, clear, any data (owner, 2026-11-26)** - the plan below; approved by the owner ("yes, start").
  Owner, 2026-11-26: (1) the app looks light and flowing, it is clear where each thing is done, not overloaded;
  (2) not an ArduPilot app - decoding, viewing, automatic research and reports for simulation and test data of any
  kind; ArduPilot is one example; (3) one finished version, nothing left for a later one.

  Who does what: a session WITHOUT push starts the round on a local branch from main and hands over ONE patch with all
  commits since main (skill sv-patch; checked with `git am` on a fresh clone). The owner gives it to a session WITH
  push, which applies it on main, continues from TASKS.md "Current state" and pushes (prompt-1.38.0-calm.md).

  Commit 0 (done): the judge's JR1 (formula 500 -> readable 400) and JR2 (test_file_browser_edit END state),
  cherry-picked from `judge/release-1.37.1`, without its 1.37.1 bump.

  ## Phase 1 - audit and spec (no code; the owner sees it once)
  1. Screenshots of every screen (welcome, a recording with plots + Inspector, Checks, Compare, Investigate / What
     changed?, Messages, Report, Sweeps' 5 steps, Live, Settings, palette) - dark / light, en / he - /tmp/audit/before.
  2. "Where is each thing": every action -> every place it appears; duplicates marked.
  3. Load count per screen: visible controls, always-on instruction lines, empty-state paragraphs.
  4. **ArduPilot-centrism audit**: every place the app assumes a flight / a drone / ArduPilot outside a profile:
     - welcome: FEATURED starts with `ardupilot`; 4 of 6 featured cards are flights; examples/ is mostly UAV
       (copter_flight.bin, uav_flight*.csv, folder_of_flights, sim_vs_flight, drones, sweeps/drone_tuning);
     - Checks: the automatic health check (svcore/health.py) is ArduPilot rules (VIBE, BATT_*, EKF, GPS); the
       Checks panel's sub-tabs (Events, Parameters, Instruments, Hardware) are log-specific;
     - words in the generic UI: flight, mission, flown, drone, mode band;
     - report templates and the What-to-look-at wording; the docs' and README's order and pictures.
  5. **Capability audit for generic research** - try each with a non-flight file and write what is missing:
     - formats: MATLAB / Simulink `.mat` (timeseries, Simulink.SimulationData.Dataset / logsout, structs with
       time), HDF5 groups, Parquet, CSV with several time columns, units and descriptions read from the file;
     - a batch of simulation runs (Monte Carlo / a parameter grid) as a folder: one table of results per run;
     - requirements: a generic requirements / checks file (limits, settling time, overshoot, rise time, steady-state
       error, rate limits, "within X of the reference", "A before B") evaluated on every run, with a verdict per run
       and per requirement;
     - automatic research with no rules written: generic flags on any signal (stuck / flat, saturation at a constant,
       spikes, NaN / gaps, time steps, oscillation, drift, a step and its response metrics) - the "health check" for
       any data;
     - comparison of a simulation with a test / reference run, and of a run with a baseline (tolerance bands);
     - the report: a generic "simulation / test verification" template (requirements table, pass / fail per run,
       the plots that show each failure, reproduction info), en + he, HTML / Word / PDF / LaTeX as today;
     - headless: the CLI runs load -> checks -> report on a file or a folder (for CI of the user's own simulations);
       a Python entry point for the same.
  6. The spec: per screen before -> after; per capability what exists / what is added. Shown to the owner ONCE in
     Hebrew (pictures, the table of duplicates, the change list); his answers go into TASKS.md "Open specs".
     Ask him in the same message: CI on every push to main (I5, "not now" before) - yes / no.

  Starting points seen in the 1.37.0 pictures (verify, do not take as given):
  - TopBar ~15 controls -> about 8, grouped; theme and language into Settings (+ palette); Save / Download labelled
    or under one *File ▾*.
  - The always-on hint line above the plots -> tooltip / tour / Help.
  - Long empty-state paragraphs (Inspector Notes, "Select a signal...", Checks "No limits set...") -> one line + "how?";
    the Inspector closed when there is nothing to show.
  - The floating Note / Find similar / What changed? bar over a plot -> one place (the plot's ⋯ or context menu).
  - Sweeps: three navigation layers and two "See the results" -> the step cards + one Next; paragraphs -> one line + "?".
  - Checks: six sub-tabs -> at most 3-4; the verdict first; log-only tabs only when the file is a log.
  - Rail vs the Recordings / Sweeps switch: make "mode" vs "panel" obvious; tooltips say what each is for; a disabled
    entry says why.
  - Visual weight: one spacing scale, fewer boxes / outlines, one primary button per screen, muted secondary text,
    the mode band once; small targets (×, close tab, drag handle) at least 24 px.

  ## Phase 2 - build (one coherent change per commit; CHANGELOG / ROADMAP "CC" / TASKS in the same commit)
  A. Calm and clear: the approved screen changes, screen by screen, e2e that click moved controls updated, GUIDE /
     GUIDE.he / features updated.
  B. Any data:
     1. Profiles: the ArduPilot health check becomes one profile (chosen automatically for ArduPilot / PX4 logs);
        a generic profile (the flags of Phase 1.5) runs on every file; a profile is a file (JSON) a user can write.
     2. Requirements: extend checks.json into a generic requirements file (the metrics of Phase 1.5; backward
        compatible); a verdict per run / per requirement in Checks, Sweeps and the report.
     3. Batches: a folder of simulation runs -> results table -> Sweeps / Checks (reuse folder_of_flights' mechanism,
        named generically).
     4. Formats: whatever Phase 1.5 found missing (Simulink Dataset / logsout, units / descriptions from the file).
     5. The report: a generic verification template; flight wording only in the flight template.
     6. Headless: CLI (and a Python call) load -> checks -> report on a file or folder, exit code = verdict.
     7. Examples (made by tools, like make_drone.py; small files): a Simulink-like `.mat` control loop (step
        response vs requirements), a vehicle / process simulation in HDF5, a Monte-Carlo folder with a requirements
        file, a simulation against its test run (non-flight), a bench test (exists: bench). The welcome screen
        groups examples by task (look, compare, find what went wrong, verify against requirements, sweep, report),
        generic first; ArduPilot / PX4 under "Flight logs".
     8. Words: generic terms in the chrome (run, recording, signal, mode/state); flight words only in profiles,
        templates and examples. README / docs reordered: generic first, flight logs as one section.
  C. Technical leftovers: oxlint baseline in quick_check + CI (171 warnings today; fix no-loss-of-precision
     chartUtil.test.ts:49 and globals mapLayers.ts:38); "1 limits" singulars; "neighbours hold" "–" with no goal;
     Hebrew time ranges in the health check; Compare's unit on the difference plot + noise note; a new derived
     signal's name shortened (formula in the tooltip); loaders' print() -> logging; C2 (panel widths, the Inspector on
     the first cursors); C7, C9, C12-C19 only if /home/claude/review exists - otherwise noted and skipped.
  D. Refactoring (behaviour unchanged, after the UI work on each file): the csv_loader <-> bin_loader cycle (shared
     module, re-exports kept); bin_loader.py split; Globe3D / TimeChart / GeoChart split into hooks + helpers; the
     bundle (vendor chunks for react / uplot, lazy GeoChart and rare panels; no chunk over 500 kB).
  Not in scope: N5 (window under 930 px, documented).

  ## Phase 3 - verify against the goal
  Screenshots again (/tmp/audit/after) and the load count again; every action in one place; a separate agent that has
  not seen the work gets the app and tasks ("open a Simulink result and check it against its requirements", "compare
  two runs", "find what went wrong", "make a report", "change the language", "start a sweep") and says where it would
  click first - what it cannot find in one try is fixed. Before / after shown to the owner.

  ## Phase 4 - release 1.38.0
  CLAUDE.md "Releasing" + sv-release: ci by hand, version in the five files + install.md, CHANGELOG with highlights,
  README (en + he) and docs reviewed, pictures and film, mkdocs --strict, the whole e2e one file at a time until green,
  TASKS / ROADMAP. The session with push pushes to main; the owner tags v1.38.0.

  ## Handover rule (every stop)
  Before a patch is made: TASKS.md "Current state" says which phase / item is done, what was tested, what is next;
  the Log names the e2e that ran. The patch = all commits since origin/main (git format-patch), checked with git am
  on a fresh clone, authored David Alpert <davidalpert11@gmail.com>.

- **UX review 2026-11-23 (owner: "clean up the code, modular; review the design; examples that show how it is built";
  "one whole, flowing, coherent app")** - built in UX1-UX4 (ROADMAP "UX"). The principle written into components/rail.ts:
  *the tools that act on the plots (Files, Create, Compare, Checks) sit beside them; the workspaces read and worked in
  (Investigate, Messages, Report) are pages in one frame* (shell/PanelFrame.tsx: head where the plots' bar is, the
  demo's line, an index column, the main column - the Report's own anatomy). Proposed next, not started (each its own
  task, the owner's yes first):
  1. *Design* - the Inspector beside a page shows the plots' cursor values: hide it on a page, or give each page its
     own (Messages: the byte under the pointer; Investigate: the signal chosen in What changed).
  2. *Design* - Checks as a page too (its findings list + a finding's detail), the same frame.
  3. *Design* - Sweeps: the same head / index / main anatomy as the pages, so the two areas read as one app.
  4. *Examples* - the one-step demos (flight, car, bench, ardupilot, twoFlights) as two or three steps each.
  5. *Code* - the files past ~1000 lines, split by part (the way App.tsx was): Globe3D.tsx 1379, TimeChart.tsx 1122,
     GeoChart.tsx 1100, sweeps/state.ts 1138, index.css 2185 (its area rules into styles/*), backend reportparts.py
     1420, report.py 1373, bin_loader.py 1271, routes/sweep.py 1100, csv_loader.py 1041.
  6. *Media* - pictures 52-54 and the training film's messages / report chapters now follow the steps (their scripts
     updated: `_finish_demo`, `_wide_panel` a no-op on a page); refresh them at the next release.

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

- 2026-11-26 · CH2 the anomaly finder (svcore/channel.py, /api/messages/channel, op messages what anomalies): 11 kinds, each
  injected once in test_channel; the serial link demo: 4 checksum, 1 broken, 18 unanswered, 1 retry, 3 gaps, 1 reconnect,
  4 counter skips. backend test_channel test_messages_library test_bytestream test_msginspect test_protocol, mypy.
- 2026-11-26 · CH plan written (Open specs "CH"): the inventory of the channel analysis (patterns, handshake, request / reply,
  anomalies, files compared), run on examples/serial_link, and the build order CH1-CH6.
- 2026-11-26 · AU plan written (Open specs "AU"): the inventory of the name-driven automations and the build order.
- 2026-11-26 · Phase 3: audit_screens again (outlined 394 -> 250), a fresh agent's first clicks - fixed Checks'
  requirements line, the Report's export labels, singulars. e2e: test_checks_view, test_one_per_plot,
  test_less_clutter, test_calm_screen, test_what_changed, test_report_doc (4 / 5: the LaTeX test - no TeX here),
  test_welcome_cards, test_judge_a_run, test_features - green.
- 2026-11-26 · CC22: timeChartDraw.ts, geoMap.ts, globe3dParts.ts out of TimeChart / GeoChart / Globe3D (behaviour
  unchanged; plots pixel-identical). e2e: every time-plot drawing file and every map / 3D file (11 files, 71 tests) -
  green; Vitest 315; oxlint none new.
- 2026-11-26 · CC21 (rest): bin_loader.py split into ardupilot_tables / bin_lazy / bin_index, names re-exported.
  backend pytest 1541 passed, mypy clean.
- 2026-11-26 · CC10 (rest) fewer outlines (394 -> 250 visible frames), Goal's one way on, its table hint a tooltip;
  test_features' Checks test waits for the events list to settle (it was flaky: the any-data findings arrive after the
  list). e2e: test_sweeps_flow, test_sweeps_workspace, test_sweeps_groups, test_calm_screen, test_plot_polish,
  test_features (126), test_checks_view, test_welcome_cards, test_settings - green.
- 2026-11-26 · CC3 (Next runs): its explanations as tooltips. e2e test_sweeps_flow (35), test_sweeps_workspace (12),
  test_study_common - green.
- 2026-11-26 · CC20 (rest): the noise note in Compare (noiseRatio, ≈ noise). backend test_compare_noise, -k compare;
  e2e test_compare_diff, test_compare_tolerances, test_judge_a_run - green.
- 2026-11-26 · CC13: a verdict column per requirement + requirements met in a folder's runs table (job and CLI).
  backend test_summary; e2e test_welcome_cards, test_folder_of_recordings, test_sweeps_data_columns - green.
- 2026-11-26 · CC15 (rest): [[requirements]] and the Verification ready report; CLI check reads each file's own checks
  file. backend test_report_parts, test_cli_api, test_checks; Vitest reportReady / reportDoc; e2e test_report_parts,
  test_report_doc.
- 2026-11-26 · CC15 (generic templates) + CC17: Actuator effort, Frequency content, Many runs as an envelope; the
  library's Any data first, flight logs grouped; generic words in maps / step response. e2e: test_any_data_templates
  (new, 3), test_templates_recent_badfiles, test_object_templates, test_template_tabs, test_first_minute,
  test_one_per_plot, test_flat_line_solo, test_fresh_user, test_workflows, test_features -k template - green; backend
  test_templates.
- 2026-11-26 · CC4: the span's Note / Find similar / What changed? in the plot's ⋯ and right-click menus
  (spanActions.ts), the head's bar gone. e2e: test_plot_polish, test_conditions, test_what_changed, test_plot_room,
  test_welcome_cards - green; tsc, oxlint (168, none new), Vitest.
- 2026-11-26 · CC3 (more): Checks' flags note and the checks file's line as tooltips; Sweeps' step intros at most two
  lines (the whole in the tooltip), *More than one to optimize?* the Optimize column's tooltip, *Need finer resolution?*
  the Next runs button's. e2e: test_sweeps_flow, test_checks_view, test_sweeps_workspace, test_welcome_cards,
  test_study_common - green.
- 2026-11-26 · 1.38.0 Phase 2, second part: CC3 CC5 CC6 CC8 CC10 (part) CC15 (part) CC19 CC20 CC23; docs for 1.38
  (GUIDE, GUIDE.he, features, limitations, command-line, README). quick_check green; e2e: test_features (126, two flaky
  under load - green alone), test_report_doc, test_report_parts, test_error_segments, test_object_frames,
  test_missing_choice, test_sweeps_flow, test_sweeps_groups, test_plot_menus, test_tab_band, test_less_clutter,
  test_checks_view, test_compare_diff, test_compare_tolerances, test_templates_recent_badfiles, test_template_tabs,
  test_move_plots_tabs, test_what_changed, test_conditions, test_welcome_cards, test_needle, test_plot_room,
  test_messages, test_first_minute, test_pyops - green. Phase 3 counts measured (SPEC_1_38.md).
- 2026-11-26 · 1.38.0 Phase 2, first part: CC1 File ▾ / Settings, CC2 Sweeps in the top row, CC7 Checks' tabs and words,
  CC9 one Open, CC11 requirements, CC12 profiles (any data, the user's), CC14 Simulink names, CC16 simulation examples,
  CC18, CC20 / CC21 (part). quick_check green; e2e run: test_file_help_menus, test_export_recording, test_messages,
  test_calm_screen, test_folder_of_recordings, test_study_common, test_sweeps_workspace, test_sweeps_flow,
  test_sweeps_data_columns, test_sweeps_groups, test_fresh_user, test_template_tabs, test_workflows, test_first_minute,
  test_settings, test_unsaved_close, test_tour, test_report_doc, test_judge_a_run, test_features, test_checks_view,
  test_welcome_cards, test_templates_recent_badfiles, test_overview_strip, test_file_browser_edit, test_study_demo,
  test_map_memory, test_study_loop, test_file_colours, test_perf_budget - all green (test_welcome_cards' picture test
  green once the three new cards' pictures were made).
- 2026-11-26 · 1.38.0 started (owner: one finished version - calm and clear, any data, not ArduPilot-centred). CC0:
  the judge's JR1 / JR2 cherry-picked from `judge/release-1.37.1` (without its 1.37.1 bump - that branch is superseded).
  quick_check green; backend test_formula_limits; e2e not run yet.
- 2026-11-26 · 1.38.0 Phase 1: 19 screens shot (dark / light, en / he) and counted (controls, TopBar, prose, boxes);
  the ArduPilot / capability audit; the spec docs/dev/SPEC_1_38.md (CC1-CC23). Owner: approved, build it all; I5 no.
- 2026-11-26 · CC18 the lint gate (tools/lint_baseline.py in quick_check + ci). quick_check; e2e test_messages.
- 2026-11-25 · RW round 2 (both reviewers: YES once one blocking item each is fixed): RW9 Sweeps with no limit -
  Hold every condition / Fail / the holds column "–", Show: All; RW10 Checks - a log's health check (or a checks
  file) before the automatic flags, 3 cards + "+N more", the strip's chip from the same parts; RW11 the Similarity tab
  marked (Tab.kind, optional) and reused after a restart, its name in today's language; RW12 the timeline names the
  event's own signal it does not draw. test_compare_tolerances raced the detail's 350 ms refresh - now waits for the
  end state. Checks: quick_check; Vitest similarityTab.test.ts; e2e all test_sweeps_*, test_needle,
  test_folder_of_recordings, test_welcome_cards, test_checks_view (5), test_plot_polish, test_overview_strip,
  test_plot_room, test_flat_line_solo, test_compare_diff, test_compare_params, test_compare_tolerances (x6),
  test_judge_a_run, test_tab_band, test_workflows, test_features -k "P01 or compare or tab", test_what_changed - green.

- 2026-11-25 · RW (the three-agent review, judge's round 1) on branch review-1125, one commit per fix: RW1 Checks /
  Sweeps never green with nothing judged (the automatic flags counted and listed), RW2 the report (file names not
  paths - Settings *Files in a report*, name=value parameters, non-zero counts, flags first in What to look at), RW3
  What changed? counts that add up + the first change's time + one name, RW4 the top bar's *Open ▾*, RW5 a Compare row
  click in a Similarity tab of its own, RW6 the demo's last line goes when the user leaves it, RW7 the similarity %
  defined and the units, RW8 the flag's 24 px target. Checks: quick_check (tsc, Vitest 311, backend pytest, mypy);
  backend test_report_parts; e2e test_checks_view, test_sweeps_flow, test_sweeps_workspace, test_sweeps_groups,
  test_sweeps_data_columns, test_folder_of_recordings, test_welcome_cards, test_plot_polish, test_findings_report,
  test_report_parts, test_report_doc, test_live_report, test_settings, test_confluence_copy, test_what_changed,
  test_features (whole), test_plot_room, test_conditions, test_file_help_menus, test_first_minute,
  test_templates_recent_badfiles, test_tour, test_unsaved_close, test_workflows, test_calm_screen, test_messages,
  test_aligned_plots, test_plot_menus, test_compare_diff, test_compare_params, test_compare_tolerances,
  test_judge_a_run, test_cursor_labels, test_file_colours, test_less_clutter, test_tab_band, test_overview_strip,
  test_flat_line_solo - all green. Not the whole suite (end of the round, after the reviewers).

- 2026-11-24 · The build of v1.36.0 failed on Windows (owner pasted the log): backend test_rawlink - a UDP link's
  bytes went back in time. time.time() on Windows moves in ~16 ms steps; chunks of one step had one stamp, and each
  chunk's bytes are 1 µs apart from it, so the next chunk overlapped. Fix: svcore/rawlink.py stamps with wall time at
  start + perf_counter; read_svraw keeps every byte after the one before (old recordings too). New test
  test_chunks_with_one_time_stay_in_order. Backend test_rawlink 4 / 4, mypy. In the 1.36.0 section (not published:
  the build failed) - the owner moves the tag v1.36.0 to this commit.

- 2026-11-24 · The reviewer: "APPROVED FOR RELEASE" (re-checked 1-18 on 44c4177). Its suggestion done (index.css's
  parts say so in their header). The whole e2e one file at a time again: 100 files, 550 passed; test_report_doc's LaTeX
  test (no TeX), test_file_browser_edit once under load (alone: 3 / 3 twice). Release 1.36.0 prepared: version, CITATION,
  CHANGELOG highlights, validation page, mkdocs --strict. The owner tags v1.36.0.

- 2026-11-24 · Reviewer (session_0146GPW2guKSxqJE46HkbNSn) batches 1-2, 18 points; answered and fixed forward:
  897d6da (a page stays a page while playing; e2e), eddf8d4 (demo lines: a step done by hand moves on, reportDemo in
  two steps, struct label, fields in view, Hebrew buttons in the noun form, texts), 491d428 (Messages head padding,
  chosen card corner, Sweeps title on narrow windows, rail aria-label i18n), 44c4177 (CHANGELOG wording, the 930 px
  limitation). #1 (design test) fixed in 16ed922 by reading index.css with its parts, not by moving rules (the
  cascade). quick_check all green (Vitest 311, backend 1520, mypy); e2e test_welcome_cards, test_report_parts,
  test_plot_room, test_messages, test_cursor_labels, test_sweeps_flow, _workspace, test_settings. Waiting for its
  re-check.

- 2026-11-24 · Fix forward: backend test_design_tokens failed after the index.css split (its parts in styles/ counted
  as an area's file, and the token checks read index.css only). The test now reads index.css with its parts and checks
  they are imported right after it, in order. Backend 1520 passed.

- 2026-11-24 · The whole e2e one file at a time after UX5: 100 files, 539 passed, 2 failed - test_report_doc's LaTeX
  test (no TeX in this container, as in 1.35.0) and test_map_smooth::test_playback_redraws_the_map_without_the_panels:
  App rendered on every playback frame since UX2 (usePlotsComeBack read the cursor with a selector; already failing at
  a638327). Fixed: a store subscription, no render. test_map_smooth 6 / 6, test_messages 16 / 16, test_what_changed.

- 2026-11-24 · UX5.5: five big files split by part (report.py, app/reportparts.py, routes/sweep.py, index.css,
  sweeps/state.ts), each its own commit, made in a separate worktree so the e2e running here were not disturbed; the
  CSS split checked by building before / after (byte for byte the same). Not split, with reasons (ROADMAP): Globe3D,
  TimeChart, GeoChart, bin_loader, csv_loader. Backend 1519 passed, mypy clean, Vitest 311; e2e test_confluence_copy,
  test_report_doc (LaTeX test fails without a TeX, as in 1.35.0), test_live_report, test_findings_report,
  test_sweeps_flow / _workspace / _data_columns / _big_table, test_messages, test_report_parts, test_needle.

- 2026-11-24 · UX5.4: the one-step demos lead on in 2-3 steps (look / compare or check / the report; sim: align then
  compare; investigate: cursors then What changed?). They still open what their cards show (the pictures promise it).
  tsc, Vitest; e2e test_welcome_cards (+1), test_plot_room (updated: the line moves on), test_cursor_labels,
  test_file_colours, test_less_clutter, test_tab_band, test_report_parts. The unused nvStudy string removed (UX5.3).

- 2026-11-24 · UX5.3: Sweeps - the steps row is the page head (the study's name with the area's icon; the Navigator's
  name head gone). Screenshots en/light, he/dark. Vitest; e2e test_sweeps_flow, _workspace, _charts, _data_columns,
  _groups, _big_table, test_folder_of_recordings, test_fresh_user, test_settings - all green. (Messages to the
  coordinator session were refused by the permission system; progress is reported here.)

- 2026-11-24 · UX5.2: Checks in the one frame (beside by default, a page with its ⤢: file + sections as the index,
  the section as the main column); screenshots en/light and he/dark checked. quick_check; e2e test_checks_view,
  test_event_navigation, test_tuning_tools, test_live_report, test_plot_polish.

- 2026-11-24 · UX5.1: the Inspector is not shown beside a page (decided: hide - it is all the plots' properties; a
  page's own context would be a second Inspector); its top-bar button off with a hint, back with the plots
  (rail.ts pageOnScreen). quick_check; e2e test_messages -k "inspector or one_home or serial_link".

- 2026-11-24 · Owner: "approved, continue; when done open a session that challenges you and asks questions - answer and
  fix until it is satisfied and approves a release"; "whenever a session starts to fill up, open a new one". UX1-UX4
  fast-forwarded to main (v1.35.0 already tagged at 53ae002). UX5 handed to a fresh session (the first one was full).

- 2026-11-23 · UX1-UX4 (owner, Hebrew: modular code; Investigate / other panels without room; messages only by a
  right-click; examples that open finished - then "one whole, coherent app"): App.tsx -> shell/ (effects, Dialogs,
  CursorValues, panels, PanelFrame); rail.ts the panels' table with place / width / isFull; Investigate, Messages as
  pages in the Report's anatomy (index + main, the demo's line), the plots back when an action needs them; AddStream
  form; demoGuide steps (serialLink, linkStructure, gpsNmea, reportDemo open raw), the label *a test report, step by
  step*; tests: Vitest panelPlace (3), e2e test_messages (+ test_add_a_stream_form), test_report_parts; media scripts
  follow the steps. On branch claude/cleanup-layout-guides - 1.35.0 is not tagged yet, main left as it is.

- 2026-11-23 · Release 1.35.0 prepared (owner: "yes - update all the documents"): version 1.35.0 (build.bat, version.py,
  CITATION 2026-11-23, installer .iss + version_info, install.md), CHANGELOG 1.35.0 – 2026-11-23 with highlights; README
  (the report editor's undo and comments, English + Hebrew), GUIDE.md / GUIDE.he.md (Asked before, the editor's keys;
  he: the field rows, Add a stream, the stream's ⋯), limitations (the editor's undo and Asked before are not saved);
  ROADMAP: MSG10, WC5, RE4 (editor - the ID was the built-in LaTeX's), FB1, the release. Validation page. Pictures 42
  48 49 50 51 52 53 55 56 57 (57 with TeX Live installed in the container). The whole e2e one file at a time: 100
  files, 545 passed, 1 failed - test_report_doc::test_latex_report_written_in_latex_typeset_offline, no TeX in the
  container; after `apt-get install texlive-xetex ...` test_report_doc 5 / 5.
- 2026-11-23 · FB1 - the file dialog lost the row click (the flaky test_messages direction-column test). Cause: after the
  serial-link example the dialog starts in examples/serial_link, which also has link_mixed.csv; the test typed the data
  folder + Enter, `goto_folder` saw the path box (not the listing) and clicked link_mixed.csv in the OLD list; the new
  listing then reset the pick - Open disabled. A real user bug too (a slow folder, a click on the old list). Fix: while
  another folder is listed, the old list is `inert` (dimmed after 0.2 s). Test: test_file_browser_edit
  ::test_a_click_while_another_folder_loads_is_not_lost (the new listing held back by the test; failed before the fix). e2e: test_file_browser_edit,
  test_messages, test_templates_recent_badfiles, test_first_minute, test_fresh_user, test_workflows, test_features (126)
  green; the serial-link + direction-column pair 12 of 12.
- 2026-11-23 · MSG10 / WC5 / RE4 pushed to main (the owner's patch). quick_check green, `npm run build`, mkdocs --strict;
  e2e test_messages 14, test_what_changed 12, test_report_parts 3, test_live_report 6 passed; test_report_doc 4 passed,
  test_latex_report_written_in_latex_typeset_offline failed twice: this container has no LaTeX ("No LaTeX on this
  computer"), not the patch. ci by hand: green (frontend, backend 3.9 + 3.12, e2e).
- 2026-11-23 · docs for MSG10 / WC5 / RE4: messages.md (Add a stream, the stream's ⋯, the structure form's rows),
  reports.md + reports.he.md (comments, the editor's keys), features.md (three lines). `mkdocs build --strict` green.
  The whole e2e one file at a time (101 files): 544 passed; test_messages::test_decode_as_messages_both_ways_with_a_direction_column
  failed once - after the serial-link example its Ctrl+O dialog's Open stays disabled (the row click lost); the same on
  main without these changes (3 of 12 runs of the pair), alone always green. Open: find why the click is lost.
- 2026-11-23 · RE4 (owner: "Ctrl+Z in the report's editing; a comment with Ctrl+/ and so on"): `editText.ts` (the editor's
  history - a step per pause or per piece put in, with the selection; toggleComment, indent, move, duplicate lines;
  stripMdComments) + editText.test.ts; ReportScreen keys and ↶ ↷ <!> in the toolbar; `prepareDoc` leaves Markdown
  comments out (their references too). Vitest 308; e2e test_report_doc (5, new test_editor_undo_a_comment_and_line_keys),
  test_report_parts, test_live_report, test_findings_report, test_report_*_zoom green.
- 2026-11-23 · WC5 (owner: "another investigation of what changed; and just remove it"): `ui.wcEarlier` (UI only, not
  saved), `investigation.ts openWhatChanged` (the shown span goes to the earlier ones; the chart's ? and the panel's button
  use it), *Asked before* chips in Investigate (open / ✕ / Clear all), *What changed between the cursors?* while one is
  shown. e2e test_what_changed (12, new test_another_span_keeps_the_first_one_to_open_again_or_remove) green.
- 2026-11-23 · MSG10 (owner: "removing one variable removed a whole group; a stream once defined cannot be removed; how do I
  define another TX"): StructureEditor - a row per field (✕ in sight, the conversion folded under it, Undo in the notice),
  a message removed only from its 🗑 after a question, messages fold. MessagesPanel - each stream's ⋯ (Fold, Start over,
  Forget the definition / Remove from the list; `messages.ts forgetStream`, one commit), *Add a stream* (any signal, byte-like
  names first). e2e test_messages (14, new test_remove_one_field_a_message_and_a_stream) green; quick_check: test_rawlink
  UDP failed once under load, alone green. Not yet: What changed keeping earlier spans (spec to the owner).
- 2026-11-22 · Release 1.34.0 again: the whole e2e one file at a time - 100 files, 541 passed; test_study_loop 1 failed under
  load (79 s), alone 3 / 3 twice (19 s). The owner moves the tag (commands given).
- 2026-11-22 · Z1 (owner: "zoom on y, everywhere"): the app's XY / FFT / step / envelope and every plot of the HTML page; the
  wheel's keys as the app's time plot. CHANGELOG: everything after the v1.34.0 tag folded into 1.34.0 (the owner had not
  released it: the tag is moved). e2e test_zoom_values, test_report_xy_zoom, test_report_linked_zoom, test_live_report,
  test_tuning_tools green; the whole suite next.
- 2026-11-22 · CP7 (owner: "a copy as a high-resolution picture"): Settings -> Copied pictures, Copy image and the static copy
  drawn again at 2 / 3 times. backend test_clip (6), e2e test_features (126), test_settings, test_confluence_copy green.
- 2026-11-22 · CP6 (owner: where on the page; copy / move after; a drag onto Chrome opens it): markers, headings, the choice;
  data-page; text/uri-list. backend test_confluence (6), test_clip (5), e2e test_confluence_copy (4) green.
- 2026-11-22 · CP5 (owner: "drag the plot or the tab out - HTML by default"): DownloadURL + picture + title; the toast after a drop
  outside. e2e test_confluence_copy (4), test_move_plots, test_move_plots_tabs, test_features (126) green.
- 2026-11-22 · CP4 (owner: "how do I test the Confluence export without Confluence?"): tools/try_confluence.py - the tests'
  stand-in as a tool, now showing the page (its macros drawn) and its attachments; e2e test_confluence_copy opens it and sees the plot.
  Fixed: Confluence Cloud has neither the HTML macro nor user macros - the page gets a link (test_confluence 5).
- 2026-11-22 · Release 1.34.0 prepared (owner: "yes - then release"): the whole e2e one file at a time - 99 files, 539 passed, none
  failed; pictures 52 53 55 56 (the bytes view, the step 4 list, the `message` lane); backend 1516, Vitest 301, mypy, mkdocs --strict.
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
- 2026-11-26 · Release 1.37.0 prepared after the three-agent review (critic / advocate / judge, rounds 1-4, both reviewers YES): review-1125 merged into main; version, CITATION, CHANGELOG highlights, features / GUIDE / GUIDE.he, validation page, pictures; the whole e2e (100 files, 555 passed; test_file_help_menus fixed - waited for the END state; test_file_browser_edit green alone). The owner tags v1.37.0.
