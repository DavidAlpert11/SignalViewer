"""MSG1 / MSG3: messages in a byte stream - the serial link demo from Help -> Examples opens the Link review; *Decode as
messages…* on a signal with a direction column (both ways) makes the tab with the reply latency; the definition kept.

    python -m pytest tests/e2e/test_messages.py -q
"""
import os
import shutil

import pytest

pw = pytest.importorskip("playwright.sync_api")
from test_features import S, env, open_files, pg, save_as, sig  # noqa: E402,F401
from test_report_doc import preview_has  # noqa: E402

DEMO = os.path.join(os.path.dirname(__file__), "..", "..", "examples", "serial_link")
SHOT = os.environ.get("SV_SHOTS")             # a folder: pictures of the screen for the owner (not needed by the test)


def shot(pg, name):
    if SHOT:
        os.makedirs(SHOT, exist_ok=True)
        pg.screenshot(path=os.path.join(SHOT, name))


def test_the_serial_link_example_opens_the_link_review(pg):
    """Owner, 2026-11-23: the example is built in front of the user - the raw bytes, then each step's button: the
    messages found (the Messages page on the link), their plots (the panel beside them), the link's report."""
    pg.locator(".topbar .menubar-btn", has_text="Help").click()
    pg.locator(".menu.ctx button", has_text="Examples").click()
    pg.locator(".menu.ctx.sub button", has_text="a serial link").click()
    pg.wait_for_selector(".demo-guide[data-demo=serialLink][data-step='1'] .demo-next", timeout=30000)
    assert not S(pg, "s.ws.messageStreams?.length") and S(pg, "s.panel") != "messages"          # only the raw bytes yet
    pg.locator(".demo-guide .demo-next").click()
    pg.wait_for_selector(".stage-panel .page.messages .msgp-current .msgp-edit", timeout=30000)   # Messages as a page
    pg.wait_for_selector(".page.messages .demo-guide[data-step='2'] .demo-next")                # the line follows
    pg.locator(".demo-guide .demo-next").click()
    pg.wait_for_function("window.__sv.state().ws.tabs.some(t => t.name.startsWith('Messages: tx_byte'))", timeout=30000)
    pg.wait_for_selector(".main .side.messages")                          # a new tab: the plots back, the panel beside them
    pg.locator(".demo-guide[data-step='3'] .demo-next").click()
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
    pg.wait_for_selector(".messages .msgp-stream.open .msgp-edit")
    shot(pg, "msg_dialog.png")
    # a direction column is there: "both" is guessed, with dir and TX
    assert pg.locator(".msgp-stream.open input[value=both]").is_checked()
    assert pg.locator(".msgp-stream.open .msg-dir").input_value().endswith("/dir")
    assert pg.locator(".msgp-stream.open .msg-txv option:checked").inner_text().startswith("TX")
    pg.locator(".msgp-stream.open .msg-go").click()
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


def test_any_column_says_the_direction_the_user_picks_tx_and_rx(pg, tmp_path):
    """MSG5 (owner, 2026-11-22): a numeric column with several values (a node address: 5, 9, 12) as the direction -
    the user picks TX and RX from its values (each with its count); the third node's bytes are in neither."""
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "backend", "tests"))
    from test_bytestream import _node_csv
    import pathlib
    _node_csv(pathlib.Path(pg.env["data"]) / "nodes.csv")
    open_files(pg, "nodes.csv")
    sig(pg, "byte").click(button="right")
    pg.locator(".menu.ctx button", has_text="Decode as messages").click()
    pg.wait_for_selector(".messages .msgp-stream.open .msgp-edit")
    box = pg.locator(".msgp-stream.open")
    box.locator("input[value=both]").check()
    node = S(pg, "s.runs.find(r => r.name.startsWith('nodes')).signals.find(x => x.name === 'node').id")
    box.locator(".msg-dir").select_option(node)
    pg.wait_for_function("document.querySelectorAll('.msgp-stream.open .msg-txv option').length === 3")
    assert [o.strip() for o in box.locator(".msg-txv option").all_inner_texts()][2].startswith("12")
    box.locator(".msg-txv").select_option("5")
    box.locator(".msg-rxv").select_option("9")
    box.locator(".msg-dirleft").wait_for()
    assert "60" in box.locator(".msg-dirleft").inner_text()
    shot(pg, "msg_direction_values.png")
    box.locator(".msg-go").click()
    pg.wait_for_function("window.__sv.state().ws.tabs.some(t => t.name.startsWith('Messages: byte'))", timeout=30000)
    ms = S(pg, "s.ws.messageStreams")
    assert ms[0]["dir"] == node and ms[0]["txValue"] == 5 and ms[0]["rxValue"] == 9
    assert S(pg, "s.ws.tabs.find(t => t.name.startsWith('Messages: byte')).plots[1].signals.length") == 2


