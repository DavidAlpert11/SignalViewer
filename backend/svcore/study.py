"""The study file (W14, W15, W17, W18): one definition of a "one parameter set for many systems" question.

A study (``<name>.svstudy.json``, JSON, ``version: 1``, schema ``docs/dev/study.schema.json``) is built and
saved in the Sweeps panel; the same file drives the panel, the API (``/api/sweeps/*``) and the command line
(``python -m signalviewer.study``). It holds:

* ``tables``  - N sweep tables (paths or globs relative to the study file: new result files in the folder are
  picked up on the next open), each with its column roles, name mapping, active scenarios, constraints,
  objective and aggregation over scenarios;
* ``shared``  - the shared parameters S (one value chosen for all tables) and their matching tolerance;
* ``combine`` - how the tables' scores are combined (min of the worst table, or a Pareto front);
* ``search``  - the space new runs are proposed in (W15);
* ``next``    - the next-run settings (batch size counted in candidate values of S);
* ``launcher``- how runs are handed to the user's launcher application (W17);
* ``start``   - round 1 of a study that has no runs yet: a start grid and each table's scenarios (C1);
* ``demo``    - the smart-sweep demo's reference settings (W18);
* ``history`` - written by the app: each round's proposals and their state.

Loading is backward compatible: unknown keys are kept (``extra``) and written back; missing keys take their
defaults. Nothing here computes anything - see ``svcore/sweeps_common.py`` (W14), ``sweeps_next.py`` (W15),
``launcher.py`` (W17) and ``demo.py`` (W18).
"""
from __future__ import annotations

import dataclasses
import glob
import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Type, TypeVar

STUDY_VERSION = 1
STUDY_SUFFIX = ".svstudy.json"
ROLES = ("shared", "scenario", "local", "output", "ignore")
REASONS = ("refine", "boundary", "gap", "start")
RUN_STATES = ("pending", "submitted", "done", "failed", "partly done")

T = TypeVar("T")


