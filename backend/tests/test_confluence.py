"""CP4 (owner, 2026-11-22: "a good way to throw an interactive plot from the app straight to Confluence, the easiest
way"): Send to Confluence - the page attached and its macro added through Confluence's REST API, against a stand-in
(fake_confluence.py). The token never goes back to the page; a page's link of any form; sent again: a new version of
the attachment, the page left as it is; the errors say what to do."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from fake_confluence import TOKEN, Fake  # noqa: E402

client = TestClient(app)


@pytest.fixture()
def conf(monkeypatch, tmp_path):
    monkeypatch.delenv("SV_OFFLINE", raising=False)
    f = Fake()
    yield f
    f.close()
    client.post("/api/confluence", json={"url": "", "user": "", "token": ""})


@pytest.fixture()
def run(tmp_path):
    p = tmp_path / "bench.csv"
    p.write_text("time,speed\n" + "".join("%g,%g\n" % (i * 0.1, i % 7) for i in range(200)), encoding="utf-8")
    r = client.post("/api/files/open", json={"paths": [str(p)]}).json()["opened"][0]
    yield r
    client.delete(f"/api/runs/{r['id']}")


def _plot(run):
    return {"name": "", "plots": [{"mode": "time", "title": "Speed", "signals": [{"id": f"{run['id']}/speed", "label": "speed",
            "color": "#e33", "width": 1.5, "scale": 1, "offset": 0, "state": False, "tOffset": 0}]}]}


def test_send_to_confluence_attaches_and_adds_the_macro_once(conf, run):
    # not set up: said, with where to set it
    r = client.post("/api/export/confluence", json={"page": conf.url + "/pages/viewpage.action?pageId=4711", "tabs": [_plot(run)]})
    assert r.status_code == 400 and "Settings" in r.json()["detail"]
    s = client.post("/api/confluence", json={"url": conf.url + "/display/ENG/Bench+run+7", "token": TOKEN}).json()
    assert s == {"url": conf.url, "user": "", "hasToken": True, "recent": []}          # the server's address, no token back
    assert TOKEN not in client.get("/api/confluence").text
    assert client.post("/api/confluence/test").json() == {"user": "Dana Tester"}
    # sent, by the page's /display/ link: the attachment, then the HTML macro at the page's end
    body = {"page": conf.url + "/display/ENG/Bench+run+7", "title": "Speed", "tabs": [_plot(run)]}
    out = client.post("/api/export/confluence", json=body).json()
    assert out["page"] == "Bench run 7" and out["added"] and not out["updated"] and out["name"] == "Speed.html"
    assert out["url"] == conf.url + "/display/ENG/Bench+run+7"
    a = conf.attachments["Speed.html"]
    assert b'id="sv-data"' in a["data"] and a["data"].startswith(b"<!doctype html>")
    assert conf.page["version"] == 4 and conf.page["body"].startswith("<p>The bench run.</p>")
    assert '<ac:structured-macro ac:name="html"' in conf.page["body"] and 'data-name="Speed.html"' in conf.page["body"]
    # sent again (by its pageId link): a new version of the attachment, the page as it was
    again = client.post("/api/export/confluence", json={**body, "page": conf.url + "/pages/viewpage.action?pageId=4711"}).json()
    assert again["updated"] and not again["added"] and a["versions"] == 2 and conf.page["version"] == 4
    # the user macro's way, another plot: its markup in the storage format
    out = client.post("/api/export/confluence", json={**body, "title": "Speed 2", "macro": "user",
                                                       "page": conf.url + "/spaces/ENG/pages/4711/Bench+run+7"}).json()
    assert out["added"] and '<ac:structured-macro ac:name="signalviewer"' in conf.page["body"]
    assert '<ac:parameter ac:name="file">Speed 2.html</ac:parameter>' in conf.page["body"]
    assert [x["title"] for x in client.get("/api/confluence").json()["recent"]][:1] == ["Bench run 7"]


def test_confluence_errors_say_what_to_do(conf, run):
    client.post("/api/confluence", json={"url": conf.url, "token": "wrong"})
    r = client.post("/api/confluence/test")
    assert r.status_code == 400 and "refused the token" in r.json()["detail"]
    client.post("/api/confluence", json={"token": TOKEN})
    r = client.post("/api/export/confluence", json={"page": conf.url + "/pages/viewpage.action?pageId=99", "tabs": [_plot(run)]})
    assert r.status_code == 400 and "no such page" in r.json()["detail"]
    r = client.post("/api/export/confluence", json={"page": "https://example.com/some/thing", "tabs": [_plot(run)]})
    assert r.status_code == 400 and "not a link to a Confluence page" in r.json()["detail"]
    assert client.post("/api/confluence", json={"url": "confluence.example.com"}).status_code == 400
    client.post("/api/confluence", json={"url": "http://127.0.0.1:9/confluence"})
    r = client.post("/api/confluence/test")
    assert r.status_code == 400 and "could not be reached" in r.json()["detail"]


def test_sv_offline_sends_nothing(monkeypatch, conf, run):
    client.post("/api/confluence", json={"url": conf.url, "token": TOKEN})
    monkeypatch.setenv("SV_OFFLINE", "1")
    r = client.post("/api/confluence/test")
    assert r.status_code == 400 and "SV_OFFLINE" in r.json()["detail"] and not conf.calls