def test_the_time_tells_the_header_from_the_footer_on_screen(pg):
    """MSG6 (owner, 2026-11-22): a recording that starts inside a message, with pauses between messages - step 2 shows
    A5 5A as the header (it comes right after the pauses) and 0D 0A as what ends a message, and says why."""
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "backend", "tests"))
    from test_msginspect import _burst_stream
    t, b = _burst_stream(0.01, 5)
    with open(os.path.join(pg.env["data"], "bursts.csv"), "w", encoding="utf-8") as f:
        f.write("time,byte\n" + "".join("%.6f,%d\n" % (x, y) for x, y in zip(t, b)))
    open_files(pg, "bursts.csv")
    sig(pg, "byte").click(button="right")
    pg.locator(".menu.ctx button", has_text="Decode as messages").click()
    box = pg.locator(".messages .msgp-stream.open")
    box.locator(".msg-bytime").wait_for(timeout=20000)
    box.locator(".msg-framing-line").wait_for()
    assert "header A55A" in box.locator(".msg-framing-line").inner_text()
    assert "footer 0D0A" in box.locator(".msg-framing-line").inner_text()
    chips = box.locator(".msg-pat").all_inner_texts()
    assert any(c.startswith("A5 5A") and "header" in c for c in chips), chips
    assert any(c.startswith("0D 0A") and "footer" in c for c in chips), chips
    assert "right after a pause" in box.locator(".msg-pat", has_text="A5 5A").first.get_attribute("title")
    shot(pg, "msg_by_time.png")


def example(pg, text):
    pg.locator(".topbar .menubar-btn", has_text="Help").click()
    pg.locator(".menu.ctx button", has_text="Examples").click()
    pg.locator(".menu.ctx.sub button", has_text=text).click()


def test_messages_to_signals_example_makes_two_recordings(pg):
    """MSG2: the serial link with its two structure files -> two recordings of their own, plotted."""
    example(pg, "messages to signals")
    pg.wait_for_selector(".demo-guide[data-demo=linkStructure] .demo-next", timeout=30000)
    assert not S(pg, "s.runs.some(r => r.name.endsWith(' - messages'))")       # nothing made before the steps
    for step in ("1", "2", "3"):                                              # open the link, its structure files, make
        pg.locator(f".demo-guide[data-step='{step}'] .demo-next").click()
    pg.wait_for_selector(".demo-guide[data-step=done]", timeout=60000)
    pg.wait_for_function("['tx_byte - messages', 'rx_byte - messages'].every(n => window.__sv.state().runs.some(r => r.name === n))", timeout=60000)
    sigs = S(pg, "s.runs.find(r => r.name === 'rx_byte - messages').signals.map(x => x.name)")
    assert "ATTITUDE.roll [deg]" in sigs and "ATTITUDE.alt [m]" in sigs and "STATUS.mode" in sigs
    pg.wait_for_function("window.__sv.state().ws.tabs.some(t => t.name === 'rx_byte - messages')", timeout=30000)
    pg.wait_for_timeout(1500)
    shot(pg, "msg2_link_recording.png")
    ms = S(pg, "s.ws.messageStreams")
    assert len(ms) == 1 and sorted(m["label"] for m in ms[0]["made"]) == ["RX", "TX"]