@dataclass
class Objective:
    expr: str = ""                     # an expression over the row's columns (svcore/formula.py syntax)
    sense: str = "min"                 # "min" | "max"
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TableSpec:
    id: str = ""                       # short, stable: used in run ids and file names
    name: str = ""                     # shown to the user
    paths: List[str] = field(default_factory=list)       # files or globs, relative to the study file
    rename: Dict[str, str] = field(default_factory=dict)  # this table's column -> the common name (mapping)
    roles: Dict[str, str] = field(default_factory=dict)   # common column name -> one of ROLES (missing: default)
    drop: Dict[str, List[Any]] = field(default_factory=dict)  # scenario column -> values left out (inactive)
    constraints: List[str] = field(default_factory=list)  # boolean expressions, all must hold
    objective: Objective = field(default_factory=Objective)
    aggregate: str = "worst"           # over scenarios: "worst" | "mean"
    sim_exe: str = ""                  # W17: this table's simulation program (launcher's {{sim_exe}})
    params_template: str = ""          # W17: inline template for one run's parameters file (overrides the launcher's)
    params_template_file: str = ""     # W17: or a template file, relative to the study file
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SharedParam:
    name: str = ""
    tolerance: float = 0.0             # 0 = exact value matching
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Combine:
    mode: str = "auto"                 # "auto" (same objective everywhere -> minworst, else pareto) | "minworst" | "pareto"
    weights: Dict[str, float] = field(default_factory=dict)   # table id -> weight on its min-max normalised score
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchParam:
    min: Optional[float] = None
    max: Optional[float] = None
    step: Optional[float] = None       # the smallest step a proposal may use
    values: Optional[List[float]] = None   # or an explicit list of allowed values
    integer: bool = False
    log: bool = False
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Search:
    params: Dict[str, SearchParam] = field(default_factory=dict)   # shared parameter -> its space
    constraints: List[str] = field(default_factory=list)          # on S itself, e.g. "Kp * Ki < 3"
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class NextSettings:
    batch: int = 20                    # candidate values of S per round (each expands to its runs in every table)
    mix: Dict[str, float] = field(default_factory=lambda: {"refine": 0.5, "boundary": 0.3, "gap": 0.2})
    folder: str = "next/round_{{round}}"   # relative to the study file
    columns: Optional[List[str]] = None    # None = the table's own input columns + run_id, reason, round
    format: str = "csv"                # "csv" | "xlsx"
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Results:
    glob: str = "results/{{table}}/{{run_id}}*"
    format: str = "csv_row"            # "csv_row" | "csv_series" | "json" | "loader"
    reduce: Dict[str, str] = field(default_factory=dict)      # csv_series: output -> expression over the series
    json_keys: Dict[str, str] = field(default_factory=dict)   # json: output -> key path ("a.b.c")
    converter: List[str] = field(default_factory=list)        # optional command: gets the path, prints one CSV row
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Status:
    failed_glob: str = ""              # a file that marks a failed run
    timeout_s: Optional[float] = None  # per round
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Launcher:
    params_template: str = ""          # inline text template ({{name}}, {{run_id}}, {{table}}, {{round}})
    params_template_file: str = ""     # or a file, relative to the study file
    params_name: str = ""              # default "{{table}}/{{run_id}}.xml" (".json" for a JSON template)
    submit: List[str] = field(default_factory=list)   # argument list (no shell): {{round_dir}} {{params_files}} {{sim_exe}} {{run_id}} {{params_file}}
    submit_mode: str = "round"         # "round" | "run"
    sim_exe: str = ""
    results: Results = field(default_factory=Results)
    status: Status = field(default_factory=Status)
    local_workers: Optional[int] = None    # set: a local process pool of that size runs `submit` per run
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Demo:
    sleep_ms: int = 30                 # added to each simulated run, to make the workers visible
    noise: float = 0.01                # relative seeded noise on the outputs (0 = off)
    seed: int = 1
    tolerance_pct: float = 0.5         # "reached the full-grid optimum" = within this % of it
    max_rounds: int = 12
    reference: str = "reference.json"  # the cached full-grid reference, next to the study
    start_grid: int = 4                # the start round: this many values per shared parameter (L4)
    scenarios: Dict[str, Dict[str, List[Any]]] = field(default_factory=dict)   # table -> scenario / local column -> values (L4)
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Start:
    """Round 1 of a study with no runs yet (any study, C1): per shared parameter how many values of its range
    (``grid``: a count for all, or parameter -> count) x each table's scenario / local columns' values."""
    grid: Any = 4                      # int (every parameter) or {param: n}
    scenarios: Dict[str, Dict[str, List[Any]]] = field(default_factory=dict)   # table -> scenario / local column -> values
    extra: Dict[str, Any] = field(default_factory=dict)

    def count(self, name: str) -> int:
        g = self.grid
        n = g.get(name, 4) if isinstance(g, dict) else g
        return max(1, int(n))


@dataclass
class Proposal:
    run_id: str = ""
    table: str = ""
    values: Dict[str, Any] = field(default_factory=dict)   # the table's own input columns -> value
    reason: str = "refine"             # one of REASONS
    state: str = "pending"             # one of RUN_STATES
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Round:
    round: int = 0
    date: str = ""
    folder: str = ""
    proposals: List[Proposal] = field(default_factory=list)
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Study:
    version: int = STUDY_VERSION
    name: str = ""
    tables: List[TableSpec] = field(default_factory=list)
    shared: List[SharedParam] = field(default_factory=list)
    combine: Combine = field(default_factory=Combine)
    search: Search = field(default_factory=Search)
    next: NextSettings = field(default_factory=NextSettings)
    launcher: Launcher = field(default_factory=Launcher)
    start: Optional[Start] = None
    demo: Optional[Demo] = None
    history: List[Round] = field(default_factory=list)
    extra: Dict[str, Any] = field(default_factory=dict)
    path: str = ""                     # where it was read from (not saved)

    @property
    def folder(self) -> str:
        return os.path.dirname(os.path.abspath(self.path)) if self.path else os.getcwd()

    def table(self, tid: str) -> TableSpec:
        for t in self.tables:
            if t.id == tid:
                return t
        raise KeyError(f"No table '{tid}' in the study (tables: {', '.join(t.id for t in self.tables)}).")

    def table_files(self, t: TableSpec) -> List[str]:
        """The files of a table now: its globs expanded (relative to the study file), sorted, each once."""
        out: List[str] = []
        for p in t.paths:
            full = p if os.path.isabs(p) else os.path.join(self.folder, p)
            hits = sorted(glob.glob(full)) if any(c in p for c in "*?[") else ([full] if os.path.isfile(full) else [])
            out += [os.path.abspath(h) for h in hits if os.path.abspath(h) not in out]
        return out

    def start_plan(self) -> Optional[Start]:
        """The start round as the study says it: ``start`` first, else the demo's ``start_grid`` / ``scenarios``
        (studies written before C1); None when neither says the scenarios."""
        if self.start is not None:
            return self.start
        if self.demo is not None and self.demo.scenarios:
            return Start(grid=int(self.demo.start_grid), scenarios=self.demo.scenarios)
        return None

    def pending(self) -> List[Proposal]:
        return [p for r in self.history for p in r.proposals if p.state in ("pending", "submitted")]


