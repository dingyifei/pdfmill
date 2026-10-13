"""Tests for the print pipeline and the CUPS / SumatraPDF backends."""

import subprocess
from pathlib import Path

import pytest

from pdfmill.config import PrintTarget, parse_config
from pdfmill.printing import PrinterError, PrintSafetyError, check_safety, get_backend, print_profile, split_by_weight
from pdfmill.printing.cups import CupsBackend
from pdfmill.printing.sumatra import SumatraBackend


def profile(**print_cfg):
    return parse_config({"outputs": {"label": {"pages": "all", "print": {"enabled": True, **print_cfg}}}}).outputs[
        "label"
    ]


class TestPrintProfile:
    def test_each_file_to_each_target(self, make_pdf, backend, tmp_path):
        files = [make_pdf("a.pdf"), make_pdf("b.pdf")]
        prof = profile(targets={"x": {"printer": "Label"}, "y": {"printer": "Laser"}})
        jobs = print_profile(prof, files, backend, tmp_path)
        assert jobs == ["Label-1", "Laser-2", "Label-3", "Laser-4"]
        assert [(p, f.name) for p, f, _ in backend.jobs] == [
            ("Label", "a.pdf"),
            ("Laser", "a.pdf"),
            ("Label", "b.pdf"),
            ("Laser", "b.pdf"),
        ]

    def test_merge_into_one_job(self, make_pdf, backend, tmp_path):
        files = [make_pdf("a.pdf", sizes=[(612, 792)] * 2), make_pdf("b.pdf")]
        print_profile(profile(printer="Label", merge=True), files, backend, tmp_path)
        assert [(p, n) for p, _, n in backend.jobs] == [("Label", 3)]

    def test_merge_and_split_by_weight(self, make_pdf, backend, tmp_path):
        files = [make_pdf(f"{i}.pdf", sizes=[(612, 792)] * 3) for i in range(3)]  # 9 pages
        prof = profile(
            merge=True, targets={"slow": {"printer": "Laser", "weight": 1}, "fast": {"printer": "Label", "weight": 2}}
        )
        print_profile(prof, files, backend, tmp_path)
        assert [(p, n) for p, _, n in backend.jobs] == [("Label", 6), ("Laser", 3)]

    def test_checks_all_printers_before_printing(self, make_pdf, backend, tmp_path):
        prof = profile(targets={"x": {"printer": "Label"}, "y": {"printer": "Gone"}})
        with pytest.raises(PrinterError, match="Gone"):
            print_profile(prof, [make_pdf()], backend, tmp_path)
        assert backend.jobs == []  # nothing half-printed

    def test_backend_failure_raises(self, make_pdf, tmp_path):
        from tests.conftest import FakeBackend

        with pytest.raises(PrinterError, match="rejected"):
            print_profile(profile(printer="Label"), [make_pdf()], FakeBackend(failing={"Label"}), tmp_path)

    def test_dry_run_prints_nothing(self, make_pdf, backend, tmp_path):
        assert print_profile(profile(printer="Label"), [make_pdf()], backend, tmp_path, dry_run=True) == []
        assert backend.jobs == []


class TestSafety:
    def cfg(self, **kw):
        return profile(printer="Label", **kw).print

    def test_no_limits(self, make_pdf):
        check_safety([make_pdf(sizes=[(9999, 9999)])], self.cfg(), "label")

    def test_max_pages(self, make_pdf):
        files = [make_pdf("a.pdf", sizes=[(612, 792)] * 2), make_pdf("b.pdf")]
        check_safety(files, self.cfg(max_pages=3), "label")
        with pytest.raises(PrintSafetyError, match="3 pages exceeds max_pages"):
            check_safety(files, self.cfg(max_pages=2), "label")

    def test_max_page_size_either_orientation(self, make_pdf):
        cfg = self.cfg(max_page_size=["4.1in", "6.1in"])
        check_safety([make_pdf(sizes=[(288, 432), (432, 288)])], cfg, "label")
        with pytest.raises(PrintSafetyError, match="exceeds max_page_size"):
            check_safety([make_pdf(sizes=[(612, 792)])], cfg, "label")

    def test_warn_only(self, make_pdf):
        check_safety([make_pdf(sizes=[(612, 792)])], self.cfg(max_page_size=["4in", "6in"], action="warn"), "label")

    def test_unreadable_file_fails_closed(self, tmp_path):
        bad = tmp_path / "bad.pdf"
        bad.write_bytes(b"not a pdf")
        with pytest.raises(PrintSafetyError, match="cannot read"):
            check_safety([bad], self.cfg(max_pages=10), "label")

    def test_blocks_before_printing(self, make_pdf, backend, tmp_path):
        with pytest.raises(PrintSafetyError):
            print_profile(profile(printer="Label", max_pages=1), [make_pdf(sizes=[(612, 792)] * 2)], backend, tmp_path)
        assert backend.jobs == []


