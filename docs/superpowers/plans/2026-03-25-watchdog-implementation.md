# 老马OpenClaw小龙虾看门狗 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Windows green-exe watchdog that automatically detects, starts, and restarts the OpenClaw gateway, with a system tray icon and a geek-style dark terminal UI.

**Architecture:** A tkinter main window (dark terminal style) backed by a background WatchdogThread that implements a four-state machine (STOPPED/STARTING/RUNNING/RESTARTING). The UI, tray, gateway manager, and state machine are all decoupled through callbacks so each can be tested and modified independently.

**Tech Stack:** Python 3.11+, tkinter (UI), pystray + Pillow (tray), psutil (process detection), winreg (autostart), PyInstaller (packaging)

---

## File Map

| File | Responsibility |
|------|---------------|
| `main.py` | Entry point — wires all components together and starts the app |
| `config.py` | All constants in one place (port, timeouts, retry count, intervals) |
| `core/gateway.py` | Detect gateway (process + port), start (PowerShell), stop, kill |
| `core/watchdog.py` | WatchdogState enum + WatchdogThread (state machine + monitor loop) |
| `utils/autostart.py` | Read/write Windows registry for startup entry |
| `utils/notifier.py` | Windows tray bubble notification wrapper |
| `utils/tray.py` | pystray tray icon + right-click menu |
| `ui/main_window.py` | tkinter main window — status bar, log area, buttons |
| `assets/icon.py` | Generate icon.ico programmatically (no external file needed) |
| `build.bat` | One-command PyInstaller build |
| `requirements.txt` | pystray, Pillow, psutil |
| `tests/test_gateway.py` | Unit tests for gateway detection and process management |
| `tests/test_watchdog.py` | Unit tests for state machine transitions |
| `tests/test_autostart.py` | Unit tests for registry read/write |

---

## Task 1: Project Setup

**Files:**
- Create: `requirements.txt`
- Create: `config.py`
- Create: `tests/__init__.py`
- Create: `core/__init__.py`
- Create: `utils/__init__.py`
- Create: `ui/__init__.py`

- [ ] **Step 1: Create directory structure**

```bash
cd /c/Users/tntwl/Desktop/op-watchdog
mkdir -p core utils ui tests assets
touch core/__init__.py utils/__init__.py ui/__init__.py tests/__init__.py
```

- [ ] **Step 2: Create requirements.txt**

```
pystray==0.19.5
Pillow==10.3.0
psutil==5.9.8
pyinstaller==6.6.0
pytest==8.2.0
```

- [ ] **Step 3: Install dependencies**

```bash
pip install -r requirements.txt
```

Expected: all packages install without error.

- [ ] **Step 4: Create config.py**

```python
# config.py
GATEWAY_PORT = 18790
MONITOR_INTERVAL = 300       # 监控检查间隔（秒）
STARTUP_TIMEOUT = 30         # 单次启动等待超时（秒）
MAX_RETRY_COUNT = 3          # 最大启动/重启尝试次数（含首次）
CHECK_INTERVAL = 2           # 启动/重启等待时的检测间隔（秒）
STOP_WAIT = 3                # 执行stop命令后等待时间（秒）
SOCKET_TIMEOUT = 2           # 端口连接超时（秒）
AUTOSTART_KEY = "LaomaClawWatchdog"
GATEWAY_PROCESS_NAME = "openclawgateway"
GATEWAY_START_CMD = "openclawgateway"
GATEWAY_STOP_CMD = "openclaw gateway stop"
APP_NAME = "老马OpenClaw小龙虾看门狗"
APP_VERSION = "1.0.0"
```

- [ ] **Step 5: Commit**

```bash
git init
git add .
git commit -m "chore: project scaffold and config"
```

---

## Task 2: Gateway Detection

**Files:**
- Create: `core/gateway.py` (detection methods only)
- Create: `tests/test_gateway.py`

- [ ] **Step 1: Write failing tests for detection**

```python
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
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd /c/Users/tntwl/Desktop/op-watchdog
pytest tests/test_gateway.py -v
```

Expected: `ModuleNotFoundError: No module named 'core.gateway'`

- [ ] **Step 3: Implement detection methods in core/gateway.py**

