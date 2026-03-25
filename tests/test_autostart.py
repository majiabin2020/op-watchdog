# tests/test_autostart.py
import sys
from unittest.mock import patch, MagicMock
import pytest

# Only run on Windows
pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows only")

from utils.autostart import AutostartManager


@pytest.fixture
def mgr():
    return AutostartManager()


class TestIsEnabled:
    def test_returns_true_when_key_exists(self, mgr):
        mock_key = MagicMock()
        with patch("winreg.OpenKey", return_value=mock_key), \
             patch("winreg.QueryValueEx", return_value=("path", 1)):
            assert mgr.is_enabled() is True

    def test_returns_false_when_key_missing(self, mgr):
        with patch("winreg.OpenKey", side_effect=FileNotFoundError):
            assert mgr.is_enabled() is False


class TestEnable:
    def test_writes_registry_key(self, mgr):
        mock_key = MagicMock()
        with patch("winreg.OpenKey", return_value=mock_key), \
             patch("winreg.SetValueEx") as mock_set, \
             patch("sys.executable", "C:\\app.exe"):
            mgr.enable()
            mock_set.assert_called_once()
            args = mock_set.call_args[0]
            assert "LaomaClawWatchdog" in args


class TestDisable:
    def test_deletes_registry_key(self, mgr):
        mock_key = MagicMock()
        with patch("winreg.OpenKey", return_value=mock_key), \
             patch("winreg.DeleteValue") as mock_del:
            mgr.disable()
            mock_del.assert_called_once()

    def test_silent_when_key_not_found(self, mgr):
        mock_key = MagicMock()
        with patch("winreg.OpenKey", return_value=mock_key), \
             patch("winreg.DeleteValue", side_effect=FileNotFoundError):
            mgr.disable()  # Should not raise
