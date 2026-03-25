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