def test_add_a_stream_form(pg):
    """UX3 (owner, 2026-11-23: "defining a signal as messages is reached only by a right-click"): Messages -> Add a
    stream - the two signals of a link chosen as TX and RX in the panel itself; the page shows that stream's editor."""
    shutil.copy(os.path.join(DEMO, "link_tx_rx.csv"), os.path.join(pg.env["data"], "link_tx_rx.csv"))
    open_files(pg, "link_tx_rx.csv")
    pg.locator(".rail button[aria-label=Messages]").click()
    pg.wait_for_selector(".stage-panel .page.messages")                          # a page of its own
    pg.locator(".msgp-add").click()
    form = pg.locator(".msgp-addform")
    form.locator("[data-kind=pair]").click()
    assert form.locator("select").nth(0).input_value().endswith("/tx_byte")      # byte-like names guessed per side
    assert form.locator("select").nth(1).input_value().endswith("/rx_byte")
    form.locator(".msgp-addgo").click()
    pg.wait_for_selector(".msgp-current .msgp-edit")
    assert pg.locator(".msgp-current input[value=pair]").is_checked()
    assert pg.locator(".page-index .msgp-stream.chosen").count() == 1


def test_propose_a_binary_structure_rename_and_make(pg):
    shutil.copy(os.path.join(DEMO, "link_tx_rx.csv"), os.path.join(pg.env["data"], "link_tx_rx.csv"))
    open_files(pg, "link_tx_rx.csv")
    sig(pg, "rx_byte").click(button="right")
    pg.locator(".menu.ctx button", has_text="Decode as messages").click()
    pg.wait_for_selector(".messages .msgp-stream.open .msgp-edit")
    assert pg.locator(".msgp-stream.open input[value=rx]").is_checked()                  # named rx: guessed RX
    pg.locator(".msgp-stream.open .msg-propose").click()
    pg.wait_for_selector(".msgp-stream.open .msg-struct .msg-msg")
    assert pg.locator(".msgp-stream.open .msg-hdr").input_value() == "EB90"
    att = pg.locator(".msgp-stream.open .msg-msg", has=pg.locator(".msg-name[value=MSG_A0]"))
    att.locator(".msg-f-name").first.fill("roll")
    att.locator(".msg-f-conv").first.click()                                     # the first field's conversion
    att.locator(".msg-f-scale").first.fill("0.01")                               # x scale
    shot(pg, "msg2_propose_binary.png")
    pg.locator(".msgp-stream.open .msg-make").click()
    pg.wait_for_function("window.__sv.state().runs.some(r => r.name === 'rx_byte - messages')", timeout=30000)
    roll = S(pg, "s.runs.find(r => r.name === 'rx_byte - messages').signals.find(x => x.name === 'MSG_A0.roll')")
    assert roll is not None


def test_gps_nmea_example_and_uart_proposes_nmea(pg):
    example(pg, "raw NMEA")
    pg.wait_for_function("window.__sv.state().runs.some(r => r.name.endsWith('receiver.nmea'))", timeout=60000)
    pg.locator(".demo-guide[data-demo=gpsNmea] .demo-finish").click()          # its two steps: the track, the side plots
    sigs = S(pg, "s.runs.find(r => r.name.endsWith('receiver.nmea')).signals.map(x => x.name)")
    assert "GGA.lat [deg]" in sigs and "RMC.speed [kn]" in sigs
    # the track on a map at once, speed / satellites / altitude beside it
    pg.wait_for_function("window.__sv.state().ws.tabs.some(t => t.plots.some(p => (p.mode === 'geo' || p.mode === '3d') && (p.objects || []).length))", timeout=30000)
    pg.wait_for_function("window.__sv.state().ws.tabs.some(t => t.name.endsWith('receiver.nmea'))", timeout=30000)
    if SHOT:
        pg.evaluate("() => { const st = window.__sv.state(); const tb = st.ws.tabs.find(t => t.plots.some(p => p.mode === 'geo' || p.mode === '3d')); window.__sv.setState({ ws: { ...st.ws, activeTab: tb.id } }); }")
        pg.wait_for_timeout(3000)
        shot(pg, "msg2_gps_map.png")
    pg.wait_for_function("window.__sv.state().runs.some(r => r.name.endsWith('receiver_uart.csv'))", timeout=60000)
    sig(pg, "rx_byte").click(button="right")
    pg.locator(".menu.ctx button", has_text="Decode as messages").click()
    pg.wait_for_selector(".messages .msgp-stream.open .msgp-edit")
    pg.locator(".msgp-stream.open .msg-propose").click()
    pg.wait_for_selector(".msgp-stream.open .msg-struct .msg-msg")
    assert pg.locator(".msgp-stream.open .msg-kind").input_value() == "text"
    names = pg.locator(".msgp-stream.open .msg-name").evaluate_all("els => els.map(e => e.value)")
    assert {"GGA", "RMC", "PDEMO"} <= set(names)
    shot(pg, "msg2_propose_nmea.png")
    pg.locator(".msgp-stream.open .msg-make").click()
    pg.wait_for_function("window.__sv.state().runs.some(r => r.name === 'rx_byte - messages')", timeout=30000)
    assert S(pg, "s.runs.find(r => r.name === 'rx_byte - messages').signals.some(x => x.name === 'PDEMO.f1')")


