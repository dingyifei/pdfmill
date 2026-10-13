"""Tests for watch mode (polling, stability, state, no double processing)."""

import json
import os
import threading
import time

import pytest

from pdfmill.config import parse_config
from pdfmill.processor import RunResult
from pdfmill.watcher import STATE_FILENAME, Watcher


class FakeProcess:
    def __init__(self, fail=(), raise_for=()):
        self.calls = []
        self.fail = set(fail)
        self.raise_for = set(raise_for)

    def __call__(self, config, input_path, output_dir=None, dry_run=False):
        self.calls.append(input_path.name)
        if input_path.name in self.raise_for:
            raise RuntimeError("boom")
        result = RunResult(sources=[input_path])
        if input_path.name in self.fail:
            result.failed[input_path] = "failed"
        return result


@pytest.fixture
def config():
    return parse_config({"outputs": {"a": {"pages": "all"}}, "watch": {"debounce_delay": 0}})


def age(path, seconds=10):
    t = time.time() - seconds
    os.utime(path, (t, t))


def make_watcher(config, d, **kw):
    kw.setdefault("process_fn", FakeProcess())
    return Watcher(config, d, **kw)


def test_new_file_processed_once_after_stable(config, tmp_path, make_pdf):
    w = make_watcher(config, tmp_path)
    age(make_pdf("a.pdf"))
    assert w.poll() == []  # first sighting: not yet known to be stable
    assert [p.name for p in w.poll()] == ["a.pdf"]
    assert w.poll() == [] and w.poll() == []
    assert w.process_fn.calls == ["a.pdf"]


def test_growing_file_waits(config, tmp_path, make_pdf):
    w = make_watcher(config, tmp_path)
    path = make_pdf("a.pdf")
    age(path)
    w.poll()
    with open(path, "ab") as f:
        f.write(b"\n% more")
    age(path)
    assert w.poll() == []  # changed since last poll
    assert len(w.poll()) == 1


def test_debounce_uses_mtime(tmp_path, make_pdf):
    config = parse_config({"outputs": {"a": {"pages": "all"}}, "watch": {"debounce_delay": 60}})
    w = make_watcher(config, tmp_path)
    make_pdf("a.pdf")  # just written
    w.poll()
    assert w.poll() == []


def test_state_survives_restart(config, tmp_path, make_pdf):
    age(make_pdf("a.pdf"))
    w = make_watcher(config, tmp_path)
    w.poll(), w.poll()
    state = json.loads((tmp_path / STATE_FILENAME).read_text())
    assert list(state["files"]) == ["a.pdf"]

    w2 = make_watcher(config, tmp_path)
    w2.poll(), w2.poll()
    assert w2.process_fn.calls == []


def test_modified_file_reprocessed(config, tmp_path, make_pdf):
    path = make_pdf("a.pdf")
    age(path, 20)
    w = make_watcher(config, tmp_path)
    w.poll(), w.poll()
    age(path, 5)  # new mtime
    w.poll(), w.poll()
    assert w.process_fn.calls == ["a.pdf", "a.pdf"]


@pytest.mark.parametrize("fake", [FakeProcess(fail={"a.pdf"}), FakeProcess(raise_for={"a.pdf"})])
def test_failure_not_retried_until_restart(config, tmp_path, make_pdf, fake):
    age(make_pdf("a.pdf"))
    w = make_watcher(config, tmp_path, process_fn=fake)
    for _ in range(4):
        w.poll()
    assert fake.calls == ["a.pdf"]
    assert not (tmp_path / STATE_FILENAME).exists()

    w2 = make_watcher(config, tmp_path, process_fn=fake)
    w2.poll(), w2.poll()
    assert fake.calls == ["a.pdf", "a.pdf"]


def test_dry_run_saves_no_state(config, tmp_path, make_pdf):
    age(make_pdf("a.pdf"))
    w = make_watcher(config, tmp_path, dry_run=True)
    w.poll(), w.poll()
    assert w.process_fn.calls == ["a.pdf"]
    assert not (tmp_path / STATE_FILENAME).exists()


def test_cleanup_source_deleted_file_is_fine(config, tmp_path, make_pdf):
    age(make_pdf("a.pdf"))

    def process_and_delete(config, input_path, **kw):
        input_path.unlink()
        return RunResult(sources=[input_path])

    w = make_watcher(config, tmp_path, process_fn=process_and_delete)
    w.poll(), w.poll()
    assert "a.pdf" in w.done


def test_corrupt_state_ignored(config, tmp_path):
    (tmp_path / STATE_FILENAME).write_text("{not json")
    assert make_watcher(config, tmp_path).done == {}


def test_run_skips_existing_when_asked(config, tmp_path, make_pdf):
    age(make_pdf("old.pdf"))
    fake = FakeProcess()
    w = Watcher(config, tmp_path, process_existing=False, poll_interval=0.01, process_fn=fake)
    thread = threading.Thread(target=w.run)
    thread.start()
    time.sleep(0.05)
    age(make_pdf("new.pdf"))
    deadline = time.time() + 5
    while "new.pdf" not in fake.calls and time.time() < deadline:
        time.sleep(0.01)
    w.stop()
    thread.join(timeout=5)
    assert fake.calls == ["new.pdf"]


def test_cli_overrides_and_config_defaults(tmp_path):
    config = parse_config(
        {
            "outputs": {"a": {"pages": "all"}},
            "watch": {"poll_interval": 7, "debounce_delay": 3, "process_existing": False},
        }
    )
    w = Watcher(config, tmp_path)
    assert (w.poll_interval, w.debounce_delay, w.process_existing) == (7, 3, False)
    w = Watcher(config, tmp_path, poll_interval=1, debounce_delay=0, process_existing=True)
    assert (w.poll_interval, w.debounce_delay, w.process_existing) == (1, 0, True)