class TestSplitByWeight:
    def targets(self, **weights):
        return {name: PrintTarget(printer=name, weight=w) for name, w in weights.items()}

    def test_rounding_gives_remainder_to_last(self, make_pdf, tmp_path):
        parts = split_by_weight(make_pdf(sizes=[(100, 100)] * 10), self.targets(a=1, b=1, c=1), tmp_path)
        from pypdf import PdfReader

        assert [len(PdfReader(p).pages) for p, _ in parts] == [3, 3, 4]

    def test_zero_weight_skipped(self, make_pdf, tmp_path):
        parts = split_by_weight(make_pdf(sizes=[(100, 100)] * 4), self.targets(a=0, b=1), tmp_path)
        assert [t.printer for _, t in parts] == ["b"]

    def test_all_zero(self, make_pdf, tmp_path):
        with pytest.raises(PrinterError):
            split_by_weight(make_pdf(), self.targets(a=0), tmp_path)

    def test_fewer_pages_than_targets(self, make_pdf, tmp_path):
        parts = split_by_weight(make_pdf(), self.targets(a=5, b=1), tmp_path)
        assert [t.printer for _, t in parts] == ["a"]


def completed(stdout="", returncode=0, stderr=""):
    return subprocess.CompletedProcess([], returncode, stdout=stdout, stderr=stderr)


class TestCups:
    @pytest.fixture
    def lp(self, monkeypatch):
        """Fake lp/lpstat. Set ``responses[cmd_prefix] = CompletedProcess``; calls are recorded."""
        calls = []
        responses = {
            ("lpstat", "-e"): completed("Brother_HL_L2420DW\nPL80E-BT\n"),
            ("lpstat", "-a"): completed("PL80E-BT accepting requests since Thu"),
            ("lpstat", "-p"): completed("printer PL80E-BT is idle.  enabled since Thu"),
            ("lp",): completed("request id is PL80E-BT-42 (1 file(s))\n"),
        }

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            for prefix in sorted(responses, key=len, reverse=True):
                if tuple(cmd[: len(prefix)]) == prefix:
                    return responses[prefix]
            raise AssertionError(f"unexpected command {cmd}")

        monkeypatch.setattr("pdfmill.printing.cups.shutil.which", lambda name: f"/usr/bin/{name}")
        monkeypatch.setattr("pdfmill.printing.cups.subprocess.run", fake_run)
        return calls, responses

    def target(self, **kw):
        return PrintTarget(printer="PL80E-BT", **kw)

    def test_list_printers(self, lp):
        assert CupsBackend().list_printers() == ["Brother_HL_L2420DW", "PL80E-BT"]

    def test_command(self):
        target = self.target(copies=2, options={"media": "w284h426"}, args=["-q", "50"])
        assert CupsBackend().command(Path("a b.pdf"), target, "label: a") == [
            "lp", "-d", "PL80E-BT", "-n", "2", "-t", "label: a", "-o", "media=w284h426", "-q", "50", "--", "a b.pdf",
        ]  # fmt: skip

    def test_print_returns_job_id(self, lp):
        assert CupsBackend().print_file(Path("a.pdf"), self.target(), "t") == "PL80E-BT-42"

    def test_print_without_job_id_fails(self, lp):
        lp[1][("lp",)] = completed("something odd")
        with pytest.raises(PrinterError, match="job id"):
            CupsBackend().print_file(Path("a.pdf"), self.target(), "t")

    def test_lp_error(self, lp):
        lp[1][("lp",)] = completed(returncode=1, stderr="lp: The printer or class does not exist.")
        with pytest.raises(PrinterError, match="does not exist"):
            CupsBackend().print_file(Path("a.pdf"), self.target(), "t")

    def test_check_printer_ok(self, lp):
        CupsBackend().check_printer("PL80E-BT")

    def test_check_printer_suggests_name(self, lp):
        with pytest.raises(PrinterError, match="Did you mean 'PL80E-BT'"):
            CupsBackend().check_printer("PL80E")

    def test_check_printer_not_accepting(self, lp):
        lp[1][("lpstat", "-a")] = completed("PL80E-BT not accepting requests since Thu -\n\tRejecting Jobs")
        with pytest.raises(PrinterError, match="cupsaccept"):
            CupsBackend().check_printer("PL80E-BT")

    def test_check_printer_paused(self, lp):
        lp[1][("lpstat", "-p")] = completed("printer PL80E-BT disabled since Thu -\n\tUnable to connect")
        with pytest.raises(PrinterError, match="cupsenable PL80E-BT"):
            CupsBackend().check_printer("PL80E-BT")

    def test_missing_cups_tools(self, monkeypatch):
        monkeypatch.setattr("pdfmill.printing.cups.shutil.which", lambda name: None)
        with pytest.raises(PrinterError, match="'lpstat' not found"):
            CupsBackend().list_printers()


