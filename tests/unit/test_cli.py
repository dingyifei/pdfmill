"""Tests for the pdfm command line."""

import pytest
import yaml

from pdfmill import __version__
from pdfmill.cli import main
from tests.conftest import FakeBackend


@pytest.fixture
def fake_backend(monkeypatch):
    backend = FakeBackend(printers=["PL80E-BT", "Laser"])
    monkeypatch.setattr("pdfmill.printing.get_backend", lambda name="auto": backend)
    monkeypatch.setattr("pdfmill.processor.get_backend", lambda name="auto": backend)
    return backend


@pytest.fixture
def write_config(tmp_path):
    def factory(**profile):
        data = {
            "input": {"path": str(tmp_path / "in")},
            "outputs": {"label": {"pages": "last", "output_dir": str(tmp_path / "out"), **profile}},
        }
        path = tmp_path / "config.yaml"
        path.write_text(yaml.safe_dump(data))
        return path

    return factory


def test_version(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_no_config_prints_help(capsys):
    assert main([]) == 1
    assert "usage: pdfm" in capsys.readouterr().out


def test_list_printers(fake_backend, capsys):
    assert main(["--list-printers"]) == 0
    assert "PL80E-BT" in capsys.readouterr().out


def test_list_printers_empty(monkeypatch):
    monkeypatch.setattr("pdfmill.printing.get_backend", lambda name="auto": FakeBackend(printers=[]))
    assert main(["--list-printers"]) == 1


def test_validate(write_config, capsys):
    assert main(["-c", str(write_config()), "--validate"]) == 0
    assert "Configuration is valid" in capsys.readouterr().out


def test_validate_reports_typo(write_config, tmp_path, capsys):
    path = tmp_path / "bad.yaml"
    path.write_text("outputs:\n  label:\n    pages: last\n    tranforms: []\n")
    assert main(["-c", str(path), "--validate"]) == 1
    assert "did you mean 'transforms'" in capsys.readouterr().err


def test_missing_config(tmp_path, capsys):
    assert main(["-c", str(tmp_path / "nope.yaml"), "--validate"]) == 1
    assert "File not found" in capsys.readouterr().err


def test_strict_validation(write_config, fake_backend, tmp_path, capsys):
    (tmp_path / "in").mkdir()
    config = write_config(print={"enabled": True, "printer": "PL80E-BT"})
    assert main(["-c", str(config), "--validate", "--strict"]) == 0
    assert "Printer OK: PL80E-BT" in capsys.readouterr().out


def test_strict_validation_failures(write_config, fake_backend, capsys):
    config = write_config(print={"enabled": True, "printer": "PL80E"})
    assert main(["-c", str(config), "--validate", "--strict"]) == 1
    err = capsys.readouterr().err
    assert "input path does not exist" in err
    assert "Printer 'PL80E' not found" in err


def test_strict_validation_missing_dependency(write_config, tmp_path, monkeypatch, capsys):
    (tmp_path / "in").mkdir()
    monkeypatch.setattr("pdfmill.cli.importlib.util.find_spec", lambda name: None)
    config = write_config(transforms=[{"stamp": "x"}, {"rotate": "auto"}])
    assert main(["-c", str(config), "--validate", "--strict"]) == 1
    err = capsys.readouterr().err
    assert "pdfmill[stamp]" in err and "pdfmill[ocr]" in err


def test_run_success_and_failure_exit_codes(write_config, fake_backend, make_pdf, tmp_path):
    make_pdf("a.pdf", directory=tmp_path / "in")
    assert main(["-c", str(write_config(print={"enabled": True, "printer": "PL80E-BT"}))]) == 0
    assert [p for p, _, _ in fake_backend.jobs] == ["PL80E-BT"]
    assert main(["-c", str(write_config(print={"enabled": True, "printer": "Missing"}))]) == 1


def test_run_with_input_and_output_override(write_config, make_pdf, tmp_path):
    src = make_pdf("a.pdf")
    assert main(["-c", str(write_config()), "-i", str(src), "-o", str(tmp_path / "o2"), "-q"]) == 0
    assert (tmp_path / "o2" / "a_label.pdf").exists()


def test_dry_run(write_config, fake_backend, make_pdf, tmp_path, capsys):
    make_pdf("a.pdf", directory=tmp_path / "in")
    assert main(["-c", str(write_config(print={"enabled": True, "printer": "PL80E-BT"})), "--dry-run"]) == 0
    assert "[dry-run] Would run: fakeprint PL80E-BT" in capsys.readouterr().out
    assert fake_backend.jobs == []
    assert not (tmp_path / "out").exists()


def test_missing_input_dir(write_config, capsys):
    assert main(["-c", str(write_config())]) == 1
    assert "Input path does not exist" in capsys.readouterr().err


def test_watch_needs_directory(write_config, make_pdf, capsys):
    assert main(["-c", str(write_config()), "-i", str(make_pdf()), "--watch"]) == 1
    assert "--watch needs an input directory" in capsys.readouterr().err


def test_watch_passes_options(write_config, tmp_path, monkeypatch):
    (tmp_path / "in").mkdir()
    created = {}

    class FakeWatcher:
        def __init__(self, config, input_dir, **kwargs):
            created.update(kwargs, input_dir=input_dir)

        def run(self):
            created["ran"] = True

    monkeypatch.setattr("pdfmill.watcher.Watcher", FakeWatcher)
    args = ["-c", str(write_config()), "--watch", "--watch-interval", "5", "--no-process-existing"]
    assert main(args) == 0
    assert created["ran"] and created["input_dir"] == tmp_path / "in"
    assert (created["poll_interval"], created["debounce_delay"], created["process_existing"]) == (5.0, None, False)


def test_backend_flag(write_config, monkeypatch):
    seen = []
    monkeypatch.setattr("pdfmill.printing.get_backend", lambda name="auto": seen.append(name) or FakeBackend())
    main(["--list-printers", "--backend", "cups"])
    assert seen == ["cups"]


def test_unexpected_error_is_reported(write_config, monkeypatch, capsys):
    def boom(*a, **k):
        raise RuntimeError("kaput")

    monkeypatch.setattr("pdfmill.processor.process", boom)
    assert main(["-c", str(write_config())]) == 1
    assert "RuntimeError: kaput" in capsys.readouterr().err
