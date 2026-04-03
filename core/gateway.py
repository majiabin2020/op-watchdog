# core/gateway.py
import socket
import subprocess
from pathlib import Path
import shutil

import psutil

from config import (
    GATEWAY_PORT,
    GATEWAY_HEALTH_ARGS,
    GATEWAY_PROCESS_CMDLINE,
    GATEWAY_PROCESS_NAME,
    GATEWAY_START_ARGS,
    GATEWAY_STOP_ARGS,
    HEALTHCHECK_TIMEOUT,
    OPENCLAW_ENTRY_SCRIPT,
    SOCKET_TIMEOUT,
)


class GatewayManager:
    _BACKGROUND_CREATION_FLAGS = (
        subprocess.CREATE_NO_WINDOW
        | subprocess.DETACHED_PROCESS
        | subprocess.CREATE_NEW_PROCESS_GROUP
    )

    def _is_gateway_process(self, proc: psutil.Process) -> bool:
        name = (proc.info.get("name") or "").lower()
        if GATEWAY_PROCESS_NAME.lower() not in name:
            return False

        cmdline = " ".join(proc.info.get("cmdline") or []).lower()
        return GATEWAY_PROCESS_CMDLINE.lower() in cmdline

    def _resolve_openclaw_command(self, args: list[str]) -> list[str]:
        """Resolve the most direct way to invoke OpenClaw on Windows."""
        openclaw_path = shutil.which("openclaw.cmd") or shutil.which("openclaw")
        if openclaw_path:
            base_dir = Path(openclaw_path).resolve().parent
            node_path = base_dir / "node.exe"
            entry_script = base_dir.joinpath(*OPENCLAW_ENTRY_SCRIPT)
            if node_path.exists() and entry_script.exists():
                return [str(node_path), str(entry_script), *args]

        return ["openclaw", *args]

    def get_launch_mode(self) -> str:
        """Return a human-readable description of the current launch mode."""
        command = self._resolve_openclaw_command(GATEWAY_START_ARGS)
        if len(command) >= 2:
            executable = Path(command[0]).name.lower()
            script_name = Path(command[1]).name.lower()
            if executable == "node.exe" and script_name == "openclaw.mjs":
                return "后台直连 node"
        return "后台调用 openclaw CLI"

    def iter_gateway_processes(self):
        """Yield node processes that belong to the OpenClaw gateway."""
        for proc in psutil.process_iter(["name", "cmdline"]):
            try:
                if self._is_gateway_process(proc):
                    yield proc
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

    def is_process_running(self) -> bool:
        """Check if the openclaw gateway node process is running.
        Matches node processes whose cmdline contains 'openclaw'."""
        return any(True for _ in self.iter_gateway_processes())

    def is_port_open(self) -> bool:
        """Quick TCP probe: the gateway port is accepting connections."""
        try:
            with socket.create_connection(("127.0.0.1", GATEWAY_PORT), timeout=SOCKET_TIMEOUT):
                return True
        except (ConnectionRefusedError, socket.timeout, OSError):
            return False

    def is_quick_alive(self) -> bool:
        """Fast liveness check used for tight monitoring loops."""
        return self.is_process_running() and self.is_port_open()

    def is_rpc_healthy(self) -> bool:
        """Official CLI health probe against the running OpenClaw gateway."""
        try:
            result = subprocess.run(
                self._resolve_openclaw_command(GATEWAY_HEALTH_ARGS),
                creationflags=subprocess.CREATE_NO_WINDOW,
                capture_output=True,
                text=True,
                timeout=HEALTHCHECK_TIMEOUT,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return False

        return result.returncode == 0

    def is_alive(self) -> bool:
        """Strong health check: process + port + official OpenClaw health probe."""
        if not self.is_quick_alive():
            return False
        return self.is_rpc_healthy()

    def start(self) -> subprocess.Popen:
        """Launch openclaw gateway directly in the background with no shell host."""
        return subprocess.Popen(
            self._resolve_openclaw_command(GATEWAY_START_ARGS),
            creationflags=self._BACKGROUND_CREATION_FLAGS,
        )

    def stop(self) -> None:
        """Stop the gateway silently without spawning a visible shell."""
        try:
            subprocess.run(
                self._resolve_openclaw_command(GATEWAY_STOP_ARGS),
                creationflags=subprocess.CREATE_NO_WINDOW,
                timeout=15,
            )
        except subprocess.TimeoutExpired:
            pass

    def kill_all(self) -> None:
        """Forcefully kill OpenClaw gateway processes via psutil."""
        for proc in self.iter_gateway_processes():
            try:
                proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
