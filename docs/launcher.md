# Run the study on your farm – Launcher mode

Your farm already runs simulations through **your launcher application**: it takes the simulation program and a
parameters file per run. Signal Viewer does not replace it and is never installed on the compute nodes. It runs
in one place (your laptop with the Portable, or one management machine) and speaks the launcher's language:

```
study ─► one parameters file per run ─► your launcher (sim.exe + params) ─► the farm
  ▲                                                                          │
  └──────────── results, read from where the runs already write them ◄──────┘
```

Everything about your launcher is in the study's `launcher` block – there is no launcher-specific code.

## The owner's checklist (do this once)

1. **Take one real parameters file** your launcher accepts (XML or JSON).
2. **Replace its values with placeholders**: `<Kp>1.2</Kp>` → `<Kp>{{Kp}}</Kp>`. A placeholder is a column name
   of that table (its own name, e.g. `{{P_gain}}` in a table that calls it so), or `{{run_id}}`, `{{table}}`,
   `{{round}}`. Values are escaped for the file's format (XML entities in `.xml`, JSON rules in `.json`). Save it
   next to the study and set `params_template_file` (per table if the tables need different files).
3. **Set `submit`** to the launcher's command line, as a list (it is run without a shell):
   ```json
   "submit": ["C:/Tools/Launcher/launcher.exe", "--exe", "{{sim_exe}}", "--list", "{{params_files}}"],
   "submit_mode": "round"
   ```
   `round`: one command per table, `{{params_files}}` is a text file listing that table's parameter files.
   `run`: one command per run, with `{{params_file}}` and `{{run_id}}`. Also: `{{round_dir}}`, `{{study_dir}}`.
4. **Set `results`** to where a run's result appears, with `{{run_id}}` (default
   `results/{{table}}/{{run_id}}*`, relative to the study), and its format: a CSV row, a CSV time series with
   `reduce` (`{"overshoot": "max(roll)"}`), JSON with `json_keys` (`{"overshoot": "out.os"}`), any file the app
   reads (`loader`), or a `converter` command that prints one CSV row. A result is found by `run_id`, else by the
   run's input values.
5. **Run a round of 3** (set `next.batch` to 3), *Send to launcher*, and check that every run turns *done*.

What comes back is collected into `next/round_<k>/collected_<table>.csv`: add `next/round_*/collected_<table>.csv`
to each table's paths and every round's results join the ranking.

Optional: `status.failed_glob` (a file that marks a failed run), `status.timeout_s` (per round),
`local_workers` (run the command per run on this PC with N workers – the same path, without a farm).

## In the app and on the command line

*Sweeps → Common parameters → Send to launcher* shows the exact command once per session, runs it, and shows each
run as *submitted / done / failed / missing*.

```bash
python -m signalviewer.study submit drones.svstudy.json [--yes]     # shows the command; asks unless --yes
python -m signalviewer.study wait   drones.svstudy.json             # 0 all done, 4 some failed, 5 timed out
python -m signalviewer.study loop   drones.svstudy.json --max-rounds 5 [--local]
```

From the Portable: `SignalViewer.exe study …` (no Python needed).

**Safety:** the command comes only from the study file you saved; nothing from a table or a result becomes a
command; there is no shell; the app listens only on this computer.

**Try it without a farm:** `tools/launcher_mock.py` reads the parameter files (XML or JSON), runs the toy drone
model (or `--exe your_sim.exe`) and writes the results; `--fail-rate 0.1` fails some runs on purpose.

**HPC Pack directly** (not verified – no cluster was available): `tools/hpc/run_one.ps1` is one task of a
parametric sweep job that writes one run's parameters from a template and runs the simulation.
