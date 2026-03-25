# core/gateway.py
import socket
import subprocess
import time
import psutil
from config import GATEWAY_PORT, SOCKET_TIMEOUT, GATEWAY_PROCESS_NAME, GATEWAY_PROCESS_CMDLINE, GATEWAY_STOP_CMD, GATEWAY_START_CMD


class GatewayManager:
    def is_process_running(self) -> bool:
        """Check if the openclaw gateway node process is running.
        Matches node processes whose cmdline contains 'openclaw'."""
        for proc in psutil.process_iter(["name", "cmdline"]):
            try:
                if GATEWAY_PROCESS_NAME.lower() not in (proc.info["name"] or "").lower():
                    continue
                cmdline = " ".join(proc.info["cmdline"] or []).lower()
                if GATEWAY_PROCESS_CMDLINE.lower() in cmdline:
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return False

    def is_alive(self) -> bool:
        """TCP connection check: gateway is up if port 18789 accepts connections."""
        try:
            with socket.create_connection(("127.0.0.1", GATEWAY_PORT), timeout=SOCKET_TIMEOUT):
                return True
        except (ConnectionRefusedError, socket.timeout, OSError):
            return False

    def start(self) -> subprocess.Popen:
        """Launch openclaw gateway in a visible CMD window.
        cmd /k runs the command and keeps the window open.
        Returns the Popen handle so caller can manage it."""
        return subprocess.Popen(
            ["cmd", "/k", GATEWAY_START_CMD],
            creationflags=subprocess.CREATE_NEW_CONSOLE,
        )

    def stop(self) -> None:
        """Run 'openclaw gateway stop' silently via cmd."""
        try:
            subprocess.run(
                ["cmd", "/c", GATEWAY_STOP_CMD],
                creationflags=subprocess.CREATE_NO_WINDOW,
                timeout=15,
            )
        except subprocess.TimeoutExpired:
            pass

    def kill_all(self) -> None:
        """Forcefully kill all node processes via psutil."""
        for proc in psutil.process_iter(["name"]):
            try:
                if GATEWAY_PROCESS_NAME.lower() in (proc.info["name"] or "").lower():
                    proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