class TestSumatra:
    def test_command_keeps_legacy_argument_order(self):
        target = PrintTarget(printer="Brother", copies=2, args=["-print-settings", "simplex"])
        assert SumatraBackend(Path("S.exe")).command(Path("a.pdf"), target, "t") == [
            "S.exe", "-print-settings", "2x", "-print-settings", "simplex", "-print-to", "Brother", "a.pdf",
        ]  # fmt: skip

    def test_nonzero_exit_raises(self, monkeypatch):
        monkeypatch.setattr(
            "pdfmill.printing.sumatra.subprocess.run", lambda *a, **k: completed(returncode=1, stderr="boom")
        )
        with pytest.raises(PrinterError, match="boom"):
            SumatraBackend(Path("S.exe")).print_file(Path("a.pdf"), PrintTarget(printer="X"), "t")

    def test_success(self, monkeypatch):
        monkeypatch.setattr("pdfmill.printing.sumatra.subprocess.run", lambda *a, **k: completed())
        assert SumatraBackend(Path("S.exe")).print_file(Path("a.pdf"), PrintTarget(printer="X"), "t") == "sumatra:a.pdf"

    def test_find_from_env(self, monkeypatch, tmp_path):
        from pdfmill.printing.sumatra import find_sumatra

        exe = tmp_path / "SumatraPDF.exe"
        exe.write_text("")
        monkeypatch.setenv("PDFMILL_SUMATRA_PATH", str(exe))
        assert find_sumatra(download=False) == exe

    def test_not_found_without_download(self, monkeypatch, tmp_path):
        from pdfmill.printing.sumatra import find_sumatra

        monkeypatch.delenv("PDFMILL_SUMATRA_PATH", raising=False)
        monkeypatch.delenv("PDFPIPE_SUMATRA_PATH", raising=False)
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
        monkeypatch.setenv("PATH", "")
        monkeypatch.chdir(tmp_path)
        with pytest.raises(PrinterError, match="not found"):
            find_sumatra(download=False)

    def test_list_printers_needs_windows(self, monkeypatch):
        monkeypatch.setitem(__import__("sys").modules, "win32print", None)
        with pytest.raises(PrinterError, match="only works on Windows"):
            SumatraBackend().list_printers()


def test_get_backend(monkeypatch):
    assert get_backend("cups").name == "cups"
    assert get_backend("sumatra").name == "sumatra"
    monkeypatch.setattr("sys.platform", "win32")
    assert get_backend("auto").name == "sumatra"
    monkeypatch.setattr("sys.platform", "darwin")
    assert get_backend("auto").name == "cups"
    with pytest.raises(ValueError):
        get_backend("magic")
