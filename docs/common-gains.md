# One parameter set for many systems

*Sweeps → Open ▾ → New study… → I have results*, then add each system's table (*Add table* in the Data step).
You have run a sweep for each of several systems - three drones, say - and they
must all fly with **the same gains**. Each table has its own scenarios (wind, mass), its own limits and its own
goal. Signal Viewer finds the values of the shared parameters that hold in **every** table, and ranks them -
the Results tab **All systems together**, shown when the study has two tables or more (a study with one table
is ranked on its own).

## The question, in a study file

A study (`<name>.svstudy.json`) is built in the app - *Define the problem* in the Data step - and saved with *Study ▾ →
Save*; *Open a saved study* opens it again, and the same file is read by the command line.

| A column is… | Meaning | Example |
|---|---|---|
| **Shared** | In every table (after the names are paired). One value is chosen for all. | Kp, Ki, Kd |
| **Scenario** | This table only. The choice must hold for every value of it you keep. | wind, mass |
| **Local** | This table only. Each table picks its own best value. | a filter |
| **Output** | A result of the run. | overshoot, settling time |

- **Names:** `P_gain` in one table and `Kp` in another are proposed as one name; you confirm.
- **Per table:** the scenario values that count, the constraints (`overshoot < 8`), the goal (minimise
  `settling_time`), and how scenarios combine - the **worst case** (default) or the mean.
- **Tables are paths or globs** next to the study: a new results file in the folder is read on the next open.

## The answer

For each value of the shared parameters that was run:

1. it **holds in a table** when some local value makes every scenario's run exist and meet the constraints
   (a missing run counts as a failure: *not run*);
2. its **score** in that table is the worst (or mean) goal over the scenarios, with the best local value;
3. it **holds for all** when it holds in every table.

With the same goal in every table, the values are ranked by the **worst table**; with different goals they are
ranked on the **Pareto front** (no other value is better in every table). A rejected value says which table,
scenario and constraint failed, and by how much. Only values that were run are chosen - to try new ones, run
the next round from the **Next runs** step (*Run from the app*). *Export CSV…* in the systems together writes the whole ranking; *Study ▾ → Report
of the study…* writes one HTML page of it (each table's goal and limits, the shared answer with each table's
verdict, the rounds run).

## Next runs to try

The **Run** column on the right of the study says what the next round will run, or what is still missing for
it. The next round is a batch of **20 candidate values** (the batch size) of the shared parameters,
each expanded to its runs in every table (its scenarios × local values) - so a batch is a few hundred runs. *Run them* runs it (on this PC's workers or through your farm's
[launcher](launcher.md)); *Only write the files* only writes it for a launcher of your own. Each run has a
reason:

- **refine** - around the best values, at half the local step;
- **boundary** - between a value that holds and a neighbour that fails;
- **gap** - values run in some tables but not in others.

Proposals stay inside the study's search space (bounds, smallest step, allowed values, constraints on the
shared parameters themselves) and are written to `next/round_<k>/<table>.csv` with a `run_id`, `reason` and
`round` column. A proposal still pending is never proposed again; when results come back with the `run_id`
(or the same values) it is marked done.

## The command line

```bash
python -m signalviewer.study rank   drones.svstudy.json [--csv ranking.csv] [--json]
python -m signalviewer.study next   drones.svstudy.json          # writes the round; exit 3 = nothing left
python -m signalviewer.study status drones.svstudy.json
```

`SignalViewer.exe study …` does the same from the Portable. Exit codes: 0 ok, 1 error, 3 nothing left to
propose at the smallest step.

## The example

*Welcome → One gain set for three drones* (`examples/drones/`, made by `tools/make_drone_sweeps.py` from a toy
attitude-loop model): a light quad (wind; overshoot < 8; fastest settling), a heavy hexa (mass × wind;
overshoot < 12 and motor saturation < 0.9; least energy) and a VTOL whose columns are called `P_gain`,
`I_gain`, `D_gain`, with a local filter and a few runs missing.
