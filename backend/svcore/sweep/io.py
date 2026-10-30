"""Reading a results table fast (see svcore/sweep/__init__.py)."""
import hashlib
import os

import pandas as pd

try:
    import pyarrow as pa
    import pyarrow.csv as pa_csv
    import pyarrow.parquet as pq
    HAVE_ARROW = True
except ImportError:                     # pragma: no cover - pyarrow is in requirements
    HAVE_ARROW = False

CACHE_DIR = os.path.join(os.environ.get("SV_CACHE_DIR") or os.path.join(os.path.expanduser("~"), ".signalviewer", "cache"), "sweeps")
CACHE_MIN_BYTES = int(float(os.environ.get("SV_SWEEP_CACHE_MIN_MB", "20")) * 1024 * 1024)


class SweepError(ValueError):
    pass


def _cache_path(path: str) -> str:
    st = os.stat(path)
    key = hashlib.sha1(f"{os.path.abspath(path)}|{st.st_size}|{st.st_mtime_ns}".encode()).hexdigest()[:20]
    return os.path.join(CACHE_DIR, key + ".parquet")


def _read_csv(path: str) -> pd.DataFrame:
    if not HAVE_ARROW:
        return pd.read_csv(path, sep=None, engine="python")
    from svcore.csv_loader import detect_delimiter
    delim = detect_delimiter(path)
    table = pa_csv.read_csv(
        path,
        read_options=pa_csv.ReadOptions(use_threads=True, block_size=8 << 20),
        parse_options=pa_csv.ParseOptions(delimiter=delim),
        convert_options=pa_csv.ConvertOptions(strings_can_be_null=True, auto_dict_encode=True, auto_dict_max_cardinality=4096),
    )
    return table.to_pandas(self_destruct=True)


def read_table(path: str, use_cache: bool = True) -> pd.DataFrame:
    """The whole table. Big CSVs go through (and later come from) a Parquet copy in the cache."""
    if not os.path.isfile(path):
        raise SweepError(f"File not found: {path}")
    ext = os.path.splitext(path)[1].lower()
    if ext in (".parquet", ".pq"):
        return pd.read_parquet(path)
    if ext in (".xlsx", ".xls"):
        return pd.read_excel(path)
    big = use_cache and HAVE_ARROW and os.path.getsize(path) >= CACHE_MIN_BYTES
    if big:
        cp = _cache_path(path)
        if os.path.isfile(cp):
            try:
                return pd.read_parquet(cp)
            except Exception:           # a half-written copy: read the CSV again
                os.remove(cp)
    df = _read_csv(path)
    if df.shape[1] == 0 or df.shape[0] == 0:
        raise SweepError("The table is empty.")
    if big:
        try:
            os.makedirs(CACHE_DIR, exist_ok=True)
            tmp = _cache_path(path) + ".part"
            pq.write_table(pa.Table.from_pandas(df, preserve_index=False), tmp, compression="zstd")
            os.replace(tmp, _cache_path(path))
        except OSError:
            pass                        # no room for the copy: the table still opens
    return df




TABLE_EXTS = (".csv", ".tsv", ".txt", ".parquet", ".pq", ".xlsx", ".xls")


def read_folder(folder: str) -> pd.DataFrame:
    """A folder of statistics files (one per run, or a few rows each): read and stacked. Columns
    missing in some files are left empty there; `_file` says where each row came from."""
    names = sorted(n for n in os.listdir(folder) if n.lower().endswith(TABLE_EXTS) and not n.startswith("."))
    if not names:
        raise SweepError("No table files in this folder (CSV, Parquet or Excel).")
    parts = []
    for n in names:
        try:
            d = read_table(os.path.join(folder, n), use_cache=False)
        except Exception as e:          # one bad file: say which
            raise SweepError(f"{n}: {e}") from None
        d["_file"] = n
        parts.append(d)
    return pd.concat(parts, ignore_index=True, sort=False)


def read_any(path: str) -> pd.DataFrame:
    return read_folder(path) if os.path.isdir(path) else read_table(path)


def from_rows(columns, rows) -> pd.DataFrame:
    """A table handed over as rows (another part of the app, e.g. Runs x conditions)."""
    df = pd.DataFrame(rows, columns=columns)
    for c in df.columns:                # numbers as numbers
        conv = pd.to_numeric(df[c], errors="coerce")
        if conv.notna().sum() == df[c].notna().sum():
            df[c] = conv
    if df.empty:
        raise SweepError("The table is empty.")
    return df


def merge(base: pd.DataFrame, more: pd.DataFrame, keys, prefer: str = "new", base_name: str = "", more_name: str = ""):
    """Two result tables as one: the rows of both, the columns of either (missing ones empty), a
    `_source` column saying which table each row came from. Where both ran the same run (the same
    values in `keys` - the parameters and must-hold-across columns), prefer="new" keeps the second
    table's row, "old" the first's, "both" keeps both. Returns (table, rows added, rows replaced)."""
    a, b = base.copy(), more.copy()
    if "_source" not in a.columns:
        a["_source"] = base_name or "1"
    b["_source"] = more_name or "2"
    keys = [k for k in (keys or []) if k in a.columns and k in b.columns]
    replaced = 0
    if keys and prefer in ("new", "old"):
        ka = a[keys].astype(str).agg("\u241f".join, axis=1) if len(keys) > 1 else a[keys[0]].astype(str)
        kb = b[keys].astype(str).agg("\u241f".join, axis=1) if len(keys) > 1 else b[keys[0]].astype(str)
        if prefer == "new":
            dup = ka.isin(set(kb))
            replaced = int(dup.sum())
            a = a[~dup]
        else:
            dup = kb.isin(set(ka))
            replaced = int(dup.sum())
            b = b[~dup]
    out = pd.concat([a, b], ignore_index=True, sort=False)
    return out, int(len(out) - len(base)), replaced
