"""Tests for the processing run: selection, outputs, printing, cleanup and failure handling."""

import os

import pytest
from pypdf import PdfReader

from pdfmill.config import parse_config
from pdfmill.processor import ProcessingError, find_inputs, process, sort_files
from tests.conftest import FakeBackend

PACKING = (612, 792)


def make_config(tmp_path, settings=None, input_cfg=None, **profiles):
    data = {"outputs": profiles, "settings": settings or {}, "input": input_cfg or {}}
    for p in profiles.values():
        p.setdefault("output_dir", str(tmp_path / "out"))
    return parse_config(data)


@pytest.fixture
def inbox(tmp_path, make_pdf):
    """Two 3-page orders: packing sheets + a label as the last page."""
    d = tmp_path / "in"
    for name in ("order1.pdf", "order2.pdf"):
        make_pdf(name, sizes=[PACKING, PACKING, (792, 612)], directory=d)
    return d


def label_profiles(label_printer="Label"):
    return {
        "packing": {"pages": "1--1", "print": {"enabled": True, "merge": True, "printer": "Laser"}},
        "label": {
            "pages": "last",
            "transforms": [{"rotate": 90}, {"size": {"width": "4in", "height": "6in"}}],
            "print": {"enabled": True, "merge": True, "printer": label_printer, "max_page_size": ["4.1in", "6.1in"]},
        },
    }


def pages_of(path):
    return [tuple(round(float(v)) for v in p.mediabox[2:]) for p in PdfReader(path).pages]


def test_happy_path_prints_merged_jobs_and_cleans_up(tmp_path, inbox):
    config = make_config(tmp_path, {"cleanup_source": True, "cleanup_output_after_print": True}, **label_profiles())
    backend = FakeBackend()
    result = process(config, inbox, backend=backend)

    assert result.ok
    assert result.jobs == ["Laser-1", "Label-2"]
    assert [(p, n) for p, _, n in backend.jobs] == [("Laser", 4), ("Label", 2)]
    assert list(inbox.iterdir()) == []  # sources removed
    assert list((tmp_path / "out").iterdir()) == []  # printed outputs removed


def test_outputs_written(tmp_path, inbox):
    profiles = label_profiles()
    for p in profiles.values():
        p["print"]["enabled"] = False
    result = process(make_config(tmp_path, **profiles), inbox)
    out = tmp_path / "out"
    assert sorted(p.name for p in out.iterdir()) == [
        "order1_label.pdf", "order1_packing.pdf", "order2_label.pdf", "order2_packing.pdf",
    ]  # fmt: skip
    assert pages_of(out / "order1_label.pdf") == [(288, 432)]
    assert pages_of(out / "order1_packing.pdf") == [(612, 792), (612, 792)]
    assert len(result.outputs) == 4 and result.jobs == []
    assert not list(out.glob("*.part"))


def test_missing_printer_keeps_every_file(tmp_path, inbox):
    """Regression: a failed print used to count as success and cleanup deleted the PDFs."""
    config = make_config(
        tmp_path, {"cleanup_source": True, "cleanup_output_after_print": True}, **label_profiles("Nope")
    )
    backend = FakeBackend()
    result = process(config, inbox, backend=backend)

    assert not result.ok
    assert set(result.failed) == {inbox / "order1.pdf", inbox / "order2.pdf"}
    assert "printing profile 'label' failed" in result.failed[inbox / "order1.pdf"]
    assert sorted(p.name for p in inbox.iterdir()) == ["order1.pdf", "order2.pdf"]
    # packing sheets printed fine and were cleaned; label outputs kept for a manual reprint
    assert sorted(p.name for p in (tmp_path / "out").iterdir()) == ["order1_label.pdf", "order2_label.pdf"]


def test_rejected_job_keeps_sources(tmp_path, inbox):
    config = make_config(tmp_path, {"cleanup_source": True}, **label_profiles())
    result = process(config, inbox, backend=FakeBackend(failing={"Label"}))
    assert not result.ok
    assert len(list(inbox.iterdir())) == 2


def test_only_failed_source_is_kept(tmp_path, inbox, make_pdf):
    make_pdf("order3.pdf", sizes=[PACKING], directory=inbox)  # no label page: "1--1" selects nothing
    config = make_config(
        tmp_path,
        {"cleanup_source": True},
        packing={"pages": "1--1"},
        label={"pages": "last"},
    )
    result = process(config, inbox, backend=FakeBackend())
    assert list(result.failed) == [inbox / "order3.pdf"]
    assert [p.name for p in inbox.iterdir()] == ["order3.pdf"]


def test_corrupt_pdf_does_not_abort_batch(tmp_path, inbox):
    (inbox / "broken.pdf").write_bytes(b"%PDF-1.4 garbage")
    config = make_config(tmp_path, label={"pages": "all"})
    result = process(config, inbox)
    assert list(result.failed) == [inbox / "broken.pdf"]
    assert len(result.succeeded) == 2


