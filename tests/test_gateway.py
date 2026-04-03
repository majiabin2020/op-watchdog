from core.gateway import GatewayManager


class FakeProc:
    def __init__(self, name, cmdline):
        self.info = {"name": name, "cmdline": cmdline}
        self.killed = False

    def kill(self):
        self.killed = True


def test_kill_all_only_targets_openclaw_processes(monkeypatch):
    target = FakeProc("node.exe", ["node", "openclaw", "gateway"])
    other_node = FakeProc("node.exe", ["node", "vite"])
    other_proc = FakeProc("python.exe", ["python", "script.py"])

    monkeypatch.setattr(
        "core.gateway.psutil.process_iter",
        lambda attrs: iter([target, other_node, other_proc]),
    )

    manager = GatewayManager()
    manager.kill_all()

    assert target.killed is True
    assert other_node.killed is False
    assert other_proc.killed is False


def test_is_alive_requires_cli_health_probe(monkeypatch):
    monkeypatch.setattr(GatewayManager, "is_process_running", lambda self: True)
    monkeypatch.setattr(GatewayManager, "is_port_open", lambda self: True)
    monkeypatch.setattr(GatewayManager, "is_rpc_healthy", lambda self: False)

    manager = GatewayManager()

    assert manager.is_alive() is False


def test_resolve_openclaw_command_prefers_direct_node_entry(monkeypatch, tmp_path):
    base = tmp_path / "nodejs"
    entry = base / "node_modules" / "openclaw"
    entry.mkdir(parents=True)
    (base / "node.exe").write_text("", encoding="utf-8")
    (entry / "openclaw.mjs").write_text("", encoding="utf-8")

    monkeypatch.setattr("core.gateway.shutil.which", lambda name: str(base / "openclaw.cmd"))

    manager = GatewayManager()
    command = manager._resolve_openclaw_command(["gateway"])

    assert command == [
        str(base / "node.exe"),
        str(entry / "openclaw.mjs"),
        "gateway",
    ]


def test_start_launches_gateway_in_background_without_console(monkeypatch):
    captured = {}

    def fake_popen(cmd, creationflags):
        captured["cmd"] = cmd
        captured["creationflags"] = creationflags
        return object()

    monkeypatch.setattr("core.gateway.subprocess.Popen", fake_popen)
    monkeypatch.setattr(
        GatewayManager,
        "_resolve_openclaw_command",
        lambda self, args: ["node.exe", "openclaw.mjs", *args],
    )

    manager = GatewayManager()
    manager.start()

    assert captured["cmd"] == ["node.exe", "openclaw.mjs", "gateway"]
    assert captured["creationflags"] == manager._BACKGROUND_CREATION_FLAGS
