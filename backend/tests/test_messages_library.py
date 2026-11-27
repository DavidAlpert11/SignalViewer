"""MSG3: the structure library (NMEA built in, the structures folder, the readers folder's ICD layouts) and the
byte streams of the open files listed for the Messages panel."""
import json
import os

import pytest
from fastapi.testclient import TestClient

from app import prefs, userreaders
from app.main import app
from app.store import store

EX = os.path.join(os.path.dirname(__file__), "..", "..", "examples")
ICD = {"name": "Bench ICD", "extensions": [".tlm"], "byte_order": "little",
       "header": {"size": 4, "sync": "0xA55A", "id": {"offset": 2, "type": "u8"}, "length": {"offset": 3, "type": "u8"}},
       "packets": [{"id": 1, "name": "NAV", "fields": [{"name": "alt", "offset": 0, "type": "i16", "scale": 0.1, "unit": "m"}]}]}


@pytest.fixture
def lib(tmp_path, monkeypatch):
    monkeypatch.setattr(prefs, "APP_DIR", str(tmp_path))
    readers = tmp_path / "readers"
    readers.mkdir()
    (readers / "bench.icd.json").write_text(json.dumps(ICD), encoding="utf-8")
    monkeypatch.setattr(userreaders, "folder", lambda: str(readers))
    return tmp_path


def test_library_lists_nmea_the_folder_and_icd_layouts_and_saves(lib):
    c = TestClient(app)
    r = c.get("/api/messages/library").json()
    assert r["folder"] == str(lib / "structures")
    src = {(i["source"], i["name"]) for i in r["items"]}
    assert ("builtin", "NMEA 0183") in src and ("readers", "Bench ICD") in src
    icd = next(i for i in r["items"] if i["source"] == "readers")
    st = c.post("/api/messages/library/get", json={"key": icd["key"]}).json()["structure"]
    assert st["header"] == "A55A" and st["messages"][0]["fields"][0]["offset"] == 4      # an ICD read as a structure
    assert c.post("/api/messages/library/get", json={"key": "builtin:nmea"}).json()["structure"]["kind"] == "text"
    # save a structure into the folder: listed next time; the same name again asks first
    mine = json.load(open(os.path.join(EX, "serial_link", "link_tx.svmsg.json"), encoding="utf-8"))
    p = c.post("/api/messages/library/save", json={"structure": mine, "name": "ground tx"}).json()["path"]
    assert p.endswith("ground_tx.svmsg.json") and os.path.isfile(p)
    assert c.post("/api/messages/library/save", json={"structure": mine, "name": "ground tx"}).status_code == 409
    assert c.post("/api/messages/library/save", json={"structure": mine, "name": "ground tx", "overwrite": True}).status_code == 200
    items = c.get("/api/messages/library").json()["items"]
    assert any(i["source"] == "folder" and i["path"] == p and i["messages"] == len(mine["messages"]) for i in items)
    # a broken file is listed with what is wrong
    (lib / "structures" / "bad.svmsg.json").write_text("{", encoding="utf-8")
    bad = next(i for i in c.get("/api/messages/library").json()["items"] if i.get("file") == "bad.svmsg.json")
    assert "error" in bad
    assert c.post("/api/messages/library/get", json={"key": "/nowhere.svmsg.json"}).status_code == 404
    assert c.post("/api/messages/library/save", json={"structure": {"kind": "x"}}).status_code == 400


def test_streams_lists_the_byte_streams_with_their_types():
    c = TestClient(app)
    lr = store.open_file(os.path.join(EX, "serial_link", "link_tx_rx.csv"))
    rows = [s for s in c.post("/api/messages/streams", json={"streams": []}).json()["streams"] if s["rid"] == lr.id]
    keys = {s["key"] for s in rows}
    assert {f"{lr.id}/tx_byte", f"{lr.id}/rx_byte"} <= keys
    tx = next(s for s in rows if s["key"] == f"{lr.id}/tx_byte")
    assert tx["header"] == "AA 55" and tx["count"] > 100 and tx["types"] and tx["types"][0]["rate"] > 0
    # defined as a TX / RX pair: both directions under the one definition's key
    pair = {"id": "m1", "sources": [f"{lr.id}/tx_byte", f"{lr.id}/rx_byte"], "carries": "pair"}
    rows = [s for s in c.post("/api/messages/streams", json={"streams": [pair]}).json()["streams"] if s["rid"] == lr.id]
    mine = [s for s in rows if s["key"] == ",".join(pair["sources"])]
    assert sorted(s["name"].split()[-1] for s in mine) == ["RX", "TX"]


def test_streams_split_by_a_direction_column_share_one_key():
    """Both ways in one signal with a dir column (TX = 0): both directions belong to the byte signal's card."""
    c = TestClient(app)
    lr = store.open_file(os.path.join(EX, "serial_link", "link_mixed.csv"))
    rows = [s for s in c.post("/api/messages/streams", json={"streams": [], "runs": [lr.id]}).json()["streams"]]
    assert len(rows) == 2 and {s["key"] for s in rows} == {f"{lr.id}/byte"}


