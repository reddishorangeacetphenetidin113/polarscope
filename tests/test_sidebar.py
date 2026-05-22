"""Sidebar tests: record/stop-record button state machine + auto-stop coupling."""
from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication

from ui.sidebar import Sidebar


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def sidebar(qapp):
    s = Sidebar()
    s.set_ports(["/dev/cu.usbserial-FAKE"])
    yield s
    s.deleteLater()


def test_record_disabled_until_scanning(sidebar):
    sidebar.set_state("disconnected")
    assert not sidebar._record_btn.isEnabled()
    sidebar.set_state("connected")
    assert not sidebar._record_btn.isEnabled()
    sidebar.set_state("scanning")
    assert sidebar._record_btn.isEnabled()


def test_swap_buttons_on_recording_flag(sidebar):
    sidebar.set_state("scanning")
    sidebar._recording = True
    sidebar._update_record_buttons()
    assert not sidebar._record_btn.isVisibleTo(sidebar)
    assert sidebar._stop_record_btn.isVisibleTo(sidebar)
    sidebar._recording = False
    sidebar._update_record_buttons()
    assert sidebar._record_btn.isVisibleTo(sidebar)
    assert not sidebar._stop_record_btn.isVisibleTo(sidebar)


def test_stop_recording_click_emits_signal(sidebar):
    sidebar.set_state("scanning")
    sidebar._recording = True
    sidebar._update_record_buttons()
    stops: list[None] = []
    sidebar.record_stopped.connect(lambda: stops.append(None))
    sidebar._on_stop_recording_clicked()
    assert len(stops) == 1
    assert not sidebar._recording


def test_disconnect_while_recording_auto_emits_stop(sidebar):
    sidebar.set_state("scanning")
    sidebar._recording = True
    sidebar._update_record_buttons()
    stops: list[None] = []
    sidebar.record_stopped.connect(lambda: stops.append(None))
    sidebar.set_state("disconnected")
    assert len(stops) == 1
    assert not sidebar._recording


def test_scan_stop_while_recording_auto_emits_stop(sidebar):
    sidebar.set_state("scanning")
    sidebar._recording = True
    sidebar._update_record_buttons()
    stops: list[None] = []
    sidebar.record_stopped.connect(lambda: stops.append(None))
    sidebar.set_state("connected (idle)")
    assert len(stops) == 1
    assert not sidebar._recording


def test_record_failed_reverts_state(sidebar):
    sidebar.set_state("scanning")
    sidebar._recording = True
    sidebar._update_record_buttons()
    stops: list[None] = []
    sidebar.record_stopped.connect(lambda: stops.append(None))
    sidebar.on_record_failed()
    assert not sidebar._recording
    # record_failed should NOT additionally emit record_stopped — the worker
    # never actually opened the file, there's nothing to close.
    assert len(stops) == 0


def test_stop_recording_no_op_when_not_recording(sidebar):
    sidebar.set_state("scanning")
    stops: list[None] = []
    sidebar.record_stopped.connect(lambda: stops.append(None))
    sidebar._on_stop_recording_clicked()
    assert len(stops) == 0


def test_is_recording_property(sidebar):
    assert not sidebar.is_recording
    sidebar.set_state("scanning")
    sidebar._recording = True
    assert sidebar.is_recording
