# core/watchdog.py
import threading
import time
from enum import Enum
from typing import Callable, Optional

from config import (
    MONITOR_INTERVAL, STARTUP_TIMEOUT, MAX_RETRY_COUNT,
    CHECK_INTERVAL,
)
from core.gateway import GatewayManager


class WatchdogState(Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    RESTARTING = "restarting"


class StartAttemptResult(Enum):
    SUCCESS = "success"
    STOPPED = "stopped"
    EARLY_EXIT = "early_exit"
    TIMEOUT = "timeout"


class WatchdogThread:
    def __init__(self, gateway: Optional[GatewayManager] = None):
        self._gateway = gateway or GatewayManager()
        self._state = WatchdogState.STOPPED
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._current_proc = None  # Track current gateway Popen handle
        self.restart_count = 0

        # Callbacks — set by UI layer
        self.on_status_change: Optional[Callable[[WatchdogState], None]] = None
        self.on_log: Optional[Callable[[str], None]] = None
        self.on_notify: Optional[Callable[[str, str], None]] = None  # (title, msg)
        self.on_restart_count: Optional[Callable[[int], None]] = None
        self.on_gateway_presence: Optional[Callable[[bool], None]] = None

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

    def _set_gateway_presence(self, online: bool) -> None:
        if self.on_gateway_presence:
            self.on_gateway_presence(online)

    def _increment_restart_count(self) -> None:
        self.restart_count += 1
        if self.on_restart_count:
            self.on_restart_count(self.restart_count)

    def _reset_restart_count(self) -> None:
        self.restart_count = 0
        if self.on_restart_count:
            self.on_restart_count(self.restart_count)

    def _cleanup_stale_process(self, *, log_cleanup: bool = True) -> None:
        """Close previous console window and kill any lingering gateway process."""
        if self._current_proc is not None:
            try:
                self._current_proc.terminate()
            except Exception:
                pass
            self._current_proc = None
        if self._gateway.is_process_running():
            if log_cleanup:
                self._log("→ 检测到 OpenClaw 残留进程，正在清理...")
            self._gateway.kill_all()
            time.sleep(3)  # 等待 OS 释放端口 18789

    def _attempt_start(self) -> StartAttemptResult:
        """Try to start the gateway and report the outcome."""
        if self._stop_event.is_set():
            return StartAttemptResult.STOPPED
        self._cleanup_stale_process()
        if self._stop_event.is_set():
            return StartAttemptResult.STOPPED

        self._log(f"→ 当前启动方式：{self._gateway.get_launch_mode()}")
        self._log("⚡ 正在调用命令启动网关...")
        self._current_proc = self._gateway.start()
        # Wait up to STARTUP_TIMEOUT seconds, but respect stop requests.
        # Also exit early if the node process never appeared / already died.
        elapsed = 0
        while elapsed < STARTUP_TIMEOUT:
            if self._stop_event.is_set():
                return StartAttemptResult.STOPPED
            time.sleep(CHECK_INTERVAL)
            elapsed += CHECK_INTERVAL
            if self._gateway.is_quick_alive():
                return StartAttemptResult.SUCCESS
            # Early-exit: after 10 s, if no node process is running the start
            # command failed quickly (e.g. port still occupied). Clean up and
            # let the caller retry immediately instead of waiting 90 s.
            if elapsed >= 10 and not self._gateway.is_process_running():
                self._log("→ 网关进程启动后意外退出（可能端口冲突），立即清理重试...")
                self._cleanup_stale_process()
                return StartAttemptResult.EARLY_EXIT
        # Full timeout — kill what we started so next attempt is clean
        self._log("→ 启动超时，清理本次残留进程，准备下次重试...")
        self._cleanup_stale_process()
        return StartAttemptResult.TIMEOUT

    def start_watching(self) -> None:
        """Called when user clicks '开始看门'."""
        if self._state != WatchdogState.STOPPED:
            return
        self._reset_restart_count()
        self._stop_event.clear()
        self._set_state(WatchdogState.STARTING)  # Set synchronously before thread spawns
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Called when user clicks '关闭看门' or exits."""
        self._set_state(WatchdogState.STOPPED)
        self._stop_event.set()

    def _run(self) -> None:
        """Main watchdog loop."""
        # State is already STARTING (set by start_watching before this thread spawned)

        # ── Phase 1: Initial startup ──────────────────────────────────
        if self._gateway.is_quick_alive():
            self._log("● 检测到网关已在运行，开始监控")
            self._set_state(WatchdogState.RUNNING)

        if self._state != WatchdogState.RUNNING:
            success = False
            for attempt in range(1, MAX_RETRY_COUNT + 1):
                if self._stop_event.is_set():
                    self._log("● 已取消启动监控")
                    self._cleanup_stale_process(log_cleanup=False)
                    return
                self._log(f"⚡ 启动网关 (第 {attempt}/{MAX_RETRY_COUNT} 次)...")
                result = self._attempt_start()
                if result == StartAttemptResult.SUCCESS:
                    self._set_gateway_presence(True)
                    self._log("✓ 网关启动成功")
                    self._set_state(WatchdogState.RUNNING)
                    success = True
                    break
                if result == StartAttemptResult.STOPPED:
                    self._log("● 启动过程已取消")
                    self._cleanup_stale_process(log_cleanup=False)
                    return
                if result == StartAttemptResult.TIMEOUT:
                    self._log(f"✗ 第 {attempt} 次启动超时")
                elif result == StartAttemptResult.EARLY_EXIT:
                    self._log(f"✗ 第 {attempt} 次启动失败：进程意外退出")

            if not success:
                self._set_gateway_presence(False)
                self._log("✗ 网关启动失败，请手动检查 OpenClaw 安装")
                self._notify("❌ 启动失败", "网关启动失败，请手动检查OpenClaw")
                self._set_state(WatchdogState.STOPPED)
                return

        # ── Phase 2: Monitor loop ─────────────────────────────────────
        check_count = 0
        while not self._stop_event.is_set():
            # Sleep MONITOR_INTERVAL seconds.
            # Every CHECK_INTERVAL seconds, also do a cheap process check so
            # that if the gateway dies mid-countdown we skip the remaining wait.
            for tick in range(MONITOR_INTERVAL):
                if self._stop_event.is_set():
                    return
                time.sleep(1)
                if tick > 0 and tick % CHECK_INTERVAL == 0:
                    if not self._gateway.is_quick_alive():
                        self._log("⚡ 检测到网关进程意外退出，跳过等待立即重启...")
                        break
            else:
                # Countdown completed normally → scheduled check
                check_count += 1
                self._log(f"→ 定时检查中... (第 {check_count} 次)")

            if self._stop_event.is_set():
                return

            if self._gateway.is_alive():
                self._set_gateway_presence(True)
                self._log("✓ 网关运行正常")
                continue

            if self._gateway.is_quick_alive():
                self._set_gateway_presence(True)
                self._log("→ 网关进程与端口正常，但应用层健康检查暂未通过")
                continue

            # ── Gateway down: restart ─────────────────────────────────
            self._set_gateway_presence(False)
            self._log("✗ 网关异常退出！准备重启...")
            self._notify("⚠️ 网关已停止", "OpenClaw网关异常退出，正在自动重启...")
            self._set_state(WatchdogState.RESTARTING)

            restarted = False
            for attempt in range(1, MAX_RETRY_COUNT + 1):
                if self._stop_event.is_set():
                    self._log("● 已取消自动重启")
                    self._cleanup_stale_process(log_cleanup=False)
                    return
                self._log(f"⚡ 重启网关 (第 {attempt}/{MAX_RETRY_COUNT} 次)...")
                result = self._attempt_start()
                if result == StartAttemptResult.SUCCESS:
                    self._set_gateway_presence(True)
                    self._log("✓ 网关重启成功！已恢复正常运行")
                    self._notify("✅ 网关已恢复", "OpenClaw网关已恢复正常运行")
                    self._increment_restart_count()
                    self._set_state(WatchdogState.RUNNING)
                    restarted = True
                    break
                if result == StartAttemptResult.STOPPED:
                    self._log("● 自动重启已取消")
                    self._cleanup_stale_process(log_cleanup=False)
                    return
                if result == StartAttemptResult.TIMEOUT:
                    self._log(f"✗ 第 {attempt} 次重启超时")
                elif result == StartAttemptResult.EARLY_EXIT:
                    self._log(f"✗ 第 {attempt} 次重启失败：进程意外退出")

            if not restarted:
                self._set_gateway_presence(False)
                self._log("✗ 网关重启失败，请手动检查")
                self._notify("❌ 重启失败", "网关重启失败，请手动检查OpenClaw")
                self._set_state(WatchdogState.STOPPED)
                return
