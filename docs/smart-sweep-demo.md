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

## Your own program

Keep the contract – read the parameters file, write one CSV row (inputs, outputs, `run_id`) where `out` says –
and change the study's `launcher.submit` to run it, e.g. `["python", "my_sim.py", "{{params_file}}"]`. To run the
same study on your farm, change the `launcher` block to your launcher's command (see *Launcher mode*).
