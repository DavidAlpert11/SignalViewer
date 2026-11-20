"""MSG1: messages in a byte stream - the serial link demo from Help -> Examples opens the Link review; *Decode as
messages…* on a signal with a direction column (both ways) makes the tab with the reply latency; the definition kept.

    python -m pytest tests/e2e/test_messages.py -q
"""
import os
import shutil

import pytest

pw = pytest.importorskip("playwright.sync_api")
from test_features import S, env, open_files, pg, sig  # noqa: E402,F401
from test_report_doc import preview_has  # noqa: E402

DEMO = os.path.join(os.path.dirname(__file__), "..", "..", "examples", "serial_link")
SHOT = os.environ.get("SV_SHOTS")             # a folder: pictures of the screen for the owner (not needed by the test)


def shot(pg, name):
    if SHOT:
        os.makedirs(SHOT, exist_ok=True)
        pg.screenshot(path=os.path.join(SHOT, name))


def test_the_serial_link_example_opens_the_link_review(pg):
    pg.locator(".topbar .menubar-btn", has_text="Help").click()
    pg.locator(".menu.ctx button", has_text="Examples").click()
    pg.locator(".menu.ctx.sub button", has_text="a serial link").click()
    pg.wait_for_selector(".rd .rd-text", timeout=30000)
    pg.wait_for_function("(window.__sv.state().ws.report?.doc?.text || '').includes('[[messages]]')", timeout=30000)
    # the packet's make-up, requests and replies, the handshake and its reconnect - in the preview
    preview_has(pg, "fixed AA 55", "fixed EB 90", "requests and replies", "The handshake", "a reconnect", "Unanswered")
    shot(pg, "msg_report.png")
    if SHOT:                                                         # further down: the link's part and its plots
        pg.frame_locator(".rd-preview iframe, .rd iframe").first.locator("text=requests and replies").first.scroll_into_view_if_needed()
        pg.wait_for_timeout(800)
        shot(pg, "msg_report_link.png")


def test_decode_as_messages_both_ways_with_a_direction_column(pg):
    shutil.copy(os.path.join(DEMO, "link_mixed.csv"), os.path.join(pg.env["data"], "link_mixed.csv"))
    open_files(pg, "link_mixed.csv")
    sig(pg, "byte").click(button="right")
    pg.locator(".menu.ctx button", has_text="Decode as messages").click()
    pg.wait_for_selector(".msgdlg")
    shot(pg, "msg_dialog.png")
    # a direction column is there: "both" is guessed, with dir and TX
    assert pg.locator(".msgdlg input[value=both]").is_checked()
    assert pg.locator(".msgdlg .msg-dir").input_value().endswith("/dir")
    assert pg.locator(".msgdlg .msg-txv option:checked").inner_text() == "TX"
    pg.locator(".msgdlg .msg-go").click()
    pg.wait_for_function("window.__sv.state().ws.tabs.some(t => t.name.startsWith('Messages: byte'))", timeout=30000)
    pg.wait_for_timeout(1500)
    shot(pg, "msg_tab.png")
    n = S(pg, "s.ws.tabs.find(t => t.name.startsWith('Messages: byte')).plots.length")
    assert n == 6                                                    # bytes, type, length, interval, ok, latency
    # TX and RX: two lines in each quantity's plot; the latency of the answered requests
    assert S(pg, "s.ws.tabs.find(t => t.name.startsWith('Messages: byte')).plots[1].signals.length") == 2
    assert S(pg, "s.runs.find(r => r.format === 'derived').signals.some(x => x.params?.what === 'latency' && x.samples === 284)")
    ms = S(pg, "s.ws.messageStreams")
    assert len(ms) == 1 and ms[0]["carries"] == "both"               # the definition kept in the session
