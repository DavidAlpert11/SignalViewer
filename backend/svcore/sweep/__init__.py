"""Sweeps (the run-envelope area): a results table, one row per run - parameters and scenario
columns first, outputs last - read fast, its columns described and their roles guessed.

Not to be confused with svcore/envelope.py (many runs of ONE signal over time, the Monte-Carlo
view in Recordings). Here a run is a row of numbers, not a recording.

Modules
-------
io.py        reading, the Parquet cache
columns.py   describing columns, guessing roles and scales
shape.py     sets, combinations, what is missing
derived.py   new columns: a formula per run, an aggregate per parameter set
evaluate.py  the question - must hold across, goal, conditions - answered per parameter set
encode.py    columns to the page (Float32, base64)
export.py    the re-run list

Reading a big table fast
------------------------
* CSV: Apache Arrow's multi-threaded parser (the same one csv_loader uses), every column at once;
  text columns become dictionary-encoded (a scenario name is stored once, not per row).
* The first read of a big file writes a Parquet copy (zstd) into the cache folder, keyed on path +
  size + mtime: reopening is a column read from a compressed binary file, not a parse.
* Parquet and Excel are read as they are (Excel through pandas: those files are small).

Roles
-----
param   - what we choose (a design parameter)
hold    - what we don't choose and must hold across (scenario, wind, seed...)
output  - a result of the run
id      - one value per row (a run number): not a parameter
ignore  - nothing to say: the same value in every run, or empty

Guess: the outputs are the trailing block - from the first column that looks like a measurement
(many distinct numbers) to the end; before it, grid-like columns are inputs, a name that says
scenario / case / seed... makes an input a `hold`. A constant column is `ignore` wherever it is.
The user corrects the guess once; the study keeps it.
"""
from svcore.sweep.columns import ROLES, SCALES, describe, describe_column, guess_roles, guess_scale  # noqa: F401
from svcore.sweep.io import SweepError, read_table  # noqa: F401
from svcore.sweep.shape import head, summary  # noqa: F401
from svcore.sweep.derived import SET_OPS, DerivedError  # noqa: F401,E402
from svcore.sweep.encode import encode  # noqa: F401,E402
from svcore.sweep.evaluate import QuestionError, answer, prepare, run_rows, set_rows  # noqa: F401,E402
from svcore.sweep.export import rerun_rows, write_csv  # noqa: F401,E402
