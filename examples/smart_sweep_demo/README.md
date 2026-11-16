# Smart-sweep demo – run it yourself

Three files make the whole chain, Python 3.8+ only (nothing to install):

| File | What it is |
|---|---|
| `sim.py` | **One simulation.** Reads one JSON file with every input of one run, writes one CSV row: the inputs and the outputs. |
| `sweep_wrapper.py` | **The wrapper.** Gets many sets of inputs, runs `sim.py` once for each, collects the rows into the sweep's table. |
| `grid.txt` | **The inputs**, one per line, MATLAB-style: `Kp: 0.5, 1, 2:0.5:4` (start:step:end), `mode: calm, gusty`. |

```
cd examples/smart_sweep_demo
python sweep_wrapper.py --spec grid.txt --set table=A --out my_sweep.csv
```

126 runs in under a second; run the same command again and only the missing runs are run. Open `my_sweep.csv`
in Signal Viewer → Sweeps to see which settings hold.

Other ways to give the inputs:

```
python sweep_wrapper.py --inputs runs.csv --out my_sweep.csv          # a table: one run per row
python sweep_wrapper.py --list params_files.txt                       # JSON files already written (what the app passes)
```

## Your own simulation

Copy `sweep_wrapper.py` next to your program and tell it how to run one simulation – `{params}` is the JSON file:

```
python sweep_wrapper.py --spec grid.txt --out sweep.csv --sim "python my_sim.py {params}"
python sweep_wrapper.py --spec grid.txt --out sweep.csv --sim "matlab -batch run_one('{params}')"
```

Your program reads the JSON (`json.load`, MATLAB `jsondecode(fileread(p))`), runs, and writes one CSV row – a header
and one line with the inputs, the outputs and `run_id` – to the path under `"out"`.

From the app: Sweeps → a study → *How to run* → **A wrapper on this PC**. Each round the app writes one JSON file per
run and runs the wrapper on their list (`--list {{params_files}}`); the rows come back into the study. *Put the
example wrapper beside the study* copies this file there for you. The demo itself runs its rounds this way.
