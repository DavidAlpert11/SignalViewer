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

## Writing

`# Heading`, `**bold**`, `*italic*`, `` `code` ``, `- list`, `1. numbered`, tables (`| a | b |` then `|---|---|`),
`> quote`, callouts `> [!NOTE]` `> [!TIP]` `> [!WARNING]` `> [!IMPORTANT]` `> [!FINDING]`, `[a link](https://…)`,
a picture `![alt](C:/pictures/rig.png)` (put into the page), `---` a line, `\newpage` a page break (PDF, Word), and
math: `$x^2$` in a line, `$$ … $$` on its own (fractions, roots, sums, integrals, Greek letters - matplotlib's
mathtext, the same in the page, the PDF and Word; no matrices). Each paragraph reads right-to-left when it starts
in Hebrew, left-to-right in English.

## When something cannot be filled

A plot or tab that is not there, a signal of a file that is closed, a condition that does not exist: it shows as a
red ⚠ with the reason, in the preview and in the file - never an empty cell or an old number - and the head of the
screen counts them. Saving asks first. Each edit is one Undo step (after a pause in typing).
