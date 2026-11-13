# The smart-sweep demo – see it converge on your PC

*Welcome → Smart sweep demo.* In under a minute on an ordinary laptop, watch the loop of *Next runs to try* and
*Launcher mode* find the gains three drones can share – and see what it saves compared with running the whole
grid.

## What it shows

- The **simulation is a real program** (`examples/smart_sweep_demo/sim.py`, standard library only): it reads one
  JSON parameters file and writes one CSV row named by the run. It is run on a local pool of workers – you see
  them fill and empty.
- **Round 1** runs a coarse start grid (4 × 4 × 4 gain values × each drone's scenarios: 768 runs).
- **Each next round** proposes 20 candidate values (× 12 runs) where they help most: around the best, at the
  edge of the constraints, where a drone has not run.
- The **reference** is the whole fine grid (21 × 21 × 21 = 9 261 values × 12 = 111 132 runs) computed once in
  memory with the same formulas – only to measure, never to propose.

## How to read it

- **The convergence chart**: x = runs executed, y = the best (worst-drone) settling time found so far; the dashed
  line is the full-grid optimum; the marker at the right is where the full grid would finish.
- **The gain space**: two of the three gains on the axes (the third on the slider); the values tried, coloured by
  round, filled when they hold for every drone; the current best; the true optimum as a ring.
- **The sentence** is computed from the numbers, e.g. *"Found the full-grid optimum within 0.5 % after 1 728
  runs – the full grid needs 9 261 × 12 = 111 132 runs (≈ 64× fewer)."*

*Next round* runs one round; *Run until converged* stops when the best has not changed for two rounds, when
nothing is left to propose, or at the round limit; *Reset* starts again. It runs in `~/.signalviewer/
smart_sweep_demo`, never in the installed examples.

## Without the app

```bash
python -m signalviewer.study demo examples/smart_sweep_demo/demo.svstudy.json
```

prints one line per round (runs, best, gap to the full-grid optimum) and the same sentence.

## The loop – the same for your own program

The demo is one case of **the loop**, which any study in *Sweeps → Common parameters* can run (*Run the loop*):

1. Signal Viewer proposes the next runs (the gains to try, each with its reason);
2. it writes one parameters file per run and starts **the command** of the study – your program on this PC
   (*on this PC*, N runs at a time) or your farm's launcher;
3. it **waits for the result files** to appear in the results folder (`results/{{table}}/{{run_id}}*`), reads them;
4. it ranks every value tried so far and proposes again – until the best has not changed for two rounds, nothing
   is left to try, or the round limit. *Stop* stops after the running round; the loop can be started again later.

The panel shows the exact command, where the results are read from, the runs done / running / failed, the best so
far, the convergence and every round.

## Make it yours

In the demo, *How this demo works → Copy the demo to a folder…* copies the study and `sim.py` into a new folder and
opens it in *Common parameters*, nothing run yet. There, under **Runs**:

- **The command** – one argument per line, run without a shell, e.g.
  `python` · `{{study_dir}}/my_sim.py` · `{{params_file}}` (`{{study_dir}}` is the study's folder; the command runs in
  the round's folder);
- **Where it runs** – *on this PC* (how many at a time) or *your launcher / farm* (once per round with a list file,
  or once per run);
- **Results** – where a run's result file appears;
- each table's **parameters file** – a template with `{{column}}` placeholders.

Then *Run the loop*. If no run of a round gives a result, the loop stops and shows the end of the command's output.

## Your own program

Keep the contract – read the parameters file, write one CSV row (inputs, outputs, `run_id`) where `out` says –
and change the study's `launcher.submit` to run it, e.g. `["python", "my_sim.py", "{{params_file}}"]`. To run the
same study on your farm, change the `launcher` block to your launcher's command (see *Launcher mode*).