# ------------------------------------------------------------------ dict <-> dataclass (unknown keys kept)

_NESTED: Dict[Any, Dict[str, Any]] = {}


def _field_types(cls) -> Dict[str, Any]:
    if cls not in _NESTED:
        import typing
        _NESTED[cls] = typing.get_type_hints(cls)
    return _NESTED[cls]


def _build(tp: Any, v: Any) -> Any:
    import typing
    origin = typing.get_origin(tp)
    args = typing.get_args(tp)
    if origin is typing.Union:                       # Optional[X]
        inner = [a for a in args if a is not type(None)]
        return None if v is None else _build(inner[0], v)
    if dataclasses.is_dataclass(tp) and isinstance(tp, type):
        return from_dict(tp, v if isinstance(v, dict) else {})
    if origin in (list, List) and args and isinstance(args[0], type) and dataclasses.is_dataclass(args[0]):
        item: Any = args[0]
        return [from_dict(item, x if isinstance(x, dict) else {}) for x in (v or [])]
    if origin in (dict, Dict) and len(args) == 2 and isinstance(args[1], type) and dataclasses.is_dataclass(args[1]):
        val: Any = args[1]
        return {k: from_dict(val, x if isinstance(x, dict) else {}) for k, x in (v or {}).items()}
    return v


def from_dict(cls: Type[T], d: Dict[str, Any]) -> T:
    """A dataclass from a dict: known keys typed (nested blocks too), missing keys defaulted, unknown kept in `extra`."""
    hints = _field_types(cls)
    kw: Dict[str, Any] = {}
    extra: Dict[str, Any] = {}
    for k, v in d.items():
        if k in hints and k not in ("extra", "path"):
            kw[k] = _build(hints[k], v)
        else:
            extra[k] = v
    obj = cls(**kw)
    if "extra" in hints:
        obj.extra = extra   # type: ignore[attr-defined]
    return obj


def to_dict(obj: Any) -> Any:
    """Back to plain JSON values, the unknown keys of `extra` written where they were."""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        out: Dict[str, Any] = {}
        for f in dataclasses.fields(obj):
            if f.name in ("extra", "path"):
                continue
            out[f.name] = to_dict(getattr(obj, f.name))
        out.update(getattr(obj, "extra", {}) or {})
        return out
    if isinstance(obj, list):
        return [to_dict(x) for x in obj]
    if isinstance(obj, dict):
        return {k: to_dict(v) for k, v in obj.items()}
    return obj


def defaults() -> Study:
    return Study()


def loads(text: str, path: str = "") -> Study:
    d = json.loads(text)
    if not isinstance(d, dict):
        raise ValueError("A study file holds one JSON object.")
    v = d.get("version", STUDY_VERSION)
    if not isinstance(v, int) or v > STUDY_VERSION:
        raise ValueError(f"This study file is version {v}; this Signal Viewer reads version {STUDY_VERSION}. "
                         "Update Signal Viewer to open it.")
    s = from_dict(Study, d)
    s.version = STUDY_VERSION
    s.path = path
    return s


def load(path: str) -> Study:
    with open(path, encoding="utf-8") as f:
        return loads(f.read(), os.path.abspath(path))


def dumps(s: Study) -> str:
    return json.dumps(to_dict(s), indent=2, ensure_ascii=False)


def save(s: Study, path: Optional[str] = None) -> str:
    """Written whole and then renamed into place (a crash never leaves half a study)."""
    target = os.path.abspath(path or s.path)
    if not target:
        raise ValueError("No path to save the study to.")
    tmp = target + ".tmp"
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(dumps(s))
    os.replace(tmp, target)
    s.path = target
    return target
