# tests/test_gateway.py
import socket
from unittest.mock import patch, MagicMock
import psutil
import pytest
from core.gateway import GatewayManager

@pytest.fixture
def gw():
    return GatewayManager()

class TestIsProcessRunning:
    def test_returns_true_when_process_exists(self, gw):
        mock_proc = MagicMock()
        mock_proc.info = {"name": "openclawgateway.exe"}
        with patch("psutil.process_iter", return_value=[mock_proc]):
            assert gw.is_process_running() is True

    def test_returns_false_when_no_process(self, gw):
        with patch("psutil.process_iter", return_value=[]):
            assert gw.is_process_running() is False

    def test_case_insensitive_match(self, gw):
        mock_proc = MagicMock()
        mock_proc.info = {"name": "OpenClawGateway.EXE"}
        with patch("psutil.process_iter", return_value=[mock_proc]):
            assert gw.is_process_running() is True

class TestIsPortOpen:
    def test_returns_true_when_port_connectable(self, gw):
        with patch("socket.create_connection") as mock_conn:
            mock_conn.return_value.__enter__ = MagicMock(return_value=None)
            mock_conn.return_value.__exit__ = MagicMock(return_value=False)
            assert gw.is_port_open() is True

    def test_returns_false_when_port_refused(self, gw):
        with patch("socket.create_connection", side_effect=ConnectionRefusedError):
            assert gw.is_port_open() is False

    def test_returns_false_on_timeout(self, gw):
        with patch("socket.create_connection", side_effect=socket.timeout):
            assert gw.is_port_open() is False

class TestIsAlive:
    def test_alive_when_both_pass(self, gw):
        with patch.object(gw, "is_process_running", return_value=True), \
             patch.object(gw, "is_port_open", return_value=True):
            assert gw.is_alive() is True

    def test_not_alive_when_process_missing(self, gw):
        with patch.object(gw, "is_process_running", return_value=False), \
             patch.object(gw, "is_port_open", return_value=True):
            assert gw.is_alive() is False

    def test_not_alive_when_port_closed(self, gw):
        with patch.object(gw, "is_process_running", return_value=True), \
             patch.object(gw, "is_port_open", return_value=False):
            assert gw.is_alive() is False

class TestStop:
    def test_stop_runs_correct_command(self, gw):
        with patch("subprocess.run") as mock_run:
            gw.stop()
            mock_run.assert_called_once()
            call_args = mock_run.call_args
            # command contains "openclaw gateway stop"
            cmd = " ".join(call_args[0][0])
            assert "openclaw" in cmd and "stop" in cmd

class TestKillAll:
    def test_kills_matching_processes(self, gw):
        mock_proc = MagicMock()
        mock_proc.info = {"name": "openclawgateway.exe"}
        mock_proc.kill = MagicMock()
        with patch("psutil.process_iter", return_value=[mock_proc]):
            gw.kill_all()
            mock_proc.kill.assert_called_once()

    def test_skips_non_matching_processes(self, gw):
        mock_proc = MagicMock()
        mock_proc.info = {"name": "chrome.exe"}
        mock_proc.kill = MagicMock()
        with patch("psutil.process_iter", return_value=[mock_proc]):
            gw.kill_all()
            mock_proc.kill.assert_not_called()

class TestStart:
    def test_start_launches_powershell(self, gw):
        with patch("subprocess.Popen") as mock_popen:
            gw.start()
            mock_popen.assert_called_once()
            call_args = mock_popen.call_args
            cmd = " ".join(call_args[0][0])
            assert "powershell" in cmd.lower()
            assert "openclawgateway" in cmd
