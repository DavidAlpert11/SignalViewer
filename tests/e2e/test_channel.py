"""CH (owner, 2026-11-26): a communication channel - separate TX and RX made one channel of requests and replies in one
click, its anomalies counted and shown over time, the counts compared with a similar file.

    python -m pytest tests/e2e/test_channel.py -q
"""
import os
import shutil

import pytest

pw = pytest.importorskip("playwright.sync_api")
from test_features import S, env, live_settings, open_files, pg  # noqa: E402,F401

DEMO = os.path.join(os.path.dirname(__file__), "..", "..", "examples", "serial_link")


def messages_page(pg):
    pg.keyboard.press("Control+k")
    pg.keyboard.type("Messages")
    pg.keyboard.press("Enter")
    pg.wait_for_selector(".page.messages, .side.messages")


def test_separate_tx_and_rx_become_one_channel_in_one_click(pg):
    shutil.copy(os.path.join(DEMO, "link_tx_rx.csv"), os.path.join(pg.env["data"], "link_tx_rx.csv"))
    open_files(pg, "link_tx_rx.csv")
    messages_page(pg)
    offer = pg.locator(".ch-offer")
    offer.wait_for(timeout=30000)
    assert "tx_byte" in offer.inner_text() and "rx_byte" in offer.inner_text()
    offer.locator(".ch-make").click()
    # kept in the session at once (one Undo), TX first; the stream opens as the pair
    pg.wait_for_function("(window.__sv.state().ws.messageStreams || []).some(m => m.carries === 'pair' && m.sources[0].endsWith('/tx_byte') && m.sources[1].endsWith('/rx_byte'))")
    pg.wait_for_selector(".msgp-current input[value=pair]:checked, .msgp-stream.open input[value=pair]:checked", timeout=30000)
    assert pg.locator(".ch-offer").count() == 0
    pg.keyboard.press("Control+z")
    pg.wait_for_function("!(window.__sv.state().ws.messageStreams || []).length")
