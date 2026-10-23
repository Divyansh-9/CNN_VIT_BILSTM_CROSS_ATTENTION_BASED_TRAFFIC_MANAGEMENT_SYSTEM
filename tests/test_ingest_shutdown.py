"""D12: the ingest stops cleanly on Ctrl+C, SIGTERM or Ctrl+Break.

Before D12, `python -m server.mqtt_ingest` waited on an untimed
`Event().wait()`, so Ctrl+C ended it with a `KeyboardInterrupt` traceback and no
disconnect from the broker. These tests need no broker; `test_mqtt_live.py`
stops a real ingest process.
"""

from __future__ import annotations

import signal
import threading

import pytest

pytest.importorskip("paho.mqtt")

from server.mqtt_ingest import serve_until_stopped, stop_on_signals  # noqa: E402


class FakeIngest:
    def __init__(self):
        self.stored, self.refused, self.failed = 3, [("t", "r")], []
        self.stopped = 0

    def stop(self):
        self.stopped += 1


class InterruptedEvent(threading.Event):
    """Raises KeyboardInterrupt on its first wait, as Ctrl+C does."""

    def wait(self, timeout=None):
        raise KeyboardInterrupt


def test_ctrl_c_disconnects_and_returns_a_summary_instead_of_a_traceback():
    ingest = FakeIngest()
    summary = serve_until_stopped(ingest, InterruptedEvent(), poll_s=0.01)
    assert ingest.stopped == 1
    assert summary == "stopped; 3 stored, 1 refused, 0 failed"


def test_a_stop_request_disconnects():
    ingest, stop = FakeIngest(), threading.Event()
    threading.Timer(0.05, stop.set).start()
    serve_until_stopped(ingest, stop, poll_s=0.01)
    assert ingest.stopped == 1


def test_the_wait_polls_so_ctrl_c_can_interrupt_it_on_windows():
    seen = []

    class Recording(threading.Event):
        def wait(self, timeout=None):
            seen.append(timeout)
            return True

    serve_until_stopped(FakeIngest(), Recording(), poll_s=0.25)
    assert seen == [0.25]               # never an untimed wait


def test_sigterm_and_sigbreak_set_the_stop_event():
    names = [n for n in ("SIGTERM", "SIGBREAK") if hasattr(signal, n)]
    saved = {n: signal.getsignal(getattr(signal, n)) for n in names}
    try:
        stop = threading.Event()
        stop_on_signals(stop)
        for name in names:
            stop.clear()
            signal.getsignal(getattr(signal, name))(getattr(signal, name), None)
            assert stop.is_set(), name
    finally:
        for name, handler in saved.items():
            signal.signal(getattr(signal, name), handler)
