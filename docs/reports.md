# Writing a report

Since 1.31 a report is a document you write - like Markdown - with your plots, tabs and values in it.
**Report** on the left rail opens it in place of the plots (the same button goes back); you write on the left,
the page it makes is shown on the right as you type, and **HTML**, **PDF** and **Word** save it.

```markdown
# Flight 12 - heavy payload

Roll peaked at **{{ max(Roll) :.1f }}°** at {{ tmax(Roll) :.1f }} s.
The roll error while gusting was {{ rms(Roll - DesRoll, when="Gust") :.2f }}°.

[[Attitude.Roll]]

[[Attitude.Motors | 30..60, no table]]

$$\omega_n = \sqrt{k_p / J}$$
```

A report made before 1.31 (the Report panel's title, introduction, plots and summary) opens as the document that
form made - the same parts in the same order - and only changes when you edit it.

## Plots and tabs: `[[ ]]`

| Write | Puts in |
|---|---|
| `[[Attitude]]` | every plot of the tab *Attitude* (as the old report did: plots unticked there stay out) |
| `[[Attitude.Roll]]` | the plot titled *Roll* in that tab |
| `[[tab2.plot3]]` | by position, when a tab or plot has no name |
| `[[Attitude.Roll \| 10..60]]` | only 10 - 60 s (the plot and its statistics) |
| `[[… \| all]]` | the whole recording (otherwise: the zoom the plot has now) |
| `[[… \| no table]]` / `[[… \| table only]]` | the plot without its statistics table / the table alone |
| `[[notes]]` `[[findings]]` | the notes; the findings with their status |
| `[[investigation]]` `[[process]]` `[[verdict]]` | the investigation's sections, the process in brief, Compare's verdict |

A plot goes on a line of its own. You do not have to type them: the **Insert** list on the left puts a tab or a
plot where the cursor is (click, or drag it into the text), and a plot's ⋯ menu / a tab's right-click menu have
**Add to report**. Typing `[[` offers the names (Tab takes the first).

## Values: `{{ }}`

Signals are written by name, as in formulas (`Roll`, `{Motor 3}`, `{flight_b.bin:Roll}` when two files have one).
Every value is computed on **every sample** - never on what a plot draws.

| Write | Gives |
|---|---|
| `{{ max(Roll) }}` | a statistic: `max min mean rms std range first final samples duration tmax tmin absmax integral` |
| `{{ mean(Speed, 10, 60) }}` | over 10 - 60 s |
| `{{ rms(Roll - DesRoll) }}` | of a formula (the same formulas as *Create signals*) |
| `{{ mean(Speed, when="Cruise") }}` | only while a condition (Investigate) holds |
| `{{ stretches("Gust") }}` / `{{ holds("Gust") }}` | how many times a condition held / for how many seconds |
| `{{ peak = max(Roll) }}` then `{{ peak * 2 }}` | a variable (defined silently, used further on) |
| `{{ max(Roll) :.2f }}` | a format after a colon: `.2f` two decimals, `.3g` three digits, `,d` thousands |

Without a format a value has about four significant digits. *Value…* in the Insert list writes one for you - a
signal, a statistic, the whole recording / between the cursors / what the plot shows (written as numbers, so the
report does not move with the cursors) and an optional condition.


## Ready reports and ready-made parts (1.32)

The **Insert** list on the left starts with what the open files have, found by the signals' names - any recording,
not one format:

![The ready-made parts beside the text, and the automatic report's What to look at](images/48_report_parts.png)

**Ready reports** - one click writes a whole report made of parts: *Automatic report* (everything found),
*Control review*, *Navigation review*, *Comparison of the files* (offered when they fit). A report nobody wrote yet
is replaced; otherwise the parts go in where the cursor is. Edit the result like any text - delete a part, move it,
write around it. **Save as my report template…** keeps your report under a name and offers it again in any
session; a session template saved from the template library carries the report too, and opening it on the next
recording brings the report (only when that session has no report of its own yet).

**Ready-made parts**, by category - each one click (or drag) into the text:

| Write | Puts in |
|---|---|
| `[[tracking]]` | **commanded vs actual**: every command and its measured value, paired by name (`DesRoll`/`Roll`, `roll_cmd`/`roll`, `alt_target`/`alt`, `x_setpoint`/`x`…) - RMS and largest error (and when), bias, delay, and for each step of the command the overshoot and settling time; a table, worst first, and the worst pairs plotted (the command dashed, the error on the right axis) |
| `[[tracking roll \| tol 2, outside 1%]]` | only the pairs named like *roll*; pass / fail: the error within ±2 for all but 1 % of the time |
| `[[navigation]]` | **navigation errors between objects**: each map object's position, velocity and attitude error against the reference - RMS, mean, 95 %, largest and when - and the worst plotted. The reference is guessed (a simulation's truth, else a receiver), shown in the list and changeable: `[[navigation \| ref GPS, position]]`. With several files, each file against its own reference |
| `[[states]]` `[[states Mode]]` | **the scenario**: each state signal (a mode, a phase, a status - text values) as a time line: every stretch, its duration and where it was (height, distance from the start); most time in, the changes |
| `[[trajectory]]` | the track's facts - duration, distance travelled, farthest from the start, highest, fastest - and the track |
| `[[moments]]` | **special moments** on one time line: the phases, every change of a state (*gps.status OK → LOST*), leaving and returning to the ground, highest, farthest, the largest tracking errors, a signal stuck or at its limit, a gap, a spike |
| `[[differences]]` | **the files compared** (two or more open): see below |
| `[[summary]]` | **what to look at**: the most important things the other parts found, worst first - put it at the top |
| `[[plot Roll, DesRoll \| 10..60]]` | a plot made from names, in no tab; a name in several files is drawn from each; `[[plot xy Lon, Lat]]` |

Options after `|`, separated by commas: `top 5` (how many plotted), `table` (tables only), `tol 2`, `outside 1%`,
`skip yaw`, `ref NAME`, `base FILE`, `position` / `velocity` / `attitude`, `min 2s` (states shorter than that not
listed). A part that finds nothing says so in one line; an unknown option is a red ⚠ that lists the known ones.
Every number is computed on every sample.

### Comparing files: the main differences and the central region of the change

![Two runs of one mission: the central region of the change, the signals ranked, where the files differ](images/49_report_differences.png)

`[[differences]]` compares every signal the files share (by name, whatever the unit's spelling) with the
**baseline** - the file whose name says so (*ref*, *baseline*, *golden*, *nominal*), else the first; the list
lets you choose another (`| base FILE`). For each signal, the difference on every sample is measured **as a share
of how much the signal moves** (its 1st–99th percentile span - one spike does not set it):

- **overall** - over the whole common time;
- **in its region** - in the 1 % slices of time where it is largest. A signal the same everywhere but in one place
  has a small overall and a large value here: it is not lost among signals that differ a little all the time;
- its **region** (where the difference is above a quarter of its peak) and when it **first diverged** (left its
  own usual difference and stayed out).

Signals are *the same* under 2 %, *small* to 10 %, *large* above (`small 1%, large 5%` to change). Then: **the
central region of the change** - the window where the top signals' differences are largest together - and the
first signal to diverge; a table of the top signals (one per family: *IMU.AccX/Y/Z* is one row); a plot of
*where the files differ* over the whole time; each top signal **zoomed on its own region** with every file's line;
states whose sequence differs (*OK → LOST → OK*); **parameters that differ** (a log's parameters, a file's
settings, numbers in the file names - often the cause); and the rest of the differences in a table at the end.
Time and counter signals are not compared; signals in one file only are listed.

![The same automatic report in Hebrew](images/50_report_parts_hebrew.png)

### The demo recordings

`examples/report_demo` has two recordings of one generic test mission (`tools/make_report_demo.py` writes them):
a scenario (`mission.phase`: IDLE, TAKEOFF, CRUISE, TURN, DESCENT, LAND), four commanded / measured pairs
(`ctrl.alt_cmd`/`ctrl.alt`, speed, roll with steps, pitch), three objects (`sim.*` the truth, `nav.*` the estimate,
`gps.*` the receiver) and a receiver status. `mission_gust.csv` is the same mission with a gust at 140–160 s and the
receiver lost at 150–170 s. Open both, *Report*, *Automatic report*.

## Tables and pictures from outside

**Paste a table** from Word, Excel, LibreOffice or a web page: it becomes a Markdown table (Hebrew kept; a merged
cell is repeated in the cells it covered, and a note says so); headings, lists, bold and italic from Word come too.
Ctrl+Shift+V pastes plain text. **A picture** - paste it (a screenshot), drop it on the text, or the 🖼 button -
is kept **inside the session** (made smaller, at most 2000 px; up to 5 MB each, 20 MB in all) and written
`![name](asset:…)`; it travels with the session and the template and goes into the page, the PDF and Word. A
picture can still be linked from a file: `![name](C:/pictures/rig.png)`.

## Writing

`# Heading`, `**bold**`, `*italic*`, `` `code` ``, `- list`, `1. numbered`, tables (`| a | b |` then `|---|---|`),
`> quote`, callouts `> [!NOTE]` `> [!TIP]` `> [!WARNING]` `> [!IMPORTANT]` `> [!FINDING]`, `[a link](https://…)`,
a picture `![alt](C:/pictures/rig.png)` (put into the page; or pasted - see above), `---` a line, `\newpage` a page break (PDF, Word), and
math: `$x^2$` in a line, `$$ … $$` on its own (fractions, roots, sums, integrals, Greek letters - matplotlib's
mathtext, the same in the page, the PDF and Word; no matrices). Each paragraph reads right-to-left when it starts
in Hebrew, left-to-right in English.

## When something cannot be filled

A plot or tab that is not there, a signal of a file that is closed, a condition that does not exist: it shows as a
red ⚠ with the reason, in the preview and in the file - never an empty cell or an old number - and the head of the
screen counts them. Saving asks first. Each edit is one Undo step (after a pause in typing).
