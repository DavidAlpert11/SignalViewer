> **2026-11-01: history.** After Milestone 23 the owner had the Sweeps area redone simply and the old
> tools deleted (ROADMAP "Sweeps redesign"): of MF00-MF11 only the groups (MF00), the charts desk (MF02,
> with MF09's clusters / PCA / SOM as chart kinds) and next runs remain. The rest of this file is the
> research and plan as it was - read it as background, not as what the app has.

# Sweeps toward modeFRONTIER — how it explores results, what we copy, and the brief for the agent

Owner's request (2026-11-01): every capability of modeFRONTIER (ESTECO) should be possible in
Sweeps - the same capability with open libraries, no copied proprietary algorithms. This file is
(1) what modeFRONTIER's exploration actually is, checked against sources, (2) the capability map,
(3) the design decision, (4) MF00-MF11, and (5) **the brief for the agent that implements it**.

Revised 2026-11-01 with web research (the first version was written from memory). Each finding
below is marked **[V]** verified in a source listed in §7, or **[U]** unverified (memory, or
seen only in an old version) - check [U] items before building on them.

## 1. How modeFRONTIER explores - findings

**Three environments.** [V] *Workflow* (define inputs, solver nodes, outputs, objectives,
constraints, DOE + scheduler), *Run Analysis* (live dashboard of gadgets while designs run:
scatter / bubble, multi-history, design data, logs; refresh rate; stop marks running designs as
error), *Design Space* (post-processing). Newer releases add a *Planner* - several run
configurations ("plans") on one workflow [V, UM25] - and *sessions* whose evaluated designs land in
their own *session table* for comparing runs [V, VOLTA 2019 release note].

**The Design Space is table-oriented.** [V] Every chart is built *on a table*; remove the table and
its charts go. Tables: the *Designs table* (all designs, all variables), the *DOE table* (inputs
only), the *Robust designs table*, and tables the user makes with a *Table Creation Tool*; import /
export, add / edit / remove designs and columns, a *Find* dialog [V, v4 manual TOC]. Panels:
Desktop (the open charts), Explorer tree, *Categories*, Properties, Actions log, Report tool [V].

**What a row shows.** [V, basic training]
- *category* - by default the DOE or scheduler that produced the design; categories are
  user-customisable and act as the colour / grouping key of the charts;
- *feasible* (white) / *unfeasible* (yellow row, the violated constraint cell orange) / *error*
  (red row: an output missing);
- *virtual* (blue font, computed on a response surface) / *real* (black, from the solver);
- *selected* (click on the ID) vs *marked* (a checkbox column) - two separate selections.

**Charts and linking.** [V] History, scatter, bubble (4D: x, y, size, colour), parallel
coordinates (filter by ranges per axis; *the filter can be applied to other charts*), scatter
matrix (= correlation matrix + scatter + PDF per variable, Pearson), PDF / histogram, RSM 3D,
contour, function plots, *RSM Explore 3D* (2×2 with input sliders and a probe), RSM distance and
residual charts, effect table. Newer: comparison table (designs side by side, differences
highlighted) and performance history [V, VOLTA]. A user report [V, UM26] says the Design Space
*needs several charts to analyse one output and is not easy to navigate*, and that teams move to
the Python console (pyCONSOLE) for flexibility - a gap worth not copying.

**DOE.** [V] Families: space fillers, statistical, optimal, robustness. Named: full / reduced
factorial, Latin square, uniform Latin hypercube (low correlation, max distance), random / Sobol,
*incremental space filler* (adds points maximising min distance from existing ones, rejects
unfeasible). Guidance: statistics → factorial; surrogate training → uniform space filling;
optimisers → ULH / random / Sobol; rule of thumb size `2 × inputs × objectives`. [V] Box-Behnken,
central composite, full / reduced factorial, Plackett-Burman, Taguchi orthogonal arrays, Latin
hypercube - Monte Carlo for robustness (academy.esteco.com, *Design of experiments*, read 2026-11-01).
[U] D-optimal.

**Optimisers.** [V] Local / global × single / multi: BFGS, NLPQLP, SQP variants,
Levenberg-Marquardt, Powell, simplex; MOGA-II, NSGA-II, ARMOGA, MOPSO, ES, MOSA, MOGT, hybrid,
FAST (surrogate-assisted), pilOPT (self-adapting, mixes real and virtual evaluations, one
parameter: budget) - pilOPT, MOGA-II, FAST, SAnGeA are **proprietary**. pySCHEDULER lets a
Python optimiser drive the evaluations [V].

**Response surfaces (RSM).** [V] Interpolating (Shepard / k-nearest, Kriging, RBF) vs
approximating (polynomial SVD, Gaussian processes, neural nets, evolutionary design). Training
by wizard: dataset → (optional screening) → outputs, inputs, algorithms → split for validation →
train → *validation table* comparing models (mean abs / relative / normalised error, R², AIC;
best cells shaded) → *favourite* model per output. Then *virtual optimisation* on the favourites;
the virtual Pareto designs are re-run on the real solver ("Quick Run") and compared [V].

**Sensitivity / statistics.** [V] Scatter matrix (Pearson), t-Student and main-effects charts
(older), *Sensitivity Analysis tool*: SS-ANOVA (smoothing-spline ANOVA: % of variance per main
effect and interaction, a screening threshold to drop weak inputs) and a proprietary
PCE-based method; *effect table* chart. [U] ANOVA table in the classic sense.

**Multivariate.** [V] Clustering + self-organising maps (MVA), PCA, multidimensional scaling.

**Decision (MCDM).** [V] Wizard: attributes with min / max → designs to rank → algorithm →
weights, preference and indifference margins by sliders → ranking. Algorithms: linear MCDM,
GA-based MCDM (from pairwise preferences), Hurwicz, Savage minimax regret; MCDM utility.

**Robust design (RDO / MORDO).** [V] Robust designs table, mean vs standard deviation chart,
DOE families for robustness and reliability. [V] sampling: Monte Carlo, Latin hypercube, polynomial
chaos; uncertain inputs as distributions (normal, uniform...); reliability by Monte Carlo or FORM
(engineering.esteco.com, *Robust design and reliability*; ESTECO UM23 India, technology overview;
read 2026-11-01). Implemented here (MF08): Monte Carlo and Latin hypercube; polynomial chaos and
FORM not done.

## 2. Capability map (corrected)

Status: **Have** · **Part** · **Missing**. Changes from the first version in *italics*.

| Area | modeFRONTIER (verified unless [U]) | Sweeps today | Status | Task |
|---|---|---|---|---|
| Problem | inputs continuous / discrete / *categorical*, range, base; outputs; objectives min / max; constraints | roles, goals, conditions, limits in Explore (sliders) | Part | MF01 |
| *Design status* | *feasible / unfeasible / error, real / virtual, per row; violated cell marked* | holds / fails per condition | Part | MF00 |
| *Groups of designs* | *categories (by generator, customisable), selected vs marked, sub-tables, session tables* | one implicit filter | Missing | **MF00** |
| Workflow / runner | graph of nodes, CAD / CAE / MATLAB / Python nodes, introspection | - | Missing | MF06 |
| *Run monitoring* | *Run Analysis dashboard, live history, logs, stop* | journal (after) | Missing | MF11 |
| DOE | factorial, Latin square, ULH, random, Sobol, incremental space filler; [U] BB, CCD, D-opt | *Next runs* suggestions | Part | MF03 |
| Optimisation | gradient, simplex, GA / ES / PSO / SA, multi-objective, surrogate-assisted, self-adapting | ranking, Pareto of existing | Part | MF07 |
| RSM | k-NN, Kriging, RBF, polynomial, GP, NN; validation table, residual / distance charts, favourite, virtual opt, re-run | maps interpolate | Missing | MF04 |
| Sensitivity | Pearson matrix, main effects, *SS-ANOVA effect table with screening threshold*, PCE | `effects` | Part | MF05 |
| Charts | as §1; *filters shared across charts*; *comparison table* | parallel, maps, Pareto, tables | Part | MF02 |
| Multivariate | clustering, SOM, PCA, *MDS* | k-means, Ward, PCA, classical MDS, SOM (written here), clusters as groups | Have | MF09 |
| MCDM | linear, GA from pairwise, *Hurwicz, Savage regret*, margins | weighted, TOPSIS, Hurwicz, Savage, AHP pairwise weights, indifference margin | Have | MF10 |
| Robust | robust table, mean vs σ, robustness DOE | tolerance + distribution, MC / LHS on a model or run, mean / σ / percentile / P(fail), mean vs σ | Have (no PCE / FORM) | MF08 |
| Project / report | project DB, report tool, actions log | `.svsweep`, journal, report | Have | - |

## 3. Open replacements and licences

Use only these (or equal) and name methods by what they do. **Check each licence again on the
day it is added** (PyPI page + LICENSE file) and record it in `requirements.txt` as the existing
lines do; all are permissive and fit the MIT licence of the project.

| Need | Library (licence as last known - re-check) | Replaces |
|---|---|---|
| Sobol, Halton, LHS (+ optimised), discrepancy | `scipy.stats.qmc` (BSD-3, already a dependency) | ULH, Sobol, random |
| factorial, fractional, Box-Behnken, CCD | `pyDOE3` (BSD-3) - or write them (small) | factorial DOEs |
| max-min distance augment | own code on `scipy.spatial` (BSD-3) | incremental space filler |
| local / global single-objective | `scipy.optimize`: Nelder-Mead, L-BFGS-B, SLSQP, differential evolution (BSD-3) | simplex, BFGS, SQP |
| multi-objective, MCDM helpers | `pymoo` (Apache-2.0): NSGA-II/III, MOEA/D, ASF, pseudo-weights | MOGA-II, NSGA-II, MOPSO… |
| surrogates | `scikit-learn` (BSD-3): GP, k-NN, MLP, polynomial; `scipy.interpolate.RBFInterpolator` | Kriging, RBF, NN, k-NN |
| Bayesian / surrogate-assisted | own EI loop on sklearn GP; or `optuna` (MIT) | FAST, pilOPT (capability only) |
| Sobol indices, Morris | `SALib` (MIT) | sensitivity |
| additive / interaction screening | statsmodels ANOVA + GAM (BSD-3), or spline ANOVA on sklearn splines | SS-ANOVA (method is published, implementation ours) |
| PCE sensitivity | `chaospy` (MIT) | PCE-based (proprietary there) |
| clustering, PCA, MDS | `scikit-learn` | MVA |
| SOM | `MiniSom` (MIT) or ~100 lines of numpy | SOM |
| MCDM | own code: weighted sum, TOPSIS, Hurwicz, Savage, AHP (published methods) | MCDM tools |

Rule: every heavy library is an **optional extra** (`pip install signalviewer[sweeps-opt]`), the
UI says what is missing and how to add it; the app still starts without them.

## 4. The design decision

**"Group of designs" (a group of sets) becomes the central concept - yes.** Reasons from §1: in
modeFRONTIER the unit every chart, RSM, MCDM and sensitivity tool takes as input is a *table of
designs*, and categories / marked / sub-tables / session tables are four overlapping ways of
grouping. We make it **one** concept:

- A **group** = a named set of designs (sets), either a *rule* (live: `conditions hold and
  objective A < x`) or *frozen ids*. Automatic groups: *Imported*, each DOE run, *Suggested*,
  *Virtual* (from a surrogate), *Pareto*, *Holds all conditions*, *Failed / error*.
- **Every tool reads a group and may write a group** (DOE → new group; surrogate optimisation →
  *Virtual* group; *re-run these* → group of real twins; MCDM ranks a group; cluster → one group
  per cluster).
- **Colour = group** everywhere; the **brush** (current selection) is a temporary group that can be
  saved with one click. One brush across all charts and the table (no chart-local filters).
- Charts do **not** belong to a table (avoid "close the table, lose the charts").

**Layout: three areas, not five stages** (mirrors modeFRONTIER's three environments, which the
sources confirm, and drops the stages that had nothing to show):

```
┌ Problem ─┬ Run ─┬ Explore ───────────────────────────────────────────────────────────┐
│ Groups        │ Chart desktop (1/2/4 panes, each: type + group + axes)             │
│ ■ All 120     │  ┌ parallel coords ──────────┐ ┌ scatter A vs B, colour=group ┐    │
│ ■ Holds 41    │  │ brush on axis = filter    │ │ ● Pareto ring, ◇ virtual      │    │
│ ■ DOE-1 60    │  └───────────────────────────┘ └──────────────────────────────┘    │
│ ■ Virtual 15  │ Designs table (synced; row status colour; violated cell marked;     │
│ + save brush  │  real / virtual; category = group chips; selected ≠ marked)         │
│ Tools ▸ DOE · Surrogate · Sensitivity · Cluster · Decide · Compare                  │
└─────────────────────────────────────────────────────────────── selected set ▸ panel ┘
```

- **Problem** = MF01's table (parameters, objectives, conditions) + the run step (MF06).
- **Run** = MF11 live monitor; quiet until a run step exists.
- **Explore** = the design space above; today's Explore (weights, thresholds) becomes the
  *Decide* tool inside it. A study opened from a results table opens here, as today.
- Tools are side sheets, not wizards that hide the charts (the UM26 complaint): each shows its
  input group at the top and its result as a group / column / chart.

## 5. Tasks (order: MF00, MF01, MF02, MF05, MF03, MF04, MF11, MF06, MF07, MF10, MF08, MF09)

- **MF00 Groups and design status — M.** Group model (rule | ids, colour, name, source), automatic
  groups, brush → group, status per set (feasible / fails which condition / error / virtual).
  Saved in `.svsweep` as optional fields (old files open: one group *All*).
- **MF01 Problem as one table — M.** As before; adds *categorical* parameters; Q129's typed fields.
- **MF02 Charts, all linked — M.** Scatter, bubble, scatter matrix (Pearson / Spearman + histograms),
  histogram / PDF, box, contour / 3D on grids, history, comparison table, broken-conditions chart;
  one brush; colour by group.
- **MF03 DOE — M.** §3 methods; preview on the scatter matrix; output = new group, exported as a run
  list; import back matched by set id; *fill the gaps* (max-min augment of an existing group).
- **MF04 Surrogates — M/L.** Train per output on a group; k-fold / held-out validation table (MAE,
  relative, normalised, R²; best marked); residual and predicted-vs-real charts; favourite per
  output; explore panel (sliders + typed values, 2×2: surface, contour, two 1-D cuts); virtual
  optimisation → *Virtual* group → *re-run* list.
- **MF05 Sensitivity — S/M.** Correlation ranking, main and interaction effects, variance share per
  term (ANOVA / additive model) with a screening threshold, Sobol indices (data or surrogate).
- **MF06 Runner — L.** As before (template, parser, parallel, cache, stop / resume, shown before
  first run).
- **MF07 Optimisers — L.** §3; automatic choice by dimension / objectives / budget, every new design
  into the table and a group per run.
- **MF08 Robust — M.** Distributions per parameter, sampling around a set, mean / σ / percentile as
  objectives, probability of failure, mean-vs-σ chart.
- **MF09 Clusters, SOM, PCA, MDS — M.** Each cluster a group.
- **MF10 Decide — S/M.** Weighted sum, TOPSIS, Hurwicz, Savage, pairwise (AHP) weights,
  indifference margin; the ranking explained.
- **MF11 Run monitor — M** (with MF06). Live history per objective, growing Pareto, counts by
  status, log of the failing set, stop.

## 6. Brief for the implementing agent

Read `CLAUDE.md`, `docs/dev/TASKS.md`, this file. Then, per task:

1. **Verify before building.** For any [U] item the task uses, search ESTECO docs / proceedings
   (um2x.esteco.com, academy.esteco.com, engineering.esteco.com) and update §1 with the source.
   Never read or reproduce leaked manuals' text; describe capabilities only.
2. **No proprietary algorithm.** Implement the *capability* with §3; name it by what it does
   (*space-filling sample*, not *ULH*; *self-adapting optimiser*, not *pilOPT*).
3. **Licence gate.** Before adding a dependency: read its LICENSE in the released wheel/sdist;
   permissive only (MIT / BSD / Apache-2.0); add as an optional extra; write the reason and licence
   in the task notes and `requirements.txt` comment.
4. **Groups first.** Every new tool takes a group as input and writes a group / column; no
   tool-private selection. Colour by group, one brush.
5. **Backend does the maths** (`svcore/` + `app/routes/sweeps*.py`), UI gets decimated results;
   long work runs as jobs with progress and cancel.
6. **Test against known answers**: DOE properties (counts, bounds, discrepancy), surrogates on
   analytic functions (R² threshold), Sobol indices of Ishigami, Pareto of ZDT1, MCDM on a
   hand-worked table.
7. **Compatibility**: `.svsweep` new fields optional; an old study opens unchanged in *Explore*.
8. After each task: CLAUDE.md checks, tick ROADMAP, update TASKS.md (state, status, log).

## 7. Sources (read 2026-11-01)

- modeFRONTIER Basic Training (University of Trieste course copy): moodle2.units.it, `mF_basic_uni.pdf`.
- modeFRONTIER 4 User Manual, table of contents (Scribd, doc 141842116) - section names only, old version.
- ESTECO Academy: *Design space exploration - sensitivity analysis*; *Simulation data analytics*.
- ESTECO User Meeting proceedings: UM23 (what's new 2023R2, Python bridges), UM25, UM26 (user report).
- ESTECO news: VOLTA release 2019 Spring (session tables, comparison table, performance history).
- develop3d: Spring release - SS-ANOVA and PCE sensitivity, effect table.
- Ricco, Rigoni, Turco (2013), *Smoothing Spline ANOVA for Variable Screening*, DRNA 6.
- Park (2012), modeFRONTIER CAE examples (MCDM: linear, GA, Hurwicz).
- Brochure mF2016 (profiles: MVA = clustering + SOM, RSM, DOE, sensitivity).
- engineering.esteco.com *Robust design and reliability*; academy.esteco.com *Design of experiments*; um23.esteco.com India proceedings, technology overview (read 2026-11-01, MF08).
Not found / not seen: current online help (behind a login), videos (not viewed). Images seen only as
descriptions in the PDFs.
