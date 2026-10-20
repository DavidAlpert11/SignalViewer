"""ROS 2 and Foxglove recordings (.mcap) - T27.

Read with the `mcap` / `mcap-ros2-support` packages (MIT, Foxglove; pure Python, no ROS needed).
Every numeric field of every topic becomes a signal named "<topic>.<field path>"
("imu/accel.vector.x"), on that topic's own time: the recording time (log_time) in seconds from
the first message in the file. A ROS time ({sec, nanosec}, e.g. header.stamp) becomes one number in
seconds; text fields become state signals with their texts as labels; booleans 0 / 1.

Not read (and said so in the load report): images, point clouds, maps and other bulk topics (by
message type, before decoding), byte blobs, arrays longer than MAX_ARRAY, and encodings other than
ROS 2 (cdr) and JSON. The file is read in order, so a recording cut off by a crash keeps every
message before the cut (report "cutOff")."""
import json
import math
import os
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

from svcore.csv_loader import _progress
from svcore.models import Run, Signal
from svcore.extras import missing

MAX_ARRAY = 16                    # longer numeric arrays (ranges, pixels...) are not signals
# bulk data, not time series: never decoded (decoding images alone would take most of the time)
SKIP_TYPES = ("Image", "CompressedImage", "PointCloud", "PointCloud2", "LaserScan", "OccupancyGrid",
              "CameraInfo", "Mesh", "MarkerArray", "SceneUpdate", "RawImage", "CompressedVideo", "Grid",
              "TFMessage", "FrameTransforms", "Log")
SKIP_FIELDS = {"frame_id", "child_frame_id"}


class McapError(Exception):
    pass


def _type_leaf(schema_name: str) -> str:
    """'sensor_msgs/msg/Image' / 'foxglove.CompressedImage' -> 'Image' / 'CompressedImage'."""
    return schema_name.replace(".", "/").split("/")[-1]


class _Topic:
    """The rows of one topic, column by column (a field first seen later gets NaN before it)."""
    __slots__ = ("times", "cols", "texts", "n", "too_long")

    def __init__(self):
        self.times: List[int] = []
        self.cols: Dict[str, List[float]] = {}
        self.texts: Dict[str, Dict[str, int]] = {}        # field -> {text: code}
        self.n = 0
        self.too_long: Dict[str, int] = {}

    def add(self, log_time: int, values: Dict[str, Any]):
        for k, v in values.items():
            col = self.cols.get(k)
            if col is None:
                col = self.cols[k] = [math.nan] * self.n
            if isinstance(v, str):
                codes = self.texts.setdefault(k, {})
                v = codes.setdefault(v, len(codes))
            col.append(float(v))
        self.n += 1
        for k, col in self.cols.items():
            if len(col) < self.n:                          # absent in this message
                col.append(math.nan)
        self.times.append(log_time)


def _flatten(obj: Any, prefix: str, out: Dict[str, Any], too_long: Dict[str, int], depth: int = 0):
    if depth > 12:
        return
    if isinstance(obj, bool):
        out[prefix] = 1.0 if obj else 0.0
    elif isinstance(obj, (int, float)):
        out[prefix] = obj
    elif isinstance(obj, str):
        out[prefix] = obj
    elif isinstance(obj, (bytes, bytearray, memoryview)):
        too_long[prefix] = len(obj)
    elif isinstance(obj, dict):                        # JSON messages
        if set(obj) == {"sec", "nsec"} or set(obj) == {"sec", "nanosec"}:
            frac = obj["nanosec"] if "nanosec" in obj else obj["nsec"]
            out[prefix] = obj["sec"] + frac * 1e-9
            return
        for k, v in obj.items():
            if k not in SKIP_FIELDS:
                _flatten(v, f"{prefix}.{k}" if prefix else str(k), out, too_long, depth + 1)
    elif isinstance(obj, (list, tuple, np.ndarray)):
        if len(obj) > MAX_ARRAY:
            too_long[prefix] = len(obj)
            return
        for i, v in enumerate(obj):
            _flatten(v, f"{prefix}[{i}]", out, too_long, depth + 1)
    else:
        slots = getattr(obj, "__slots__", None)
        if not slots:
            return
        if tuple(slots) in (("sec", "nanosec"), ("sec", "nsec")):   # a ROS time / duration: seconds
            out[prefix] = getattr(obj, "sec") + getattr(obj, slots[1]) * 1e-9
            return
        for k in slots:
            if k not in SKIP_FIELDS:
                _flatten(getattr(obj, k), f"{prefix}.{k}" if prefix else k, out, too_long, depth + 1)


