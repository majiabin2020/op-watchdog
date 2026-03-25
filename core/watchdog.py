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