def test_listen_to_a_udp_link_decoded_live(pg):
    """LINK1: Live -> Listen to a link: UDP with NMEA - the recording opens and grows live; Stop keeps the file."""
    import socket
    import time
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    pg.click(".live-more")
    pg.locator(".link-conn").fill(f"udp:127.0.0.1:{port}")
    pg.locator(".link-structure").select_option(label="NMEA 0183")      # MSG3: from the structure library
    pg.locator(".link-listen").click()
    pg.wait_for_selector(".link-stop")
    lines = open(os.path.join(os.path.dirname(__file__), "..", "..", "examples", "gps_nmea", "receiver.nmea"), "rb").read().splitlines(keepends=True)
    tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def send(a, b):
        for ln in lines[a:b]:
            tx.sendto(ln, ("127.0.0.1", port))
            time.sleep(0.002)
    send(0, 100)
    pg.wait_for_function("window.__sv.state().runs.some(r => r.name.endsWith('.svraw') && r.signals.some(x => x.name.startsWith('GGA.lat')))", timeout=30000)
    n0 = S(pg, "s.runs.find(r => r.name.endsWith('.svraw')).signals.find(x => x.name.startsWith('GGA.lat')).n")
    send(100, 400)                                              # more comes in: the plots' data grows (live)
    pg.wait_for_function(f"window.__sv.state().runs.find(r => r.name.endsWith('.svraw')).signals.find(x => x.name.startsWith('GGA.lat')).n > {n0}", timeout=30000)
    shot(pg, "link_live.png")
    # MSG3: the running link shows in the Messages panel too (started and stopped in Live)
    pg.keyboard.press("Escape")
    pg.mouse.click(5, 300)
    pg.locator(".rail button[aria-label='Messages']").click()
    pg.wait_for_selector(".msgp-running .msgp-link")
    shot(pg, "msg3_running.png")
    pg.click(".live-more")
    pg.locator(".link-stop").click()
    pg.wait_for_selector(".link-listen")
    path = S(pg, "s.runs.find(r => r.name.endsWith('.svraw')).path")
    assert os.path.isfile(path) and os.path.isfile(path[:-6] + ".svmsg.json")    # the recording and its structure stay


def test_messages_panel_is_the_one_home(pg):
    """MSG3: the Messages panel - the byte streams of the open files found with their types, a log's message types
    (a click plots them), the structure library; a structure saved to the library, a stream added to the report."""
    shutil.copy(os.path.join(DEMO, "link_tx_rx.csv"), os.path.join(pg.env["data"], "link_tx_rx.csv"))
    shutil.copy(os.path.join(DEMO, "..", "copter_flight.bin"), os.path.join(pg.env["data"], "copter_flight.bin"))
    open_files(pg, "link_tx_rx.csv", "copter_flight.bin")
    pg.locator(".rail button[aria-label='Messages']").click()
    pg.wait_for_selector(".msgp-stream[data-key$='/tx_byte'] .msgp-types .chip-s", timeout=30000)
    assert pg.locator(".msgp-stream[data-key$='/rx_byte']").count() == 1
    assert "AA 55" in pg.locator(".msgp-stream[data-key$='/tx_byte'] .msgp-dir").inner_text()
    assert pg.locator(".msgp-lib-list li", has_text="NMEA 0183").count() == 1
    # the flight log's message types: a click plots that message's fields in a new tab
    pg.wait_for_selector(".msgp-log tbody tr")
    pg.locator(".msgp-log summary", has_text="copter_flight").click() if not pg.locator(".msgp-log[open]").count() else None
    pg.locator(".msgp-log tbody tr", has=pg.locator("td", has_text="ATT")).first.click()
    pg.wait_for_function("window.__sv.state().ws.tabs.some(t => t.name === 'ATT' && t.plots[0].signals.length > 0)", timeout=30000)
    # a stream opened: proposed, saved to the library (listed), added to the report
    pg.locator(".msgp-stream[data-key$='/tx_byte'] .msgp-stream-head").click()
    ed = pg.locator(".msgp-stream.open")
    ed.locator(".msg-propose").click()
    ed.locator(".msg-struct .msg-msg").first.wait_for()
    ed.locator(".msg-save").click()
    pg.locator(".dialog.small input").first.fill("ground link TX")                 # its name in the library
    pg.keyboard.press("Enter")
    pg.wait_for_selector(".msgp-lib-list li:has-text('ground link TX')", timeout=15000)
    shot(pg, "msg3_panel.png")
    ed.locator(".msg-report").click()
    pg.wait_for_function("(window.__sv.state().ws.report?.doc?.text || '').includes('[[messages tx_byte]]')", timeout=15000)
    assert S(pg, "s.ws.messageStreams.length") == 1
    # the saved structure is offered when listening to a link
    pg.click(".live-more")
    pg.wait_for_function("[...document.querySelectorAll('.link-structure option')].some(o => o.textContent === 'NMEA 0183')", timeout=15000)
    opts = pg.locator(".link-structure option").evaluate_all("els => els.map(e => e.textContent)")
    assert "NMEA 0183" in opts and len(opts) >= 4


