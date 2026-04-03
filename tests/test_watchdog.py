from core.watchdog import StartAttemptResult, WatchdogState, WatchdogThread


class FakeGateway:
    def __init__(self, *, alive_sequence=None, quick_alive_sequence=None, process_running=False):
        self.alive_sequence = list(alive_sequence or [])
        self.quick_alive_sequence = list(quick_alive_sequence or [])
        self.process_running = process_running
        self.start_calls = 0
        self.kill_calls = 0

    def is_alive(self):
        if self.alive_sequence:
            return self.alive_sequence.pop(0)
        return False

    def is_process_running(self):
        return self.process_running

    def is_quick_alive(self):
        if self.quick_alive_sequence:
            return self.quick_alive_sequence.pop(0)
        return self.process_running

    def start(self):
        self.start_calls += 1
        return DummyProc()

    def get_launch_mode(self):
        return "后台直连 node"

    def kill_all(self):
        self.kill_calls += 1


class DummyProc:
    def terminate(self):
        return None


def test_attempt_start_honors_stop_before_spawning():
    gateway = FakeGateway()
    watchdog = WatchdogThread(gateway=gateway)
    watchdog._stop_event.set()

    result = watchdog._attempt_start()

    assert result == StartAttemptResult.STOPPED
    assert gateway.start_calls == 0


def test_attempt_start_waits_for_strong_health_after_quick_probe(monkeypatch):
    gateway = FakeGateway(
        alive_sequence=[False],
        quick_alive_sequence=[True],
        process_running=True,
    )
    watchdog = WatchdogThread(gateway=gateway)

    monkeypatch.setattr("core.watchdog.time.sleep", lambda _: None)

    result = watchdog._attempt_start()

    assert result == StartAttemptResult.SUCCESS
    assert gateway.start_calls == 1


def test_attempt_start_logs_launch_mode(monkeypatch):
    gateway = FakeGateway(
        alive_sequence=[True],
        quick_alive_sequence=[True],
        process_running=True,
    )
    watchdog = WatchdogThread(gateway=gateway)
    logs = []

    monkeypatch.setattr("core.watchdog.time.sleep", lambda _: None)
    watchdog.on_log = logs.append

    result = watchdog._attempt_start()

    assert result == StartAttemptResult.SUCCESS
    assert any("当前启动方式：后台直连 node" in log for log in logs)


def test_start_watching_resets_restart_count_and_notifies_ui():
    gateway = FakeGateway()
    watchdog = WatchdogThread(gateway=gateway)
    counts = []

    watchdog.restart_count = 5
    watchdog.on_restart_count = counts.append

    watchdog.start_watching()
    watchdog.stop()
    watchdog._thread.join(timeout=1)

    assert watchdog.restart_count == 0
    assert counts[0] == 0


def test_run_cancels_initial_retries_without_starting_again():
    gateway = FakeGateway(alive_sequence=[False], quick_alive_sequence=[False])
    watchdog = WatchdogThread(gateway=gateway)
    logs = []

    watchdog.on_log = logs.append
    watchdog._set_state(WatchdogState.STARTING)
    watchdog._stop_event.set()

    watchdog._run()

    assert gateway.start_calls == 0
    assert "已取消启动监控" in logs[-1]


def test_run_cancels_restart_retries_without_starting_again(monkeypatch):
    gateway = FakeGateway(
        alive_sequence=[True, False, False],
        quick_alive_sequence=[True, False],
        process_running=True,
    )
    watchdog = WatchdogThread(gateway=gateway)
    logs = []

    monkeypatch.setattr("core.watchdog.MONITOR_INTERVAL", 1)
    monkeypatch.setattr("core.watchdog.time.sleep", lambda _: None)

    watchdog.on_log = logs.append
    watchdog._set_state(WatchdogState.STARTING)
    watchdog._stop_event.clear()

    original_set_state = watchdog._set_state

    def intercept_state(state):
        original_set_state(state)
        if state == WatchdogState.RESTARTING:
            watchdog._stop_event.set()

    watchdog._set_state = intercept_state

    watchdog._run()

    assert gateway.start_calls == 0
    assert any("已取消自动重启" in log for log in logs)


def test_monitor_loop_keeps_running_when_quick_alive_but_strong_health_fails(monkeypatch):
    gateway = FakeGateway(
        alive_sequence=[False],
        quick_alive_sequence=[True],
        process_running=True,
    )
    watchdog = WatchdogThread(gateway=gateway)
    logs = []

    monkeypatch.setattr("core.watchdog.MONITOR_INTERVAL", 1)
    monkeypatch.setattr("core.watchdog.time.sleep", lambda _: None)

    watchdog.on_log = logs.append
    watchdog._set_state(WatchdogState.RUNNING)
    watchdog._stop_event.clear()

    original_is_alive = gateway.is_alive

    def stop_after_first_strong_check():
        value = original_is_alive()
        watchdog._stop_event.set()
        return value

    gateway.is_alive = stop_after_first_strong_check

    watchdog._run()

    assert any("应用层健康检查暂未通过" in log for log in logs)