```python
# core/gateway.py
import socket
import psutil
from config import GATEWAY_PORT, SOCKET_TIMEOUT, GATEWAY_PROCESS_NAME


class GatewayManager:
    def is_process_running(self) -> bool:
        """Check if any openclawgateway process is running."""
        for proc in psutil.process_iter(["name"]):
            try:
                if GATEWAY_PROCESS_NAME.lower() in proc.info["name"].lower():
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return False

    def is_port_open(self) -> bool:
        """Check if gateway port 18790 is accepting connections."""
        try:
            with socket.create_connection(("127.0.0.1", GATEWAY_PORT), timeout=SOCKET_TIMEOUT):
                return True
        except (ConnectionRefusedError, socket.timeout, OSError):
            return False

    def is_alive(self) -> bool:
        """Both process running AND port open = truly alive."""
        return self.is_process_running() and self.is_port_open()
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
pytest tests/test_gateway.py -v
```

Expected: all 8 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add core/gateway.py tests/test_gateway.py
git commit -m "feat: gateway detection (process + port dual check)"
```

---

## Task 3: Gateway Start / Stop / Kill

**Files:**
- Modify: `core/gateway.py` (add start, stop, kill methods)
- Modify: `tests/test_gateway.py` (add operation tests)

- [ ] **Step 1: Write failing tests for start/stop/kill**

Append to `tests/test_gateway.py`:

```python
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
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_gateway.py::TestStop tests/test_gateway.py::TestKillAll tests/test_gateway.py::TestStart -v
```

Expected: `AttributeError: 'GatewayManager' object has no attribute 'stop'`

- [ ] **Step 3: Implement start/stop/kill in core/gateway.py**

Add to the `GatewayManager` class:

```python
import subprocess
import time
from config import GATEWAY_STOP_CMD, GATEWAY_START_CMD, STOP_WAIT

    def start(self) -> subprocess.Popen:
        """Launch openclawgateway in a visible PowerShell window.
        Returns the Popen handle so caller can manage it."""
        cmd = ["powershell", "-NoExit", "-Command", GATEWAY_START_CMD]
        return subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)

    def stop(self) -> None:
        """Run 'openclaw gateway stop' silently."""
        subprocess.run(
            ["powershell", "-Command", GATEWAY_STOP_CMD],
            creationflags=subprocess.CREATE_NO_WINDOW,
            timeout=15,
        )

    def kill_all(self) -> None:
        """Forcefully kill all openclawgateway processes via psutil."""
        for proc in psutil.process_iter(["name"]):
            try:
                if GATEWAY_PROCESS_NAME.lower() in proc.info["name"].lower():
                    proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
```

- [ ] **Step 4: Run all gateway tests**

```bash
pytest tests/test_gateway.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add core/gateway.py tests/test_gateway.py
git commit -m "feat: gateway start/stop/kill operations"
```

---

## Task 4: Watchdog State Machine

**Files:**
- Create: `core/watchdog.py`
- Create: `tests/test_watchdog.py`

- [ ] **Step 1: Write failing tests for state machine**

```python
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
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_watchdog.py -v
```

Expected: `ModuleNotFoundError: No module named 'core.watchdog'`

- [ ] **Step 3: Implement core/watchdog.py**

```python
# core/watchdog.py
import threading
import time
from enum import Enum
from typing import Callable, Optional

from config import (
    MONITOR_INTERVAL, STARTUP_TIMEOUT, MAX_RETRY_COUNT,
    CHECK_INTERVAL, STOP_WAIT
)
from core.gateway import GatewayManager