def test_guided_steps_from_raw_bytes_to_a_csv(pg):
    """MSG4: the four steps - the patterns found (the header first), the first messages byte by byte coloured by role,
    a click on a byte makes it a value (its first values shown at once), the recording made and saved as CSV."""
    shutil.copy(os.path.join(DEMO, "link_tx_rx.csv"), os.path.join(pg.env["data"], "link_tx_rx.csv"))
    open_files(pg, "link_tx_rx.csv")
    sig(pg, "rx_byte").click(button="right")
    pg.locator(".menu.ctx button", has_text="Decode as messages").click()
    ed = pg.locator(".msgp-stream.open")
    for n in (1, 2, 3, 4):
        ed.locator(".msg-step-%d h4" % n).wait_for()
    # step 2: proposed by itself - the header is the first pattern, the messages byte by byte
    ed.locator(".msg-step-2 .msg-pat.role-header", has_text="EB 90").first.wait_for(timeout=30000)
    ed.locator(".bv-frame .bv-b.role-header").first.wait_for()
    att = ed.locator(".bv-frame", has=pg.locator(".bv-meta b", has_text="MSG_A0")).first
    assert att.locator(".bv-b").nth(2).get_attribute("class").count("role-type") == 1
    assert att.locator(".bv-b").nth(3).get_attribute("class").count("role-length") == 1
    shot(pg, "msg4_steps.png")
    # step 2 -> 3: byte 12 is not a value any more, then a 16-bit signed MSB-first value starts there
    att.locator(".bv-b").nth(12).click()
    pg.locator(".menu.ctx button", has_text="Not a value").click()
    att.locator(".bv-b").nth(12).click()
    pg.locator(".menu.ctx button", has_text="A value starts here").click()
    pg.locator(".menu.ctx.sub button", has_text="16-bit signed, MSB first").click()
    table = ed.locator(".msg-values-t", has=pg.locator("caption", has_text="MSG_A0"))
    table.locator("th", has_text="value_12").wait_for(timeout=15000)
    assert table.locator("tbody tr").count() >= 1
    assert "×" in table.locator("caption").inner_text()                     # counted on the whole stream
    # step 4: the recording, then a CSV of it
    ed.locator(".msg-make").click()
    pg.wait_for_function("window.__sv.state().runs.some(r => r.name === 'rx_byte - messages' && r.signals.some(x => x.name === 'MSG_A0.value_12'))", timeout=30000)
    ed.locator(".msg-made").wait_for()
    ed.locator(".msg-savefile").click()
    save_as(pg, "rx_values.csv")
    path = os.path.join(pg.env["out"], "rx_values.csv")
    pg.wait_for_function("document.body.innerText.includes('rx_values.csv')", timeout=30000)
    head = open(path, encoding="utf-8").readline()
    assert "MSG_A0.value_12" in head


