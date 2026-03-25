# core/gateway.py
import socket
import subprocess
import time
import psutil
from config import GATEWAY_PORT, SOCKET_TIMEOUT, GATEWAY_PROCESS_NAME, GATEWAY_STOP_CMD, GATEWAY_START_CMD, STOP_WAIT


class GatewayManager:
    def is_process_running(self) -> bool:
        """Check if any openclawgateway process is running."""
        for proc in psutil.process_iter(["name"]):
            try:
                if GATEWAY_PROCESS_NAME.lower() in (proc.info["name"] or "").lower():
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
                if GATEWAY_PROCESS_NAME.lower() in (proc.info["name"] or "").lower():
                    proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