class WatchdogState(Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    RESTARTING = "restarting"


class WatchdogThread:
    def __init__(self, gateway: Optional[GatewayManager] = None):
        self._gateway = gateway or GatewayManager()
        self._state = WatchdogState.STOPPED
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self.restart_count = 0

        # Callbacks — set by UI layer
        self.on_status_change: Optional[Callable[[WatchdogState], None]] = None
        self.on_log: Optional[Callable[[str], None]] = None
        self.on_notify: Optional[Callable[[str, str], None]] = None  # (title, msg)
        self.on_restart_count: Optional[Callable[[int], None]] = None

    @property
    def state(self) -> WatchdogState:
        return self._state

    def _set_state(self, new_state: WatchdogState) -> None:
        self._state = new_state
        if self.on_status_change:
            self.on_status_change(new_state)

    def _log(self, msg: str) -> None:
        if self.on_log:
            self.on_log(msg)

    def _notify(self, title: str, msg: str) -> None:
        if self.on_notify:
            self.on_notify(title, msg)

    def _increment_restart_count(self) -> None:
        self.restart_count += 1
        if self.on_restart_count:
            self.on_restart_count(self.restart_count)

    def _cleanup_stale_process(self) -> None:
        """Stop and kill any lingering gateway process before starting fresh."""
        if self._gateway.is_process_running():
            self._log("→ 检测到残留进程，尝试停止...")
            self._gateway.stop()
            time.sleep(STOP_WAIT)
            if self._gateway.is_process_running():
                self._log("→ 残留进程未退出，强制终止...")
                self._gateway.kill_all()

    def _attempt_start(self) -> bool:
        """Try to start the gateway. Returns True on success."""
        self._cleanup_stale_process()
        self._log("⚡ 正在调用 PowerShell 启动网关...")
        self._gateway.start()
        # Wait up to STARTUP_TIMEOUT seconds
        elapsed = 0
        while elapsed < STARTUP_TIMEOUT:
            time.sleep(CHECK_INTERVAL)
            elapsed += CHECK_INTERVAL
            if self._gateway.is_alive():
                return True
        return False

    def start_watching(self) -> None:
        """Called when user clicks '开始看门'."""
        if self._state != WatchdogState.STOPPED:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Called when user clicks '关闭看门' or exits."""
        self._set_state(WatchdogState.STOPPED)
        self._stop_event.set()

    def _run(self) -> None:
        """Main watchdog loop."""
        self._set_state(WatchdogState.STARTING)

        # ── Phase 1: Initial startup ──────────────────────────────────
        if self._gateway.is_alive():
            self._log("● 网关已在运行，开始监控")
            self._set_state(WatchdogState.RUNNING)
        else:
            success = False
            for attempt in range(1, MAX_RETRY_COUNT + 1):
                self._log(f"⚡ 启动网关 (第 {attempt}/{MAX_RETRY_COUNT} 次)...")
                if self._attempt_start():
                    self._log("✓ 网关启动成功")
                    self._set_state(WatchdogState.RUNNING)
                    success = True
                    break
                self._log(f"✗ 第 {attempt} 次启动超时")

            if not success:
                self._log("✗ 网关启动失败，请手动检查 OpenClaw 安装")
                self._notify("❌ 启动失败", "网关启动失败，请手动检查OpenClaw")
                self._set_state(WatchdogState.STOPPED)
                return

        # ── Phase 2: Monitor loop ─────────────────────────────────────
        check_count = 0
        while not self._stop_event.is_set():
            # Sleep MONITOR_INTERVAL seconds, checking stop_event frequently
            for _ in range(MONITOR_INTERVAL):
                if self._stop_event.is_set():
                    return
                time.sleep(1)

            if self._stop_event.is_set():
                return

            check_count += 1
            self._log(f"→ 定时检查中... (第 {check_count} 次)")

            if self._gateway.is_alive():
                self._log("✓ 网关运行正常")
                continue

            # ── Gateway down: restart ─────────────────────────────────
            self._log("✗ 网关异常退出！准备重启...")
            self._notify("⚠️ 网关已停止", "OpenClaw网关异常退出，正在自动重启...")
            self._set_state(WatchdogState.RESTARTING)

            restarted = False
            for attempt in range(1, MAX_RETRY_COUNT + 1):
                self._log(f"⚡ 重启网关 (第 {attempt}/{MAX_RETRY_COUNT} 次)...")
                if self._attempt_start():
                    self._log("✓ 网关重启成功！已恢复正常运行")
                    self._notify("✅ 网关已恢复", "OpenClaw网关已恢复正常运行")
                    self._increment_restart_count()
                    self._set_state(WatchdogState.RUNNING)
                    restarted = True
                    break
                self._log(f"✗ 第 {attempt} 次重启超时")

            if not restarted:
                self._log("✗ 网关重启失败，请手动检查")
                self._notify("❌ 重启失败", "网关重启失败，请手动检查OpenClaw")
                self._set_state(WatchdogState.STOPPED)
                return
```

- [ ] **Step 4: Run watchdog tests**

```bash
pytest tests/test_watchdog.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add core/watchdog.py tests/test_watchdog.py
git commit -m "feat: watchdog state machine and monitor loop"
```

---

## Task 5: Autostart + Notifier

**Files:**
- Create: `utils/autostart.py`
- Create: `utils/notifier.py`
- Create: `tests/test_autostart.py`

- [ ] **Step 1: Write failing tests for autostart**

```python
# tests/test_autostart.py
import sys
from unittest.mock import patch, MagicMock, call
import pytest

# Only run on Windows; skip on other platforms for CI compatibility
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
            assert "LaomaCrawWatchdog" in args


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
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_autostart.py -v
```

Expected: `ModuleNotFoundError: No module named 'utils.autostart'`

- [ ] **Step 3: Implement utils/autostart.py**

```python
# utils/autostart.py
import sys
import winreg
from config import AUTOSTART_KEY

_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


class AutostartManager:
    def is_enabled(self) -> bool:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as key:
                winreg.QueryValueEx(key, AUTOSTART_KEY)
            return True
        except FileNotFoundError:
            return False

    def enable(self) -> None:
        exe_path = sys.executable
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE
        ) as key:
            winreg.SetValueEx(key, AUTOSTART_KEY, 0, winreg.REG_SZ, exe_path)

    def disable(self) -> None:
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE
            ) as key:
                winreg.DeleteValue(key, AUTOSTART_KEY)
        except FileNotFoundError:
            pass
```

- [ ] **Step 4: Run autostart tests**

```bash
pytest tests/test_autostart.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Create utils/notifier.py**

This module wraps pystray's notification — no unit tests needed as it's a thin wrapper around an external API.

```python
# utils/notifier.py
from typing import Optional


class Notifier:
    """Sends Windows system tray balloon notifications via pystray."""

    def __init__(self):
        self._icon = None  # Set by TrayManager after tray is ready

    def set_icon(self, icon) -> None:
        self._icon = icon

    def send(self, title: str, message: str) -> None:
        if self._icon:
            try:
                self._icon.notify(message, title)
            except Exception:
                pass  # Notifications are best-effort
```

- [ ] **Step 6: Commit**

```bash
git add utils/autostart.py utils/notifier.py tests/test_autostart.py
git commit -m "feat: autostart registry manager and notifier"
```

---

## Task 6: System Tray

**Files:**
- Create: `assets/icon.py`
- Create: `utils/tray.py`

- [ ] **Step 1: Create assets/icon.py — generate icon programmatically**

No .ico file required; we draw a simple icon with Pillow.

```python
# assets/icon.py
from PIL import Image, ImageDraw


def create_icon(size: int = 64) -> Image.Image:
    """Create a simple crayfish-style icon: dark background, green circle."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Dark background circle
    draw.ellipse([2, 2, size - 2, size - 2], fill=(13, 17, 23, 255))
    # Green dot (online indicator style)
    cx, cy = size // 2, size // 2
    r = size // 4
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(63, 185, 80, 255))
    return img
