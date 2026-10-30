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