def test_messages_in_order_counted_picked_and_one_plotted(pg):
    """MSG7 (owner, 2026-11-22: "plot which messages passed in order, a histogram of them; choose one kind of message
    and get its variables"): step 4 lists every message with its count and share, the types not described too; one
    left out of the recording is still counted; Plot puts one message's variables in a tab, with the lane of the
    messages in order; the recording carries `message` (which message passed when, by name)."""
    shutil.copy(os.path.join(DEMO, "link_tx_rx.csv"), os.path.join(pg.env["data"], "link_tx_rx.csv"))
    open_files(pg, "link_tx_rx.csv")
    sig(pg, "rx_byte").click(button="right")
    pg.locator(".menu.ctx button", has_text="Decode as messages").click()
    ed = pg.locator(".msgp-stream.open")
    ed.locator(".msg-list-row").first.wait_for(timeout=30000)
    rows = ed.locator(".msg-list-row th").all_inner_texts()
    assert rows[0] == "MSG_A0" and len(rows) == 5, rows                   # the most first
    assert "%" in ed.locator(".msg-list-row .msg-list-n").first.inner_text()
    # MSG_81 left out of the recording
    ed.locator(".msg-list-row", has=pg.locator("th", has_text="MSG_81")).locator(".msg-list-in").uncheck()
    assert ed.locator(".msg-list-row", has=pg.locator("th", has_text="MSG_81")).locator(".msg-list-plot").is_disabled()
    ed.locator(".msg-list-row", has=pg.locator("th", has_text="MSG_A0")).locator(".msg-list-plot").click()
    pg.wait_for_function("window.__sv.state().ws.tabs.some(t => t.name.startsWith('MSG_A0 · '))", timeout=30000)
    tab = S(pg, "s.ws.tabs.find(t => t.name.startsWith('MSG_A0 · '))")
    run = S(pg, "s.runs.find(r => r.name === 'rx_byte - messages')")
    names = {x["id"]: x["name"] for x in run["signals"]}
    assert all(names[p["signals"][0]["sig"]].startswith("MSG_A0.") for p in tab["plots"])
    assert names[tab["sharedStates"][0]] == "message"
    assert not any(n.startswith("MSG_81.") for n in names.values())        # left out: no values
    seq = next(x for x in run["signals"] if x["name"] == "message")
    assert set(seq["labels"].values()) == {"MSG_81", "MSG_82", "MSG_90", "MSG_A0", "MSG_A1"}   # but in the order
    pg.wait_for_timeout(1200)
    shot(pg, "msg7_one_message.png")
    ed.locator(".msg-list").scroll_into_view_if_needed()
    shot(pg, "msg7_list.png")


