"""CH (owner, 2026-11-26): a communication channel - separate TX and RX made one channel of requests and replies in one
click, its anomalies counted and shown over time, the counts compared with a similar file.

    python -m pytest tests/e2e/test_channel.py -q
"""
import os
import shutil

import pytest

pw = pytest.importorskip("playwright.sync_api")
from test_features import S, env, live_settings, open_files, pg  # noqa: E402,F401

SHOT = os.environ.get("SV_SHOTS")             # a folder: pictures of the screen for the owner (not needed by the test)
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


def test_the_channel_block_counts_and_shows_the_anomalies(pg):
    shutil.copy(os.path.join(DEMO, "link_tx_rx.csv"), os.path.join(pg.env["data"], "link_tx_rx.csv"))
    open_files(pg, "link_tx_rx.csv")
    messages_page(pg)
    pg.locator(".ch-offer .ch-make").click()
    view = pg.locator(".ch-view[data-total]")
    view.wait_for(timeout=30000)
    # the patterns beyond the content: both framings, the command answered by its ACK, the handshake
    txt = view.inner_text()
    assert "AA 55" in txt and "EB 90" in txt and "0x10 → RX 0x90" in txt and "Handshake" in txt
    # every anomaly of the demo counted (svcore/channel.py, test_channel): one chip per kind
    chip = lambda k: int(pg.locator(f".ch-chip[data-kind={k}] b").inner_text().replace(",", ""))
    assert chip("unanswered") == 18 and chip("checksum") == 4 and chip("retry") == 1 and chip("reconnect") == 1
    assert int(view.get_attribute("data-total")) == sum(chip(k) for k in pg.locator(".ch-chip").evaluate_all("es => es.map(e => e.dataset.kind)"))
    # the strip: a lane per kind; a click on the reconnect's mark puts the cursor there (19.5 s)
    assert pg.locator(".ch-lane[data-kind]").count() == pg.locator(".ch-chip").count()
    pg.locator(".ch-lane[data-kind=reconnect] .ch-mark").first.click()
    pg.wait_for_function("Math.abs(window.__sv.state().cursor.t1 - 19.5) < 0.05")
    # a chip shows only its kind in the list
    pg.locator(".ch-chip[data-kind=retry]").click()
    pg.locator(".ch-list summary").click()
    assert pg.locator(".ch-table tbody tr").count() == 1
    # Plot the messages: the anomalies so far, one step each, beside the data
    total = int(view.get_attribute("data-total"))
    if SHOT:
        view.screenshot(path=os.path.join(SHOT, "channel.png"))
    pg.locator(".msg-go").click()
    pg.wait_for_function("window.__sv.state().ws.tabs.some(t => t.plots.some(p => p.signals.some(s => s.sig.endsWith('.anomalies'))))", timeout=30000)
    n = S(pg, "s.runs.find(r => r.format === 'derived').signals.find(x => x.name.endsWith('.anomalies')).samples")
    assert n == total + 2                                  # from 0 at the first message to the last one
