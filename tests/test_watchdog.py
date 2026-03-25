# tests/test_watchdog.py
import threading
import time
from unittest.mock import MagicMock, patch, call
import pytest
from core.watchdog import WatchdogState, WatchdogThread


@pytest.fixture
def mock_gateway():
    gw = MagicMock()
    gw.is_alive.return_value = False
    gw.is_process_running.return_value = False
    return gw


@pytest.fixture
def watchdog(mock_gateway):
    wd = WatchdogThread(gateway=mock_gateway)
    yield wd
    wd.stop()


class TestInitialState:
    def test_starts_in_stopped_state(self, watchdog):
        assert watchdog.state == WatchdogState.STOPPED

    def test_restart_count_zero(self, watchdog):
        assert watchdog.restart_count == 0


class TestStateTransitions:
    def test_stop_from_running_transitions_to_stopped(self, watchdog):
        watchdog._state = WatchdogState.RUNNING
        watchdog.stop()
        assert watchdog.state == WatchdogState.STOPPED

    def test_on_status_callback_called_on_state_change(self, watchdog):
        cb = MagicMock()
        watchdog.on_status_change = cb
        watchdog._set_state(WatchdogState.STARTING)
        cb.assert_called_once_with(WatchdogState.STARTING)

    def test_on_log_callback_called_with_message(self, watchdog):
        cb = MagicMock()
        watchdog.on_log = cb
        watchdog._log("hello")
        cb.assert_called_once_with("hello")

    def test_restart_count_increments_on_successful_restart(self, watchdog):
        watchdog._state = WatchdogState.RUNNING
        watchdog._increment_restart_count()
        assert watchdog.restart_count == 1


class TestCleanupBeforeStart:
    def test_calls_stop_when_process_running(self, watchdog, mock_gateway):
        mock_gateway.is_process_running.return_value = True
        watchdog._cleanup_stale_process()
        mock_gateway.stop.assert_called_once()

    def test_calls_kill_when_stop_leaves_process(self, watchdog, mock_gateway):
        mock_gateway.is_process_running.side_effect = [True, True]
        watchdog._cleanup_stale_process()
        mock_gateway.kill_all.assert_called_once()

    def test_skips_stop_when_no_process(self, watchdog, mock_gateway):
        mock_gateway.is_process_running.return_value = False
        watchdog._cleanup_stale_process()
        mock_gateway.stop.assert_not_called()


class TestRunLoop:
    """Integration tests for the _run() state machine."""

    def test_already_alive_goes_directly_to_running(self, mock_gateway):
        """If gateway is already running, skip startup and enter RUNNING."""
        mock_gateway.is_alive.return_value = True
        wd = WatchdogThread(gateway=mock_gateway)
        states = []
        wd.on_status_change = states.append
        # Patch the monitor loop to exit immediately
        wd._stop_event.set()
        with patch("time.sleep"):
            wd._run()
        assert WatchdogState.STARTING in states
        assert WatchdogState.RUNNING in states

    def test_startup_failure_sets_stopped_after_max_retries(self, mock_gateway):
        """If gateway never starts, state returns to STOPPED after MAX_RETRY_COUNT."""
        mock_gateway.is_alive.return_value = False
        wd = WatchdogThread(gateway=mock_gateway)
        states = []
        wd.on_status_change = states.append
        with patch("time.sleep"), patch.object(wd, "_attempt_start", return_value=False):
            wd._run()
        assert states[-1] == WatchdogState.STOPPED

    def test_stop_event_during_startup_aborts(self, mock_gateway):
        """If stop() is called while starting, _attempt_start returns False."""
        mock_gateway.is_alive.return_value = False
        wd = WatchdogThread(gateway=mock_gateway)
        wd._stop_event.set()  # Set before _run starts
        with patch("time.sleep"), patch.object(wd, "_attempt_start", return_value=False):
            wd._run()
        assert wd.state == WatchdogState.STOPPED