```

- [ ] **Step 2: Create utils/tray.py**

```python
# utils/tray.py
import threading
from typing import Callable, Optional

import pystray
from PIL import Image

from assets.icon import create_icon
from config import APP_NAME
from utils.autostart import AutostartManager
from utils.notifier import Notifier


class TrayManager:
    def __init__(
        self,
        on_show_window: Callable,
        on_exit: Callable,
        notifier: Notifier,
        autostart: AutostartManager,
    ):
        self._on_show_window = on_show_window
        self._on_exit = on_exit
        self._notifier = notifier
        self._autostart = autostart
        self._icon: Optional[pystray.Icon] = None

    def _build_menu(self) -> pystray.Menu:
        autostart_label = (
            "开机自动启动  [●开]"
            if self._autostart.is_enabled()
            else "开机自动启动  [●关]"
        )
        return pystray.Menu(
            pystray.MenuItem(APP_NAME, None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("显示主窗口", self._handle_show),
            pystray.MenuItem(autostart_label, self._handle_toggle_autostart),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("退出", self._handle_exit),
        )

    def _handle_show(self, icon, item) -> None:
        self._on_show_window()

    def _handle_toggle_autostart(self, icon, item) -> None:
        if self._autostart.is_enabled():
            self._autostart.disable()
        else:
            self._autostart.enable()
        # Rebuild menu to reflect new state
        icon.menu = self._build_menu()

    def _handle_exit(self, icon, item) -> None:
        icon.stop()
        self._on_exit()

    def start(self) -> None:
        """Start the tray icon in a background thread."""
        icon_image = create_icon()
        self._icon = pystray.Icon(
            APP_NAME,
            icon_image,
            APP_NAME,
            menu=self._build_menu(),
        )
        # Double-click shows window
        self._icon.default_action = self._handle_show
        self._notifier.set_icon(self._icon)

        thread = threading.Thread(target=self._icon.run, daemon=True)
        thread.start()

    def hide_to_tray(self) -> None:
        pass  # Icon is always visible once started

    def stop(self) -> None:
        if self._icon:
            self._icon.stop()
```

- [ ] **Step 3: Manual smoke test for tray icon**

```bash
python -c "
from utils.notifier import Notifier
from utils.autostart import AutostartManager
from utils.tray import TrayManager
import time

notifier = Notifier()
autostart = AutostartManager()
tray = TrayManager(
    on_show_window=lambda: print('show'),
    on_exit=lambda: print('exit'),
    notifier=notifier,
    autostart=autostart,
)
tray.start()
time.sleep(10)
"
```

Expected: tray icon appears in system tray for 10 seconds. Right-click shows menu.

- [ ] **Step 4: Commit**

```bash
git add assets/icon.py utils/tray.py
git commit -m "feat: system tray icon and menu"
```

---

## Task 7: Main Window UI

**Files:**
- Create: `ui/main_window.py`

The UI is pure tkinter. No unit tests; manual visual verification.

- [ ] **Step 1: Create ui/main_window.py**

```python
# ui/main_window.py
import threading
import tkinter as tk
from datetime import datetime
from typing import Callable, Optional

from config import APP_NAME, APP_VERSION, MONITOR_INTERVAL
from core.watchdog import WatchdogState


# ── Colour palette ────────────────────────────────────────────────────
BG = "#0d1117"
BG2 = "#161b22"
BORDER = "#21262d"
BORDER2 = "#30363d"
GREEN = "#3fb950"
RED = "#ff7b72"
YELLOW = "#e8b84b"
GREY = "#8b949e"
BLUE = "#58a6ff"
FONT_MONO = ("Courier New", 10)
FONT_MONO_SM = ("Courier New", 9)
FONT_TITLE = ("Courier New", 11, "bold")


class MainWindow:
    def __init__(
        self,
        on_start: Callable,
        on_stop: Callable,
        on_hide: Callable,
        on_exit: Callable,
    ):
        self._on_start = on_start
        self._on_stop = on_stop
        self._on_hide = on_hide
        self._on_exit = on_exit

        self._root = tk.Tk()
        self._state = WatchdogState.STOPPED
        self._restart_count = 0
        self._countdown = MONITOR_INTERVAL
        self._countdown_job = None

        self._build_ui()
        self._root.protocol("WM_DELETE_WINDOW", self._on_hide)  # ✕ → hide, not quit

    # ── Build UI ──────────────────────────────────────────────────────

    def _build_ui(self):
        root = self._root
        root.title(APP_NAME)
        root.configure(bg=BG)
        root.resizable(False, False)
        root.geometry("480x520")

        # ── Title bar ─────────────────────────────────────────────────
        title_frame = tk.Frame(root, bg=BG2, pady=8)
        title_frame.pack(fill=tk.X)

        tk.Label(title_frame, text="🦞", bg=BG2, fg=GREEN,
                 font=("", 14)).pack(side=tk.LEFT, padx=(12, 4))
        tk.Label(title_frame, text=APP_NAME, bg=BG2, fg=BLUE,
                 font=FONT_TITLE).pack(side=tk.LEFT)

        btn_frame = tk.Frame(title_frame, bg=BG2)
        btn_frame.pack(side=tk.RIGHT, padx=10)
        tk.Button(btn_frame, text="●", bg=BG2, fg="#febc2e", bd=0,
                  activebackground=BG2, cursor="hand2",
                  command=self._on_hide).pack(side=tk.LEFT, padx=2)
        tk.Button(btn_frame, text="●", bg=BG2, fg="#ff5f57", bd=0,
                  activebackground=BG2, cursor="hand2",
                  command=self._on_hide).pack(side=tk.LEFT)

        tk.Frame(root, bg=BORDER2, height=1).pack(fill=tk.X)

        # ── Status area ───────────────────────────────────────────────
        status_frame = tk.Frame(root, bg=BG, pady=12, padx=16)
        status_frame.pack(fill=tk.X)

        # Gateway status column
        gw_col = tk.Frame(status_frame, bg=BG)
        gw_col.pack(side=tk.LEFT)
        tk.Label(gw_col, text="网关状态", bg=BG, fg=GREY,
                 font=FONT_MONO_SM).pack(anchor=tk.W)
        status_row = tk.Frame(gw_col, bg=BG)
        status_row.pack(anchor=tk.W)
        self._status_dot = tk.Label(status_row, text="●", bg=BG, fg=RED,
                                    font=("Courier New", 12))
        self._status_dot.pack(side=tk.LEFT)
        self._status_label = tk.Label(status_row, text="离线", bg=BG, fg=RED,
                                      font=("Courier New", 12, "bold"))
        self._status_label.pack(side=tk.LEFT, padx=(4, 0))

        # Next check column
        check_col = tk.Frame(status_frame, bg=BG)
        check_col.pack(side=tk.RIGHT, padx=(0, 20))
        self._restart_val = tk.Label(check_col, text="0", bg=BG, fg=BLUE,
                                     font=("Courier New", 11, "bold"))
        self._restart_val.pack(anchor=tk.E)
        tk.Label(check_col, text="重启次数", bg=BG, fg=GREY,
                 font=FONT_MONO_SM).pack(anchor=tk.E)

        countdown_col = tk.Frame(status_frame, bg=BG)
        countdown_col.pack(side=tk.RIGHT, padx=(0, 24))
        self._countdown_val = tk.Label(countdown_col, text="--:--", bg=BG,
                                       fg=YELLOW, font=("Courier New", 11, "bold"))
        self._countdown_val.pack(anchor=tk.E)
        tk.Label(countdown_col, text="下次检查", bg=BG, fg=GREY,
                 font=FONT_MONO_SM).pack(anchor=tk.E)

        tk.Frame(root, bg=BORDER, height=1).pack(fill=tk.X)

        # ── Log area ──────────────────────────────────────────────────
        log_frame = tk.Frame(root, bg=BG)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=16, pady=10)

        self._log_text = tk.Text(
            log_frame, bg=BG, fg=GREEN, font=FONT_MONO_SM,
            state=tk.DISABLED, wrap=tk.WORD, bd=0,
            selectbackground="#264f78",
        )
        scrollbar = tk.Scrollbar(log_frame, command=self._log_text.yview,
                                 bg=BG2, troughcolor=BG)
        self._log_text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self._log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Configure text tags for colours
        self._log_text.tag_configure("green", foreground=GREEN)
        self._log_text.tag_configure("red", foreground=RED)
        self._log_text.tag_configure("yellow", foreground=YELLOW)
        self._log_text.tag_configure("grey", foreground=GREY)
        self._log_text.tag_configure("timestamp", foreground="#555555")

        tk.Frame(root, bg=BORDER, height=1).pack(fill=tk.X)

        # ── Buttons ───────────────────────────────────────────────────
        btn_area = tk.Frame(root, bg=BG, pady=12, padx=16)
        btn_area.pack(fill=tk.X)

        self._start_btn = tk.Button(
            btn_area, text="[ 开始看门 ]",
            bg=GREEN, fg=BG, font=FONT_MONO, bd=0,
            activebackground="#2ea043", cursor="hand2",
            command=self._handle_start,
        )
        self._start_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))

        self._stop_btn = tk.Button(
            btn_area, text="[ 关闭看门 ]",
            bg=BG, fg="#444c56", font=FONT_MONO, bd=0,
            relief=tk.SOLID, activebackground=BG2, cursor="hand2",
            command=self._handle_stop,
        )
        self._stop_btn.pack(side=tk.LEFT, fill=tk.X, expand=True)

        tk.Frame(root, bg=BORDER, height=1).pack(fill=tk.X)

        # ── Footer ────────────────────────────────────────────────────
        footer = tk.Frame(root, bg=BG2, pady=4)
        footer.pack(fill=tk.X)
        tk.Label(footer, text=f"v{APP_VERSION}", bg=BG2, fg="#444c56",
                 font=FONT_MONO_SM).pack(side=tk.LEFT, padx=10)
        self._footer_label = tk.Label(
            footer, text="等待启动", bg=BG2, fg="#444c56", font=FONT_MONO_SM
        )
        self._footer_label.pack(side=tk.RIGHT, padx=10)

    # ── Button handlers ───────────────────────────────────────────────

    def _handle_start(self):
        self._on_start()
        self.hide()

    def _handle_stop(self):
        self._on_stop()

    # ── Public API (called by watchdog callbacks) ──────────────────────

    def on_state_change(self, state: WatchdogState) -> None:
        """Thread-safe: schedule UI update on main thread."""
        self._root.after(0, self._apply_state, state)

    def _apply_state(self, state: WatchdogState) -> None:
        self._state = state
        if state == WatchdogState.RUNNING:
            self._status_dot.config(fg=GREEN)
            self._status_label.config(text="在线", fg=GREEN)
            self._footer_label.config(text="监控中 · 已缩小到托盘后持续运行")
            self._start_countdown()
        elif state == WatchdogState.STARTING:
            self._status_dot.config(fg=YELLOW)
            self._status_label.config(text="启动中", fg=YELLOW)
            self._stop_countdown()
        elif state == WatchdogState.RESTARTING:
            self._status_dot.config(fg=YELLOW)
            self._status_label.config(text="重启中", fg=YELLOW)
            self._stop_countdown()
        elif state == WatchdogState.STOPPED:
            self._status_dot.config(fg=RED)
            self._status_label.config(text="离线", fg=RED)
            self._footer_label.config(text="监控已停止")
            self._stop_countdown()

    def on_restart_count(self, count: int) -> None:
        self._root.after(0, self._restart_val.config, {"text": str(count)})

    def append_log(self, message: str) -> None:
        """Thread-safe log append."""
        self._root.after(0, self._do_append_log, message)

    def _do_append_log(self, message: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        tag = "grey"
        if "✓" in message or "成功" in message or "正常" in message:
            tag = "green"
        elif "✗" in message or "失败" in message or "异常" in message or "错误" in message:
            tag = "red"
        elif "⚡" in message or "正在" in message or "尝试" in message or "重启" in message:
            tag = "yellow"

        self._log_text.config(state=tk.NORMAL)
        self._log_text.insert(tk.END, f"[{ts}] ", "timestamp")
        self._log_text.insert(tk.END, message + "\n", tag)
        self._log_text.see(tk.END)
        self._log_text.config(state=tk.DISABLED)

    # ── Countdown timer ───────────────────────────────────────────────

    def _start_countdown(self) -> None:
        self._countdown = MONITOR_INTERVAL
        self._tick_countdown()

    def _stop_countdown(self) -> None:
        if self._countdown_job:
            self._root.after_cancel(self._countdown_job)
            self._countdown_job = None
        self._countdown_val.config(text="--:--")

    def _tick_countdown(self) -> None:
        if self._state != WatchdogState.RUNNING:
            return
        mins, secs = divmod(self._countdown, 60)
        self._countdown_val.config(text=f"{mins:02d}:{secs:02d}")
        if self._countdown > 0:
            self._countdown -= 1
            self._countdown_job = self._root.after(1000, self._tick_countdown)
        else:
            self._countdown = MONITOR_INTERVAL
            self._tick_countdown()

    # ── Window management ─────────────────────────────────────────────

    def show(self) -> None:
        self._root.deiconify()
        self._root.lift()
        self._root.focus_force()

    def hide(self) -> None:
        self._root.withdraw()

    def run(self) -> None:
        self._root.mainloop()
```

- [ ] **Step 2: Quick visual smoke test**

```bash
python -c "
from ui.main_window import MainWindow
w = MainWindow(
    on_start=lambda: print('start'),
    on_stop=lambda: print('stop'),
    on_hide=lambda: print('hide'),
    on_exit=lambda: print('exit'),
)
w.append_log('● 看门狗已启动，开始监控...')
w.append_log('✓ 网关启动成功，进程 PID: 9527')
w.append_log('✗ 网关异常退出！准备重启...')
w.append_log('⚡ 正在调用 PowerShell 启动网关...')
w.run()
"
```

Expected: dark terminal-style window appears with coloured log entries.

- [ ] **Step 3: Commit**

```bash
git add ui/main_window.py assets/icon.py
git commit -m "feat: main window UI with terminal-style log"
```

---

## Task 8: Wire Everything Together (main.py)

**Files:**
- Create: `main.py`

- [ ] **Step 1: Create main.py**

```python
# main.py
from core.gateway import GatewayManager
from core.watchdog import WatchdogThread, WatchdogState
from ui.main_window import MainWindow
from utils.autostart import AutostartManager
from utils.notifier import Notifier
from utils.tray import TrayManager


def main():
    # ── Instantiate all components ────────────────────────────────────
    gateway = GatewayManager()
    watchdog = WatchdogThread(gateway=gateway)
    notifier = Notifier()
    autostart = AutostartManager()

    window = MainWindow(
        on_start=watchdog.start_watching,
        on_stop=watchdog.stop,
        on_hide=lambda: window.hide(),
        on_exit=_exit,
    )

    tray = TrayManager(
        on_show_window=window.show,
        on_exit=_exit,
        notifier=notifier,
        autostart=autostart,
    )

    # ── Wire watchdog callbacks to UI ─────────────────────────────────
    def on_status_change(state: WatchdogState):
        window.on_state_change(state)

    def on_log(msg: str):
        window.append_log(msg)

    def on_notify(title: str, msg: str):
        notifier.send(title, msg)

    def on_restart_count_change():
        window.on_restart_count(watchdog.restart_count)

    watchdog.on_status_change = on_status_change
    watchdog.on_log = on_log
    watchdog.on_notify = on_notify

    def on_restart_count(_count: int):
        window.on_restart_count(watchdog.restart_count)

    watchdog.on_restart_count = on_restart_count

    def _exit():
        watchdog.stop()
        tray.stop()
        import sys; sys.exit(0)

    # ── Start ─────────────────────────────────────────────────────────
    tray.start()
    window.run()  # Blocks until window is destroyed


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the full application**

```bash
python main.py
```

Expected: dark terminal window appears. Click "开始看门" to test the full flow.

- [ ] **Step 3: Commit**

```bash
git add main.py
git commit -m "feat: wire all components in main.py"
```

---

## Task 9: Build Executable

**Files:**
- Create: `build.bat`

- [ ] **Step 1: Create build.bat**

The build script first generates a proper `icon.ico` file from `assets/icon.py`, then runs PyInstaller with `--icon` so the exe has the lobster icon.

```bat
@echo off
echo Generating icon...
python -c "from assets.icon import create_icon; img = create_icon(256); img.save('assets/icon.ico', format='ICO', sizes=[(256,256),(64,64),(32,32),(16,16)])"

echo Building 老马OpenClaw小龙虾看门狗...
pyinstaller ^
  --onefile ^
  --noconsole ^
  --icon=assets/icon.ico ^
  --name="老马OpenClaw小龙虾看门狗" ^
  main.py
echo Done! Check dist\ folder.
pause
```

- [ ] **Step 2: Run the build**

```bash
build.bat
```

Expected: `dist\老马OpenClaw小龙虾看门狗.exe` is created.

- [ ] **Step 3: Test the built exe on a clean environment**

Double-click `dist\老马OpenClaw小龙虾看门狗.exe`. Verify:
- Window opens without errors
- "开始看门" triggers gateway start flow
- Tray icon appears after clicking "开始看门"
- Right-click tray menu shows all options

- [ ] **Step 4: Final commit**

```bash
git add build.bat
git commit -m "chore: add PyInstaller build script"
```

---

## Task 10: Run All Tests

- [ ] **Step 1: Run full test suite**

```bash
pytest tests/ -v
```

Expected: all tests PASS, no failures.

- [ ] **Step 2: Final summary commit**

```bash
git add .
git commit -m "chore: finalize v1.0.0"
```
