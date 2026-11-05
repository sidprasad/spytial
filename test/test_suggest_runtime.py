"""Check transport parity, process reuse, failure isolation and search budgets."""

import subprocess
import threading

import pytest
from hypothesis import strategies as st

from spytial._conformance import run_cases
from spytial.suggest import HypothesisSearch
from spytial.suggest._eval import evaluate_selectors
from spytial.suggest._runtime import CoreRuntime
from test_suggest_session import session, Provider, tree, state


def test_worker_matches_released_cli_and_selectors_across_requests():
    with session() as s:
        datum = s._datum(tree())
        worker = s._checks._runtime
        cases = [
            {
                "name": "empty",
                "datum": datum,
                "spec": {"constraints": [], "directives": []},
            }
        ]
        assert worker.run_cases(cases) == run_cases(cases)
        process = worker._process
        for selectors in (["left", "Tree"], ["none", "bad .."], ["right"]):
            assert worker.evaluate_selectors(datum, selectors) == evaluate_selectors(
                datum, selectors
            )
        cyclic = tree()
        cyclic.left = cyclic
        assert worker.evaluate_selectors(
            s._datum(cyclic), ["left"]
        ) == evaluate_selectors(s._datum(cyclic), ["left"])
        assert worker.run_cases(cases) == run_cases(cases)
        assert worker._process is process and process.poll() is None
    assert process.poll() is not None


def test_one_process_serves_generation_votes_and_printing(monkeypatch):
    processes = []
    original = subprocess.Popen

    def counted(*args, **kwargs):
        process = original(*args, **kwargs)
        processes.append(process)
        return process

    monkeypatch.setattr(subprocess, "Popen", counted)
    with session(proposer=Provider()) as s:
        assert not processes
        s._submit_prompt("Parents above children")
        s.judge("left", layout_states=[state(-120, 150), state(120, -150)])
        assert "Parents above children" in str(s.spec)
        assert len(processes) == 1
    assert processes[0].poll() is not None
    assert "Parents above children" in str(s.spec)
    assert len(processes) == 1


def test_worker_timeout_kills_process_and_next_request_can_restart(monkeypatch):
    original = subprocess.Popen
    processes = []

    def stalled(args, **kwargs):
        process = original([args[0], "-e", "setInterval(() => {}, 1000)"], **kwargs)
        processes.append(process)
        return process

    worker = CoreRuntime()
    try:
        with monkeypatch.context() as patch:
            patch.setattr(subprocess, "Popen", stalled)
            with pytest.raises(RuntimeError, match="exceeded"):
                worker.request({"kind": "check", "cases": []}, timeout=0.1)
        assert processes[0].poll() is not None
        with session() as s:
            result = worker.evaluate_selectors(s._datum(tree()), ["left"])
        assert result[0].ok
    finally:
        worker.close()


def test_worker_error_is_not_a_negative_verdict():
    worker = CoreRuntime()
    try:
        with pytest.raises(RuntimeError, match="Unknown request"):
            worker.request({"kind": "unknown"})
        assert worker._process is None
    finally:
        worker.close()


def test_search_bounds_include_shrinking_and_keep_a_checked_witness():
    search = HypothesisSearch(st.integers(0, 10000))
    checked = []

    def predicate(value):
        checked.append(value)
        return True

    witness = search.find(int, predicate, max_examples=1)
    assert len(checked) == 1 and witness == checked[0]
    assert search.last_run["checks"] == 1 and search.last_run["limited"]


def test_search_time_budget_stops_starting_checks(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr("spytial.suggest._search.time.monotonic", lambda: clock[0])
    search = HypothesisSearch(st.integers(), max_seconds=5)
    checked = []

    def predicate(value):
        checked.append(value)
        clock[0] += 6
        return False

    assert search.find(int, predicate, max_examples=20) is None
    assert len(checked) == 1 and search.last_run["limited"]


@pytest.mark.parametrize("max_examples", [1, 20])
def test_search_errors_still_propagate(max_examples):
    def broken(value):
        raise ValueError("broken generator/check")

    with pytest.raises(ValueError, match="broken generator/check"):
        HypothesisSearch(st.just(1)).find(int, broken, max_examples=max_examples)


def test_close_does_not_wait_for_model_or_start_checks_after_response():
    entered, release = threading.Event(), threading.Event()
    errors = []

    def slow(prompt, *, schema):
        entered.set()
        assert release.wait(10)
        return Provider()(prompt, schema=schema)

    with session(proposer=slow) as s:
        runtime = s._checks._runtime

        def request():
            try:
                s._submit_prompt("Parents above children")
            except RuntimeError as exc:
                errors.append(str(exc))

        thread = threading.Thread(target=request)
        thread.start()
        try:
            assert entered.wait(5)
            s.close()
            assert thread.is_alive() and s._closed
        finally:
            release.set()
            thread.join(5)
        assert not thread.is_alive()
        assert errors == ["This session was closed during generation."]
        assert not s.requirements and runtime._process is None
