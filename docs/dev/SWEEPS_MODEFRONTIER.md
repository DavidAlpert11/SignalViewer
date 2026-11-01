# Sweeps toward modeFRONTIER — capability map, plan (MF01–MF10), design

Owner's request (2026-11-01): every capability of modeFRONTIER (ESTECO) should be possible in
Sweeps. This file maps them against what Sweeps does today, orders the work, and proposes a design.

**Source caveat.** The capability list below was written from general knowledge of modeFRONTIER
(written without web access, as of mid-2026), not from ESTECO's current documentation. Check it
against the current product documentation before a task is started; names of algorithms and nodes
change between versions.

**What we will not copy.** modeFRONTIER's own algorithms (pilOPT, MOGA-II, the evolutionary design
surrogate…) are proprietary. We give the same *capability* with open methods (scipy, scikit-learn,
pymoo, SALib - licences to be checked against `requirements.txt` policy before adding any), and
we name them by what they do, not by a brand.

## 1. The difference in one sentence

modeFRONTIER **runs** the simulation: a workflow sends each design to the solver, reads the
results back and lets an algorithm choose the next design. Sweeps today **reads** a results table
(sets × scenarios) and analyses it - goals, conditions, Pareto, maps, robustness, Explore, *Next
runs* suggestions, report. So the analysis side is close; the generating side (DOE, run, loop) is
what is missing.

## 2. Capability map

Status: **Have** · **Part** (some of it) · **Missing**.

| Area | modeFRONTIER | Sweeps today | Status | Task |
|---|---|---|---|---|
| Problem definition | Input variables (continuous, discrete, categorical; range, base, step), outputs, objectives (min/max), constraints (≤, ≥, =, with tolerance) | Roles of columns, goals with direction / weight / threshold, conditions (`<=` …, all / any scenario), limits in Explore | Part - sliders only, spread over steps | MF01 |
| Workflow / process integration | Graph editor; nodes for scripts, Python, MATLAB/Simulink, Excel, CAE tools; input templates, output parsing; logic and sub-processes | - | Missing | MF06 |
| Execution | Local parallel, queues (SLURM, PBS, LSF), failed-design handling, design cache | - | Missing | MF06 |
| DOE | Random, Sobol, Latin hypercube (uniform), full / reduced factorial, Box-Behnken, central composite, Taguchi, D-optimal, incremental space filler, user table | *Next runs*: refine / robust / best suggestions on the grid | Part | MF03 |
| Optimization | Single and multi-objective; genetic (MOGA, NSGA-II), simulated annealing, particle swarm, evolution strategies, simplex, gradient (BFGS, SQP), surrogate-assisted, an "autonomous" hybrid | Ranking and Pareto of existing sets; suggestions of next sets | Part (no loop) | MF07 |
| Response surfaces | Polynomial, Kriging, RBF, neural network, k-nearest, stepwise regression; validation (leave-one-out, residuals); virtual optimization on the surface | Maps interpolate between grid points only | Missing | MF04 |
| Sensitivity / statistics | Correlation matrix, main and interaction effects, t-test, ANOVA, Sobol indices | *Which parameter matters* (`effects`) | Part | MF05 |
| Charts | Design table, scatter, scatter matrix, parallel coordinates, bubble (4D), history, Pareto, 3D surface, contour, histogram, box, PDF / CDF, broken constraints; linked selection | Parallel plot, maps, points, Pareto, tables, convergence (journal), filters | Part | MF02 |
| Clustering / reduction | k-means, hierarchical, self-organizing maps, PCA | - | Missing | MF09 |
| Decision making (MCDM) | Preferences by pairwise comparison, utility functions, ranking | Weights and thresholds (Explore), best set | Part | MF10 |
| Robust design / reliability | Uncertain inputs as distributions, Monte Carlo / LHS sampling, mean and spread as objectives, reliability (probability of failure) | Tolerance per parameter on the grid, worst case (`robustness`) | Part | MF08 |
| Project, report, reuse | Project database, design DB, sessions, templates, reports | `.svsweep`, autosave, undo, templates, journal, report with provenance | Have | - |

## 3. Order and why

1. **MF01 first** - the owner asked for the table view; it is also the screen every later task
   writes into (DOE ranges, optimizer bounds, distributions all live in the same rows).
2. **MF02, MF05** - analysis of tables we already read; no new dependencies of weight.
3. **MF03 DOE** with export / import closes the loop *without* running anything: generate the
   sets, the user runs them in their own tool, imports the table back. Most of modeFRONTIER's value
   for a team that already has a run script.
4. **MF04 surrogates** - then optimization can run *virtually* on the surface (MF07 part 1) before
   any runner exists.
5. **MF06 runner**, then **MF07** in the real loop; **MF08, MF09, MF10** after.

## 4. Tasks