def test_on_error_stop(tmp_path, inbox):
    (inbox / "a_broken.pdf").write_bytes(b"garbage")
    config = make_config(tmp_path, {"on_error": "stop"}, label={"pages": "all"})
    with pytest.raises(ProcessingError):
        process(config, inbox)


def test_dry_run_writes_and_deletes_nothing(tmp_path, inbox):
    config = make_config(tmp_path, {"cleanup_source": True, "cleanup_output_after_print": True}, **label_profiles())
    backend = FakeBackend()
    result = process(config, inbox, dry_run=True, backend=backend)
    assert result.ok
    assert backend.jobs == []
    assert len(list(inbox.iterdir())) == 2
    assert not (tmp_path / "out").exists()


def test_dry_run_reports_missing_printer(tmp_path, inbox):
    result = process(make_config(tmp_path, **label_profiles("Nope")), inbox, dry_run=True, backend=FakeBackend())
    assert not result.ok


def test_disabled_profile_skipped(tmp_path, inbox):
    config = make_config(tmp_path, a={"pages": "1"}, b={"pages": "1", "enabled": False})
    result = process(config, inbox)
    assert [p.name for p in result.outputs] == ["order1_a.pdf", "order2_a.pdf"]


def test_output_dir_override(tmp_path, inbox):
    process(make_config(tmp_path, a={"pages": "1"}), inbox, output_dir=tmp_path / "elsewhere")
    assert len(list((tmp_path / "elsewhere").iterdir())) == 2


def test_default_input_path_from_config(tmp_path, inbox):
    config = make_config(tmp_path, input_cfg={"path": str(inbox)}, a={"pages": "1"})
    assert len(process(config).outputs) == 2


def test_single_file_input(tmp_path, inbox):
    assert len(process(make_config(tmp_path, a={"pages": "1"}), inbox / "order2.pdf").outputs) == 1


def test_missing_input_path(tmp_path):
    with pytest.raises(ProcessingError, match="does not exist"):
        process(make_config(tmp_path, a={"pages": "1"}), tmp_path / "nope")


def test_empty_input(tmp_path):
    (tmp_path / "empty").mkdir()
    result = process(make_config(tmp_path, a={"pages": "1"}), tmp_path / "empty")
    assert result.ok and result.sources == []


def test_duplicate_page_selection_is_independent(tmp_path, make_pdf):
    src = make_pdf("doc.pdf", sizes=[(612, 792)])
    config = make_config(tmp_path, a={"pages": [1, 1], "transforms": [{"rotate": {"angle": 90, "pages": [0]}}]})
    (out,) = process(config, src).outputs
    assert pages_of(out) == [(792, 612), (612, 792)]


def test_debug_steps_saved(tmp_path, make_pdf):
    src = make_pdf("doc.pdf")
    process(make_config(tmp_path, a={"pages": "1", "debug": True, "transforms": [{"rotate": 90}]}), src)
    names = sorted(p.name for p in (tmp_path / "out").iterdir())
    assert names == ["doc_a.pdf", "doc_a_step0_selected.pdf", "doc_a_step1_rotate90.pdf"]


def test_keyword_filter(tmp_path, make_pdf):
    d = tmp_path / "in"
    make_pdf("ship.pdf", text=["SHIPPING label"], directory=d)
    make_pdf("other.pdf", text=["invoice"], directory=d)
    config = make_config(
        tmp_path, input_cfg={"filter": {"keywords": ["SHIPPING", "label"], "match": "all"}}, a={"pages": "1"}
    )
    assert [p.name for p in process(config, d).sources] == ["ship.pdf"]


def test_profile_sort_controls_print_order(tmp_path, make_pdf):
    d = tmp_path / "in"
    for i, name in enumerate(["b.pdf", "a.pdf", "c.pdf"]):
        path = make_pdf(name, directory=d)
        os.utime(path, (1000 + i, 1000 + i))
    config = make_config(
        tmp_path,
        input_cfg={"sort": "time_asc"},
        a={"pages": "1", "sort": "name_desc", "print": {"enabled": True, "printer": "Label"}},
    )
    backend = FakeBackend()
    result = process(config, d, backend=backend)
    assert [s.name for s in result.sources] == ["b.pdf", "a.pdf", "c.pdf"]  # processing order: input.sort
    assert [f.name for _, f, _ in backend.jobs] == ["c_a.pdf", "b_a.pdf", "a_a.pdf"]  # print order: profile.sort


def test_find_inputs_and_sort(tmp_path, make_pdf):
    d = tmp_path / "in"
    for name in ("B.pdf", "a.pdf", "skip.txt"):
        make_pdf(name, directory=d)
    files = find_inputs(d)
    assert [f.name for f in files] == ["B.pdf", "a.pdf"]
    assert [f.name for f in sort_files(files, "name_asc")] == ["a.pdf", "B.pdf"]
    assert [f.name for f in sort_files(files, "name_desc")] == ["B.pdf", "a.pdf"]
    assert sort_files(files, None) == files