def test_channel_route_both_ways_and_by_a_direction_column():
    """CH2: /api/messages/channel - the separate TX and RX signals, and the same link in one signal split by its
    direction column, give the same anomalies."""
    c = TestClient(app)
    a = store.open_file(os.path.join(EX, "serial_link", "link_tx_rx.csv"))
    pair = c.post("/api/messages/channel", json={"sides": [{"label": "TX", "sources": [f"{a.id}/tx_byte"]},
                                                             {"label": "RX", "sources": [f"{a.id}/rx_byte"]}]}).json()
    assert pair["counts"]["unanswered"] == 18 and pair["counts"]["reconnect"] == 1 and pair["pairs"]
    assert len(pair["events"]["t"]) == pair["total"] == sum(pair["counts"].values())
    b = store.open_file(os.path.join(EX, "serial_link", "link_mixed.csv"))
    d = c.post("/api/messages/direction-values", json={"id": f"{b.id}/dir"}).json()["values"]
    code = {x["label"]: x["v"] for x in d}
    mixed = c.post("/api/messages/channel", json={"sides": [
        {"label": "TX", "sources": [f"{b.id}/byte", f"{b.id}/dir"], "params": {"dir": code["TX"]}},
        {"label": "RX", "sources": [f"{b.id}/byte", f"{b.id}/dir"], "params": {"dir": code["RX"]}}]}).json()
    assert mixed["counts"] == pair["counts"]
    assert c.post("/api/messages/channel", json={"sides": [{"label": "TX", "sources": ["nope/x"]}]}).status_code == 404


def _split_link(tmp_path, shift=0.0):
    """The serial link's TX and RX written to two files with names that say nothing - two loggers (the second's clock
    `shift` s off)."""
    import csv
    rows = list(csv.reader(open(os.path.join(EX, "serial_link", "link_tx_rx.csv"))))[1:]
    a, b = tmp_path / "logger_a.csv", tmp_path / "logger_b.csv"
    a.write_bytes(("time,port1\n" + "".join("%s,%s\n" % (r[0], r[1]) for r in rows if r[1])).encode())
    b.write_bytes(("time,port2\n" + "".join("%.6f,%s\n" % (float(r[0]) + shift, r[2]) for r in rows if r[2])).encode())
    return store.open_file(str(a)), store.open_file(str(b))


def test_streams_answering_each_other_are_offered_as_one_channel_across_files(tmp_path):
    """CH7 / CH8: each stream's anomalies in the list; two files whose bytes answer each other (no telling names):
    one channel offered, TX the side that asks - and as one definition, the same anomalies as the link in one file."""
    c = TestClient(app)
    a, b = _split_link(tmp_path)
    r = c.post("/api/messages/streams", json={"streams": [], "runs": [a.id, b.id]}).json()
    assert {"tx": f"{a.id}/port1", "rx": f"{b.id}/port2", "why": "replies"} in r["links"]
    row = next(x for x in r["streams"] if x["key"] == f"{a.id}/port1")
    assert row["anomalies"]["counts"]["checksum"] == 2 and row["anomalies"]["total"] == sum(row["anomalies"]["counts"].values())
    pair = {"id": "m", "sources": [f"{a.id}/port1", f"{b.id}/port2"], "carries": "pair"}
    r = c.post("/api/messages/streams", json={"streams": [pair], "runs": [a.id, b.id]}).json()
    mine = [x for x in r["streams"] if x["key"] == f"{a.id}/port1,{b.id}/port2"]
    assert len(mine) == 2 and not r["links"]
    assert next(x for x in mine if x["ids"] == [f"{a.id}/port1"])["anomalies"]["counts"]["unanswered"] == 18


def test_link_by_names_only_when_clear():
    """CH1 (the rule moved to the server with CH8): one TX-like and one RX-like name in a file - not across files by
    names alone, not when ambiguous."""
    from app.routes.messages import _links
    empty = {"messages": {"t": []}}
    s = lambda i: {"rid": i.split("/")[0], "ids": [i], "r": empty}
    assert _links([s("a/tx_byte"), s("a/rx_byte")]) == [{"tx": "a/tx_byte", "rx": "a/rx_byte", "why": "names"}]
    assert _links([s("a/uplink"), s("a/downlink"), s("a/sensor_byte")]) == [{"tx": "a/uplink", "rx": "a/downlink", "why": "names"}]
    assert _links([s("a/tx_byte"), s("b/rx_byte")]) == []
    assert _links([s("a/tx1"), s("a/tx2"), s("a/rx")]) == []


def test_two_loggers_with_two_clocks_are_offered_with_the_shift(tmp_path):
    """CH9: the second logger's clock 7 s ahead - nothing overlaps in answers; the echoed ids still pair them, the offer
    says the shift, and the channel says it too."""
    c = TestClient(app)
    a, b = _split_link(tmp_path, shift=7.0)
    r = c.post("/api/messages/streams", json={"streams": [], "runs": [a.id, b.id]}).json()
    link = next(x for x in r["links"] if x["tx"] == f"{a.id}/port1")
    assert link["rx"] == f"{b.id}/port2" and link["why"] == "clock" and link["shift"] == pytest.approx(7.0, abs=0.01)
    ch = c.post("/api/messages/channel", json={"sides": [{"label": "TX", "sources": [f"{a.id}/port1"]},
                                                           {"label": "RX", "sources": [f"{b.id}/port2"]}]}).json()
    assert ch["clock"]["shift"] == pytest.approx(link["shift"], abs=1e-6)