### MF01 · The problem as one table — M
**Do:** a *Problem* view in Sweeps: three sections of one table.
- **Parameters:** name · type (continuous / integer / categorical) · min · max · step · base ·
  in the data (`lo – hi`, n values) · a small distribution strip (`Strip`) · on / off.
- **Objectives:** name · min / max · weight · threshold · current best · strip with the threshold.
- **Conditions:** column · op · value · all / any scenario · tolerance · how many sets it cuts.
Every cell is a typed field (Q129's behaviour); the strip is draggable as the slider was. The table
and Explore are two views of one draft (`explore.ts` `Draft`); undo, journal and templates as now.
Columns for later tasks (distribution - MF08, DOE levels - MF03) are hidden until those exist.

### MF02 · More charts, all linked — M
Scatter matrix, histogram / box per column, correlation matrix (Pearson / Spearman), bubble
(x, y, size, colour), 3D surface / contour on a map's grid, *broken conditions* chart (which
condition fails how often). One selection shared by every chart and the table (brushing).

### MF03 · DOE — M
Sobol, Latin hypercube (optimized), random, full / fractional factorial, Box-Behnken, central
composite, D-optimal, *fill the gaps* (space-filling added to existing sets). Input: MF01's
parameters. Output: a sets table, exported through `write_rows` (S17) and as a run list; import of the
results back into the same study, matched by set id. A preview: the sets on the scatter matrix.

### MF04 · Surrogates (response surfaces) — M/L
Per output: polynomial (degree, stepwise), Gaussian process (Kriging), RBF, k-nearest, small
neural net; validation by leave-one-out / k-fold (residual plot, R², the worst points); the
surface on maps and 3D; *virtual optimization*: any MF07 algorithm on the surrogate, its best sets
offered as *Next runs* to verify.

### MF05 · Sensitivity — S/M
Main effects and two-factor interactions (plot), ANOVA table, Sobol first / total indices (on the
data with enough sets, else on an MF04 surrogate), correlation ranking; in the report.

### MF06 · Runner — L
A study can carry a *run step*: a command (script / executable / Python function) per set, an
input file made from a template (`{{param}}`), outputs read by a parser (JSON, CSV, regex, a
SignalViewer file → its metrics through the existing loaders and formulas). Local parallel jobs
(`app/jobs.py` - check it first), timeout, failed set marked not lost, cache by parameter hash,
stop / resume. A queue backend (SLURM) as an option later. Security: commands only from the user's
own study, shown before the first run.

### MF07 · Optimizers in the loop — L (after MF06; virtual part after MF04)
Single-objective: Nelder-Mead, SQP / L-BFGS-B, differential evolution. Multi-objective: NSGA-II /
NSGA-III, MOEA/D, particle swarm. Surrogate-assisted (Bayesian optimization, expected improvement).
An *automatic* choice by the problem (dimensions, objectives, budget). Live: history chart, Pareto
growing, the best set; budget and stop rule; every design in the table as it arrives.

### MF08 · Robust design and reliability — M
A distribution per parameter (normal, uniform, triangular; MF01 column); sampling around a set
(Monte Carlo / LHS, through MF06 or MF04); mean, standard deviation, percentile as objectives;
probability of failing a condition; extends today's tolerance robustness, which stays the grid case.

### MF09 · Clusters, SOM, PCA — M
k-means / hierarchical on chosen columns, the cluster as a colour everywhere; PCA biplot;
self-organizing map (component planes) for many outputs.

### MF10 · Decision making — S/M
Pairwise comparison of objectives (and of a few candidate sets) → weights; utility per objective;
the ranking explained (why set A is above B) in Explore and the report.

## 5. Design

**One flow, five stages** across the top of the Sweeps area, replacing the steps panel's role as
the entry point (the steps stay inside each stage):

`Problem → Design (DOE) → Run → Results → Decide`

A stage that has nothing yet is shown but quiet (*Run - add a run step*); a study made from a
results table, as today, opens at *Results* with *Problem* filled from the roles, so nothing that
works now changes.

**Layout of every stage:** left - the problem table (MF01), collapsible to names only; centre - the
stage's main view (DOE preview / run progress / charts); right - the selected set (today's set
panel). The selection is one, shared by everything (MF02).

**Problem stage** (the first to build, MF01): a dense table, monospace numbers, the strip in the
row; a row's status on its left edge (a limit active, a condition cutting sets); counts at the
section heads (*Conditions 3 - 41 of 120 sets hold*). Editing is in place; nothing opens a dialog.

**Results stage:** a chart grid (1, 2 or 4 panes) where each pane picks its chart type (parallel,
scatter, matrix, map, surface, histogram, Pareto, history); the design table below, synced.

**Decide stage:** Explore as today plus MF10's comparison; the chosen set with its runs and the
*why* line, *Add to report*.
