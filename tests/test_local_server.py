"""Local mlx_lm.server lifecycle tests for S9 (issue #12), fully faked.

chat/local_server.py is about process bookkeeping: start once, reuse while the
pinned model is unchanged, restart when the model changes, trust a port someone
else already serves, and reap children on exit. subprocess.Popen and the port
probe are fakes, so these run in milliseconds on any OS.
"""

import pytest

import chat.local_server as ls


class FakePopen:
    """Minimal stand-in for subprocess.Popen with scriptable liveness."""

    started: list["FakePopen"] = []

    def __init__(self, args, **kwargs):
        self.args = list(args)
        self.returncode = None
        self.terminated = False
        self.killed = False
        self.kwargs = kwargs
        FakePopen.started.append(self)

    def model(self):
        return self.args[self.args.index("--model") + 1]

    def port(self):
        return int(self.args[self.args.index("--port") + 1])

    def poll(self):
        return self.returncode

    def terminate(self):
        self.terminated = True
        self.returncode = 0

    def kill(self):
        self.killed = True

    def wait(self, timeout=None):
        return 0


class Ctx:
    """Controls which ports answer. A port answers if a live fake serves it
    or it was explicitly marked foreign (already owned outside the app)."""

    def __init__(self):
        self.foreign: set[int] = set()

    def probe(self, port: int) -> bool:
        if port in self.foreign:
            return True
        return any(p.port() == port and p.poll() is None for p in FakePopen.started)

    def by_port(self, port: int):
        return [p for p in FakePopen.started if p.port() == port]

    def ensure(self, fine_tuned="fused-v1", base="base-v1"):
        return ls.ensure_local_servers(fine_tuned, base)


@pytest.fixture()
def lanes(monkeypatch, tmp_path):
    FakePopen.started = []
    monkeypatch.setattr(ls, "_servers", {})
    monkeypatch.setattr(ls, "_shutdown_registered", True)
    monkeypatch.setenv("LLMTUNER_HOME", str(tmp_path))
    ctx = Ctx()
    monkeypatch.setattr(ls, "_port_responding", ctx.probe)
    monkeypatch.setattr("subprocess.Popen", FakePopen)
    return ctx


def test_starts_both_ports_once_and_reports_ok(lanes):
    results = lanes.ensure()
    assert results == {"fine_tuned": None, "vanilla": None}
    assert {p.model(): p.port() for p in FakePopen.started} == {
        "fused-v1": ls.PORTS["fine_tuned"],
        "base-v1": ls.PORTS["vanilla"],
    }
    for p in FakePopen.started:
        assert "--host" in p.args and "127.0.0.1" in p.args


def test_alive_server_with_same_model_is_reused(lanes):
    lanes.ensure()
    assert len(FakePopen.started) == 2
    lanes.ensure()  # second turn must not spawn anything new
    assert len(FakePopen.started) == 2


def test_model_change_restarts_the_lane(lanes):
    lanes.ensure(fine_tuned="fused-v1", base="base-v1")
    first = lanes.by_port(ls.PORTS["fine_tuned"])[0]
    results = lanes.ensure(fine_tuned="fused-v2", base="base-v1")
    assert results == {"fine_tuned": None, "vanilla": None}
    assert first.terminated
    assert lanes.by_port(ls.PORTS["fine_tuned"])[-1].model() == "fused-v2"
    # the untouched lane stayed up
    assert not any(p.terminated for p in lanes.by_port(ls.PORTS["vanilla"]))


def test_foreign_server_on_port_is_trusted_not_fought(lanes):
    lanes.foreign.update(ls.PORTS.values())  # manual mlx_lm.server already up
    results = lanes.ensure()
    assert results == {"fine_tuned": None, "vanilla": None}
    assert FakePopen.started == []  # no child spawned over a live port


def test_dead_child_is_respawned(lanes):
    lanes.ensure()
    victim = lanes.by_port(ls.PORTS["vanilla"])[0]
    victim.returncode = 1  # it died between turns; the port stops answering
    lanes.ensure()
    respawned = lanes.by_port(ls.PORTS["vanilla"])[-1]
    assert respawned is not victim


def test_boot_failure_message(lanes, monkeypatch):
    class InstantDeath(FakePopen):
        def __init__(self, args, **kwargs):
            super().__init__(args, **kwargs)
            self.returncode = 3

    import subprocess as sp

    monkeypatch.setattr(sp, "Popen", InstantDeath)
    results = lanes.ensure()
    assert results["fine_tuned"] and "exited (code 3)" in results["fine_tuned"]
    assert results["vanilla"] and "exited (code 3)" in results["vanilla"]


def test_reap_terminates_every_child(lanes):
    lanes.ensure()
    procs = list(FakePopen.started)
    ls._reap()
    assert all(p.terminated for p in procs)
    assert ls._servers == {}