def test_bytes_as_hex_numbers_ascii_a_text_field_and_a_formula(pg):
    """MSG8 (owner, 2026-11-22: "convert hex to double and ascii, sometimes both"; "a variable of several bytes with a
    conversion formula"): the byte view shows hex, decimal, ASCII or hex with the character under it; a byte's menu
    says what each choice reads there; text from a byte to the end of the values; a field's formula on its raw x."""
    import struct
    data = b"".join(b"\xAA\x55" + struct.pack("<H", 5000 + k) + struct.pack(">d", 1.5 * k) + (b"SN%03d\0" % (k % 3)) for k in range(400))
    with open(os.path.join(pg.env["data"], "frames.csv"), "w", encoding="utf-8") as f:
        f.write("time,byte\n" + "".join("%.4f,%d\n" % (i * 0.0005 + (i // 18) * 0.01, b) for i, b in enumerate(data)))
    open_files(pg, "frames.csv")
    sig(pg, "byte").click(button="right")
    pg.locator(".menu.ctx button", has_text="Decode as messages").click()
    ed = pg.locator(".msgp-stream.open")
    frame = ed.locator(".bv-frame").nth(1)
    frame.wait_for(timeout=30000)
    assert frame.locator(".bv-b").nth(0).inner_text() == "AA"
    ed.locator(".bv-show button", has_text="ASCII").first.click()
    assert frame.locator(".bv-b").nth(12).inner_text() == "S"
    ed.locator(".bv-show button", has_text="Dec").click()
    assert frame.locator(".bv-b").nth(0).inner_text() == "170"
    ed.locator(".bv-show button", has_text="Hex + ASCII").click()
    assert frame.locator(".bv-b").nth(13).inner_text().split() == ["4E", "N"]
    assert "double LSB first" in frame.locator(".bv-b").nth(4).get_attribute("title")
    shot(pg, "msg8_hex_ascii.png")
    # bytes 12..: text to the end of the values
    frame.locator(".bv-b").nth(12).click()
    pg.locator(".menu.ctx button", has_text="Text (ASCII) starts here").click()
    pg.locator(".menu.ctx.sub button", has_text="to the end of the values").first.click()
    table = ed.locator(".msg-values-t").first
    table.locator("td", has_text="SN001").wait_for(timeout=15000)       # the values follow a moment after the form
    # bytes 4..11: a double, MSB first - the menu shows its value before it is chosen
    frame.locator(".bv-b").nth(4).click()
    pg.locator(".menu.ctx button", has_text="A value starts here").click()
    item = pg.locator(".menu.ctx.sub button", has_text="double (64-bit), MSB first")
    assert "= 1.5" in item.inner_text()
    item.click()
    table.locator("th", has_text="value_4").wait_for(timeout=15000)
    # bytes 2..3: 16-bit LSB first through a formula
    frame.locator(".bv-b").nth(2).click()
    pg.locator(".menu.ctx button", has_text="A value starts here").click()
    pg.locator(".menu.ctx.sub button", has_text="16-bit, LSB first").first.click()
    table.locator("th", has_text="value_2").wait_for(timeout=15000)
    row = ed.locator(".msg-f", has=pg.locator("input.msg-f-name[value='value_2']"))
    row.locator(".msg-f-conv").click()
    row.locator(".msg-f-formula").fill("x*0.01 - 40")
    pg.wait_for_function("""() => { const t = document.querySelector('.msgp-stream.open .msg-values-t');
        return t && [...t.querySelectorAll('tbody tr')].some(r => r.innerText.includes('10.01')); }""", timeout=15000)
    shot(pg, "msg8_values.png")


def test_not_the_type_byte_makes_one_kind_of_message(pg):
    """MSG9 (owner, 2026-11-22: "make it clear and easy"): a type byte proposed where the user knows there is none -
    its menu says *Not the type byte*: one kind of message, the clicked message's values kept."""
    shutil.copy(os.path.join(DEMO, "link_tx_rx.csv"), os.path.join(pg.env["data"], "link_tx_rx.csv"))
    open_files(pg, "link_tx_rx.csv")
    sig(pg, "rx_byte").click(button="right")
    pg.locator(".menu.ctx button", has_text="Decode as messages").click()
    ed = pg.locator(".msgp-stream.open")
    att = ed.locator(".bv-frame", has=pg.locator(".bv-meta b", has_text="MSG_A0")).first
    att.wait_for(timeout=30000)
    assert "type byte at 2" in ed.locator(".msg-framing-line").inner_text()
    att.locator(".bv-b").nth(2).click()
    pg.locator(".menu.ctx button", has_text="Not the type byte").click()
    pg.wait_for_function("document.querySelector('.msgp-stream.open .msg-framing-line').innerText.includes('one kind of message')", timeout=15000)
    pg.wait_for_function("""() => { const c = [...document.querySelectorAll('.msgp-stream.open .msg-values-t caption')];
        return c.length === 1 && c[0].innerText.startsWith('MSG ·'); }""", timeout=15000)       # one kind: one table


def test_remove_one_field_a_message_and_a_stream(pg):
    """Owner, 2026-11-23: removing one variable took its whole message, and a stream once defined could not be taken
    away. A field's ✕ removes that field only (Undo in the notice); a message is removed from its own button, asked
    first; a stream's ⋯ forgets its definition (one Undo) or, added by hand, takes it off the list."""
    shutil.copy(os.path.join(DEMO, "link_tx_rx.csv"), os.path.join(pg.env["data"], "link_tx_rx.csv"))
    open_files(pg, "link_tx_rx.csv")
    sig(pg, "rx_byte").click(button="right")
    pg.locator(".menu.ctx button", has_text="Decode as messages").click()
    pg.locator(".msgp-stream.open .msg-propose").click()
    att = pg.locator(".msgp-stream.open .msg-msg", has=pg.locator(".msg-name[value=MSG_A0]"))
    att.wait_for()
    names = lambda: att.locator(".msg-f-name").evaluate_all("els => els.map(e => e.value)")  # noqa: E731
    before = names()
    assert len(before) >= 2
    att.locator(".msg-f-del").nth(1).click()
    assert names() == before[:1] + before[2:]                                   # one field gone, the message kept
    pg.locator(".toast", has_text="Removed").locator("button", has_text="Undo").click()
    pg.wait_for_function("n => document.querySelectorAll('.msgp-stream.open .msg-msg .msg-f-name').length >= n", arg=len(before))
    assert names() == before
    # the whole message: asked first
    n_msgs = pg.locator(".msgp-stream.open .msg-msg").count()
    att.locator(".msg-msg-del").click()
    pg.locator(".dialog .btn", has_text="Remove the message").click()
    pg.wait_for_function("n => document.querySelectorAll('.msgp-stream.open .msg-msg').length === n - 1", arg=n_msgs)
    # kept in the session, then forgotten from the stream's menu - one Undo brings it back
    pg.locator(".msgp-stream.open .msg-make").click()
    pg.wait_for_function("(window.__sv.state().ws.messageStreams || []).some(m => m.sources[0].endsWith('/rx_byte'))", timeout=30000)
    pg.locator(".msgp-stream[data-key$='/rx_byte'] .msgp-stream-more").click()
    pg.locator(".menu.ctx button", has_text="Forget the definition").click()
    pg.locator(".dialog .btn", has_text="Forget the definition").click()
    pg.wait_for_function("!(window.__sv.state().ws.messageStreams || []).some(m => m.sources[0].endsWith('/rx_byte'))")
    assert pg.locator(".msgp-stream[data-key$='/rx_byte']").count() == 1      # found by itself: still listed, folded
    assert pg.locator(".msgp-stream.open[data-key$='/rx_byte']").count() == 0
    pg.evaluate("() => window.__sv.state().undo()")
    pg.wait_for_function("(window.__sv.state().ws.messageStreams || []).some(m => m.sources[0].endsWith('/rx_byte'))")


def test_the_inspector_is_not_beside_a_page(pg):
    """UX5.1: the Inspector is the plots' properties - beside the Messages page (in the plots' place) it is hidden and
    its top-bar button is off; with the page beside the plots (⤡) it is back, as the user had it."""
    shutil.copy(os.path.join(DEMO, "link_tx_rx.csv"), os.path.join(pg.env["data"], "link_tx_rx.csv"))
    open_files(pg, "link_tx_rx.csv")
    pg.evaluate("window.__sv.setState({ inspectorOpen: true })")
    pg.wait_for_selector("aside.inspector")
    pg.locator(".rail button[aria-label='Messages']").click()
    pg.wait_for_selector(".page.messages")
    pg.wait_for_selector("aside.inspector", state="detached")
    assert pg.locator(".insp-toggle").is_disabled()
    pg.locator(".page-head .panel-fill").click()                             # beside the plots
    pg.wait_for_selector("aside.inspector")
    assert not pg.locator(".insp-toggle").is_disabled()
    assert S(pg, "s.inspectorOpen") is True


def test_a_page_stays_a_page_while_it_plays(pg):
    """Review 2026-11-24 (#15): playback moves the cursor every frame - that is not an action that needs the plots, so
    Messages opened while playing stays a page, and its ⤢ is not undone; a cursor moved by hand still brings them."""
    shutil.copy(os.path.join(DEMO, "link_tx_rx.csv"), os.path.join(pg.env["data"], "link_tx_rx.csv"))
    open_files(pg, "link_tx_rx.csv")
    pg.evaluate("window.__sv.setState({ playSpeed: 1, cursor: { ...window.__sv.state().cursor, on: true, t1: 0 } })")
    pg.evaluate("window.__sv.setState({ playing: true })")
    pg.wait_for_function("window.__sv.state().cursor.t1 > 0.2")
    pg.locator(".rail button[aria-label='Messages']").click()
    pg.wait_for_selector(".page.messages")
    t0 = S(pg, "s.cursor.t1")
    pg.wait_for_function(f"window.__sv.state().cursor.t1 > {t0} + 0.5")            # it played on ...
    assert pg.locator(".page.messages").count() == 1                              # ... and the page stayed
    pg.evaluate("window.__sv.setState({ playing: false })")
    pg.evaluate("window.__sv.setState({ cursor: { ...window.__sv.state().cursor, t1: 3 } })")   # moved by hand
    pg.wait_for_selector("aside.messages")