def load_mcap(path: str, display_name: str) -> Tuple[Optional[Run], Dict[str, Any]]:
    try:
        from mcap.records import Channel, Message, Schema
        from mcap.stream_reader import StreamReader
        from mcap_ros2.decoder import DecoderFactory
    except ImportError:
        raise McapError(missing("Reading ROS 2 recordings (.mcap)", "ros")) from None
    ros2 = DecoderFactory()
    decoders: Dict[int, Optional[Callable[[bytes], Any]]] = {}     # channel id -> decode (None: skip)
    skipped: Dict[str, str] = {}
    topics: Dict[str, _Topic] = {}
    size = max(1, os.path.getsize(path))
    cut = False
    count = 0
    with open(path, "rb") as f:
        schemas: Dict[int, Any] = {}
        channels: Dict[int, Any] = {}
        try:
            # record by record, in file order (the library's message iterator first reads and sorts
            # ALL messages, so a damaged end would lose everything); each topic is sorted later
            for rec in StreamReader(f, validate_crcs=False).records:
                if isinstance(rec, Schema):
                    schemas[rec.id] = rec
                    continue
                if isinstance(rec, Channel):
                    channels[rec.id] = rec
                    continue
                if not isinstance(rec, Message):
                    continue
                message = rec
                channel = channels.get(message.channel_id)
                if channel is None:
                    continue
                schema = schemas.get(channel.schema_id)
                dec = decoders.get(channel.id, ...)
                if dec is ...:
                    dec = decoders[channel.id] = _decoder_for(schema, channel, ros2, skipped)
                if dec is None:
                    continue
                try:
                    obj = dec(message.data)
                except Exception:                  # one damaged message: skip it, keep the topic
                    skipped.setdefault(channel.topic, "some messages could not be decoded")
                    continue
                vals: Dict[str, Any] = {}
                tp = topics.get(channel.topic)
                if tp is None:
                    tp = topics[channel.topic] = _Topic()
                _flatten(obj, "", vals, tp.too_long)
                tp.add(message.log_time, vals)
                count += 1
                if count % 20000 == 0:
                    _progress(f.tell() / size, "read")
        except Exception as e:
            if e.__class__.__name__ == "LoadCancelled":
                raise
            if not count:
                raise McapError("This is not an MCAP recording, or it is damaged.") from None
            cut = True                              # damaged / cut off: keep what was read
    return _make_run(path, display_name, topics, skipped, count, cut)


def _decoder_for(schema, channel, ros2, skipped: Dict[str, str]) -> Optional[Callable[[bytes], Any]]:
    name = schema.name if schema else ""
    if name and _type_leaf(name) in SKIP_TYPES:
        skipped[channel.topic] = f"{name} (not a time series)"
        return None
    enc = channel.message_encoding
    if enc == "cdr" and schema is not None and schema.encoding == "ros2msg":
        try:
            return ros2.decoder_for(enc, schema)
        except Exception as e:
            skipped[channel.topic] = f"its message definition could not be read ({e})"
            return None
    if enc == "json":
        return lambda data: json.loads(bytes(data).decode("utf-8"))
    skipped[channel.topic] = f"encoding '{enc}' is not read yet"
    return None


def _make_run(path: str, display_name: str, topics: Dict[str, _Topic], skipped: Dict[str, str],
              count: int, cut: bool) -> Tuple[Optional[Run], Dict[str, Any]]:
    report: Dict[str, Any] = {"messages": count, "topics": len(topics)}
    if cut:
        report["cutOff"] = True
    if not topics:
        report["skipped"] = [f"{t}: {why}" for t, why in sorted(skipped.items())]
        return None, report
    t0 = min(tp.times[0] for tp in topics.values())
    sigs: Dict[str, Signal] = {}
    for topic, tp in sorted(topics.items()):
        t = (np.asarray(tp.times, dtype=np.int64) - t0) * 1e-9
        order = np.argsort(t, kind="stable") if np.any(np.diff(t) < 0) else None
        if order is not None:
            t = t[order]
        base = topic.strip("/") or topic
        for field, col in tp.cols.items():
            y = np.asarray(col, dtype=np.float64)
            if order is not None:
                y = y[order]
            name = f"{base}.{field}" if field else base
            codes = tp.texts.get(field)
            labels = {v: k for k, v in codes.items()} if codes else None
            sigs[name] = Signal(name=name, data=y, time=t, labels=labels)
        for field, n in tp.too_long.items():
            skipped.setdefault(f"{topic}.{field}", f"{n} values per message (bulk data)")
    if not sigs:
        report["skipped"] = [f"{t}: {why}" for t, why in sorted(skipped.items())]
        return None, report
    longest = max(sigs.values(), key=lambda s: len(s.time))     # type: ignore[arg-type]
    run = Run(file_path=path, csv_display_name=display_name, time=longest.time)   # type: ignore[arg-type]
    run.signals = dict(sorted(sigs.items()))
    run.compute_metadata()
    times = [s.time for s in run.signals.values() if s.time is not None and len(s.time)]
    run.start_time = float(min(t[0] for t in times))
    run.end_time = float(max(t[-1] for t in times))
    run.sample_count = int(max(len(t) for t in times))
    run.import_settings = {"format": "mcap"}
    if skipped:
        report["skipped"] = [f"{t}: {why}" for t, why in sorted(skipped.items())]
    return run, report
