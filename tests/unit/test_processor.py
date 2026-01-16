"""Tests for pdfmill.processor module."""

import logging
from unittest.mock import MagicMock, patch

import pytest

from pdfmill.config import (
    Config,
    CropTransform,
    OutputProfile,
    PrintConfig,
    PrintTarget,
    RenderTransform,
    RotateTransform,
    Settings,
    SizeTransform,
    SortOrder,
    Transform,
)
from pdfmill.logging_config import setup_logging
from pdfmill.pipeline import TransformExecutor
from pdfmill.processor import (
    ProcessingError,
    generate_output_filename,
    get_input_files,
    process,
    process_single_pdf,
)


class TestGetInputFiles:
    """Test input file discovery."""

    def test_single_file(self, temp_pdf):
        files = get_input_files(temp_pdf)
        assert files == [temp_pdf]

    def test_directory_with_pdfs(self, temp_dir):
        # Create multiple PDFs
        for name in ["a.pdf", "b.pdf", "c.pdf"]:
            (temp_dir / name).touch()

        files = get_input_files(temp_dir, "*.pdf")
        assert len(files) == 3
        assert files == sorted(files)  # Should be sorted

    def test_empty_directory(self, temp_dir):
        files = get_input_files(temp_dir, "*.pdf")
        assert files == []

    def test_nonexistent_path_raises(self, temp_dir):
        with pytest.raises(ProcessingError, match="does not exist"):
            get_input_files(temp_dir / "nonexistent")

    def test_custom_pattern(self, temp_dir):
        (temp_dir / "test.pdf").touch()
        (temp_dir / "test.txt").touch()
        (temp_dir / "other.pdf").touch()

        files = get_input_files(temp_dir, "test.*")
        assert len(files) == 2

    def test_glob_pattern(self, temp_dir):
        (temp_dir / "doc1.pdf").touch()
        (temp_dir / "doc2.pdf").touch()
        (temp_dir / "image.pdf").touch()

        files = get_input_files(temp_dir, "doc*.pdf")
        assert len(files) == 2


class TestGenerateOutputFilename:
    """Test output filename generation."""

    def test_basic(self):
        name = generate_output_filename("source.pdf", "profile")
        assert name == "source_profile.pdf"

    def test_with_prefix(self):
        name = generate_output_filename("source.pdf", "profile", prefix="pre_")
        assert name == "pre_source_profile.pdf"

    def test_with_suffix(self):
        name = generate_output_filename("source.pdf", "profile", suffix="_suf")
        assert name == "source_suf_profile.pdf"

    def test_with_both_prefix_and_suffix(self):
        name = generate_output_filename("source.pdf", "profile", "pre_", "_suf")
        assert name == "pre_source_suf_profile.pdf"

    def test_preserves_stem_not_extension(self):
        name = generate_output_filename("document.pdf", "label")
        assert name == "document_label.pdf"
        assert name.count(".pdf") == 1

    def test_complex_filename(self):
        name = generate_output_filename("my.document.pdf", "output")
        assert name == "my.document_output.pdf"


class TestApplyTransforms:
    """Test transform application via TransformExecutor."""

    def test_rotate_transform(self):
        pages = [MagicMock(), MagicMock()]
        transforms = [Transform(type="rotate", rotate=RotateTransform(angle=90))]

        mock_handler = MagicMock()
        mock_handler.apply.return_value = MagicMock(pages=pages)
        mock_handler.describe.return_value = "rotate90"

        executor = TransformExecutor()
        with patch("pdfmill.pipeline.transforms.get_transform", return_value=mock_handler):
            executor.apply(pages, transforms)
            mock_handler.apply.assert_called_once()

    def test_rotate_specific_pages(self):
        pages = [MagicMock(), MagicMock(), MagicMock()]
        transforms = [Transform(type="rotate", rotate=RotateTransform(angle=90, pages=[0, 2]))]

        mock_handler = MagicMock()
        mock_handler.apply.return_value = MagicMock(pages=pages)
        mock_handler.describe.return_value = "rotate90"

        executor = TransformExecutor()
        with patch("pdfmill.pipeline.transforms.get_transform", return_value=mock_handler):
            executor.apply(pages, transforms)
            mock_handler.apply.assert_called_once()

    def test_crop_transform(self):
        pages = [MagicMock(), MagicMock()]
        transforms = [Transform(type="crop", crop=CropTransform(lower_left=(10, 20), upper_right=(100, 200)))]

        mock_handler = MagicMock()
        mock_handler.apply.return_value = MagicMock(pages=pages)
        mock_handler.describe.return_value = "crop"

        executor = TransformExecutor()
        with patch("pdfmill.pipeline.transforms.get_transform", return_value=mock_handler):
            executor.apply(pages, transforms)
            mock_handler.apply.assert_called_once()

    def test_size_transform(self):
        pages = [MagicMock()]
        transforms = [Transform(type="size", size=SizeTransform(width="4in", height="6in", fit="contain"))]

        mock_handler = MagicMock()
        mock_handler.apply.return_value = MagicMock(pages=pages)
        mock_handler.describe.return_value = "size_contain"

        executor = TransformExecutor()
        with patch("pdfmill.pipeline.transforms.get_transform", return_value=mock_handler):
            executor.apply(pages, transforms)
            mock_handler.apply.assert_called_once()

    def test_render_transform(self):
        pages = [MagicMock(), MagicMock()]
        transforms = [Transform(type="render", render=RenderTransform(dpi=300))]

        new_pages = [MagicMock(), MagicMock()]
        mock_handler = MagicMock()
        mock_handler.apply.return_value = MagicMock(pages=new_pages)
        mock_handler.describe.return_value = "render_300dpi"

        executor = TransformExecutor()
        with patch("pdfmill.pipeline.transforms.get_transform", return_value=mock_handler):
            executor.apply(pages, transforms)
            mock_handler.apply.assert_called_once()

    def test_render_transform_replaces_pages(self):
        original_pages = [MagicMock(), MagicMock()]
        new_page_1 = MagicMock()
        new_page_2 = MagicMock()
        transforms = [Transform(type="render", render=RenderTransform(dpi=150))]

        mock_handler = MagicMock()
        mock_handler.apply.return_value = MagicMock(pages=[new_page_1, new_page_2])
        mock_handler.describe.return_value = "render_150dpi"

        executor = TransformExecutor()
        with patch("pdfmill.pipeline.transforms.get_transform", return_value=mock_handler):
            result = executor.apply(original_pages, transforms)
            # Handler returns new pages, so they should be replaced
            assert result[0] is new_page_1
            assert result[1] is new_page_2

    def test_render_dry_run(self, caplog):
        pages = [MagicMock()]
        transforms = [Transform(type="render", render=RenderTransform(dpi=300))]

        mock_handler = MagicMock()
        mock_handler.describe.return_value = "render_300dpi"

        executor = TransformExecutor()
        with caplog.at_level(logging.INFO, logger="pdfmill"):
            setup_logging()
            with patch("pdfmill.pipeline.transforms.get_transform", return_value=mock_handler):
                executor.apply(pages, transforms, dry_run=True)
                mock_handler.apply.assert_not_called()

        assert "[dry-run]" in caplog.text
        assert "render_300dpi" in caplog.text

    def test_dry_run_no_transform(self, caplog):
        pages = [MagicMock()]
        transforms = [Transform(type="rotate", rotate=RotateTransform(angle=90))]

        mock_handler = MagicMock()
        mock_handler.describe.return_value = "rotate90"

        executor = TransformExecutor()
        with caplog.at_level(logging.INFO, logger="pdfmill"):
            setup_logging()
            with patch("pdfmill.pipeline.transforms.get_transform", return_value=mock_handler):
                executor.apply(pages, transforms, dry_run=True)
                mock_handler.apply.assert_not_called()

        assert "[dry-run]" in caplog.text

    def test_multiple_transforms(self):
        pages = [MagicMock()]
        transforms = [
            Transform(type="rotate", rotate=RotateTransform(angle=90)),
            Transform(type="crop", crop=CropTransform()),
        ]

        mock_handler = MagicMock()
        mock_handler.apply.return_value = MagicMock(pages=pages)
        mock_handler.describe.return_value = "transform"

        executor = TransformExecutor()
        with patch("pdfmill.pipeline.transforms.get_transform", return_value=mock_handler):
            executor.apply(pages, transforms)
            # Two transforms, so apply should be called twice
            assert mock_handler.apply.call_count == 2

    def test_returns_pages(self):
        pages = [MagicMock()]
        executor = TransformExecutor()
        result = executor.apply(pages, [])
        assert result is pages


class TestProcessSinglePdf:
    """Test single PDF processing."""

    def test_creates_output(self, temp_multi_page_pdf, temp_dir):
        profile = OutputProfile(pages="last")

        output = process_single_pdf(
            temp_multi_page_pdf,
            "test_profile",
            profile,
            temp_dir,
        )

        assert output is not None
        assert output.exists()
        assert "test_profile" in output.name

    def test_dry_run_returns_none(self, temp_multi_page_pdf, temp_dir, caplog):
        profile = OutputProfile(pages="last")

        with caplog.at_level(logging.INFO, logger="pdfmill"):
            setup_logging()
            output = process_single_pdf(
                temp_multi_page_pdf,
                "test_profile",
                profile,
                temp_dir,
                dry_run=True,
            )

        assert output is None
        assert "[dry-run]" in caplog.text

    def test_output_dir_created(self, temp_multi_page_pdf, temp_dir):
        output_subdir = temp_dir / "subdir" / "nested"
        profile = OutputProfile(pages="first")

        output = process_single_pdf(
            temp_multi_page_pdf,
            "profile",
            profile,
            output_subdir,
        )

        assert output_subdir.exists()
        assert output.exists()

    def test_filename_prefix_suffix(self, temp_multi_page_pdf, temp_dir):
        profile = OutputProfile(
            pages="all",
            filename_prefix="pre_",
            filename_suffix="_suf",
        )

        output = process_single_pdf(
            temp_multi_page_pdf,
            "profile",
            profile,
            temp_dir,
        )

        assert output.name.startswith("pre_")
        assert "_suf_" in output.name

    def test_page_selection_error_raises(self, temp_pdf, temp_dir):
        # Single page PDF, select page 10
        profile = OutputProfile(pages="10")

        with pytest.raises(ProcessingError, match="Page selection"):
            process_single_pdf(temp_pdf, "profile", profile, temp_dir)

    def test_extracts_correct_pages(self, temp_multi_page_pdf, temp_dir):
        from pypdf import PdfReader

        profile = OutputProfile(pages="1-3")

        output = process_single_pdf(
            temp_multi_page_pdf,
            "profile",
            profile,
            temp_dir,
        )

        reader = PdfReader(str(output))
        assert len(reader.pages) == 3


class TestProcess:
    """Test full pipeline processing."""

    def test_processes_single_file(self, temp_multi_page_pdf, temp_dir, capsys):
        config = Config(outputs={"default": OutputProfile(pages="all")})
        output_dir = temp_dir / "output"

        process(config, temp_multi_page_pdf, output_dir)

        outputs = list(output_dir.glob("*.pdf"))
        assert len(outputs) == 1

    def test_processes_directory(self, temp_dir, capsys):
        from pypdf import PdfWriter

        # Create input directory with PDFs
        input_dir = temp_dir / "input"
        input_dir.mkdir()
        for name in ["doc1.pdf", "doc2.pdf"]:
            writer = PdfWriter()
            writer.add_blank_page(612, 792)
            with open(input_dir / name, "wb") as f:
                writer.write(f)

        output_dir = temp_dir / "output"
        config = Config(outputs={"extracted": OutputProfile(pages="all")})

        process(config, input_dir, output_dir)

        outputs = list(output_dir.glob("*.pdf"))
        assert len(outputs) == 2

    def test_no_files_found(self, temp_dir, caplog):
        config = Config(outputs={"default": OutputProfile(pages="all")})

        with caplog.at_level(logging.INFO, logger="pdfmill"):
            setup_logging()
            process(config, temp_dir, temp_dir)

        assert "No PDF files found" in caplog.text

    def test_multiple_profiles(self, temp_multi_page_pdf, temp_dir):
        config = Config(outputs={
            "first": OutputProfile(pages="first"),
            "last": OutputProfile(pages="last"),
        })
        output_dir = temp_dir / "output"

        process(config, temp_multi_page_pdf, output_dir)

        outputs = list(output_dir.glob("*.pdf"))
        assert len(outputs) == 2

    def test_on_error_continue(self, temp_pdf, temp_dir, caplog):
        config = Config(
            settings=Settings(on_error="continue"),
            outputs={
                "bad": OutputProfile(pages="10"),  # Will fail
                "good": OutputProfile(pages="1"),  # Will succeed
            }
        )
        output_dir = temp_dir / "output"

        # Should not raise, should continue to good profile
        with caplog.at_level(logging.ERROR, logger="pdfmill"):
            setup_logging()
            process(config, temp_pdf, output_dir)

        assert "Error" in caplog.text

        # Good profile should still produce output
        outputs = list(output_dir.glob("*.pdf"))
        assert len(outputs) == 1

    def test_on_error_stop(self, temp_pdf, temp_dir):
        config = Config(
            settings=Settings(on_error="stop"),
            outputs={"bad": OutputProfile(pages="10")}  # Will fail
        )

        with pytest.raises(ProcessingError):
            process(config, temp_pdf, temp_dir)

    def test_dry_run(self, temp_multi_page_pdf, temp_dir, caplog):
        config = Config(outputs={"default": OutputProfile(pages="all")})
        output_dir = temp_dir / "output"

        with caplog.at_level(logging.INFO, logger="pdfmill"):
            setup_logging()
            process(config, temp_multi_page_pdf, output_dir, dry_run=True)

        assert "[dry-run]" in caplog.text

        # No actual output should be created (output_dir may not even exist)
        if output_dir.exists():
            outputs = list(output_dir.glob("*.pdf"))
            assert len(outputs) == 0

    def test_print_enabled(self, temp_multi_page_pdf, temp_dir):
        config = Config(outputs={
            "label": OutputProfile(
                pages="last",
                print=PrintConfig(
                    enabled=True,
                    targets={"default": PrintTarget(printer="Test Printer")}
                ),
            )
        })
        output_dir = temp_dir / "output"

        with patch("pdfmill.pipeline.printing.print_pdf") as mock_print:
            mock_print.return_value = True
            process(config, temp_multi_page_pdf, output_dir)
            mock_print.assert_called_once()

    def test_print_error_continues(self, temp_multi_page_pdf, temp_dir, caplog):
        from pdfmill.printer import PrinterError

        config = Config(
            settings=Settings(on_error="continue"),
            outputs={
                "label": OutputProfile(
                    pages="last",
                    print=PrintConfig(
                        enabled=True,
                        targets={"default": PrintTarget(printer="Fake Printer")}
                    ),
                )
            }
        )
        output_dir = temp_dir / "output"

        with caplog.at_level(logging.ERROR, logger="pdfmill"):
            setup_logging()
            with patch("pdfmill.pipeline.printing.print_pdf") as mock_print:
                mock_print.side_effect = PrinterError("Print failed")
                process(config, temp_multi_page_pdf, output_dir)

        assert "Print error" in caplog.text


class TestCleanup:
    """Test cleanup functionality."""

    def test_cleanup_source(self, temp_dir):
        from pypdf import PdfWriter

        # Create source PDF
        source_pdf = temp_dir / "source.pdf"
        writer = PdfWriter()
        writer.add_blank_page(612, 792)
        with open(source_pdf, "wb") as f:
            writer.write(f)

        output_dir = temp_dir / "output"
        config = Config(
            settings=Settings(cleanup_source=True),
            outputs={"default": OutputProfile(pages="all")}
        )

        process(config, source_pdf, output_dir)

        assert not source_pdf.exists()

    def test_cleanup_output_after_print(self, temp_dir):
        from pypdf import PdfWriter

        input_dir = temp_dir / "input"
        input_dir.mkdir()
        source_pdf = input_dir / "source.pdf"
        writer = PdfWriter()
        writer.add_blank_page(612, 792)
        with open(source_pdf, "wb") as f:
            writer.write(f)

        output_dir = temp_dir / "output"
        config = Config(
            settings=Settings(cleanup_output_after_print=True),
            outputs={
                "label": OutputProfile(
                    pages="all",
                    print=PrintConfig(
                        enabled=True,
                        targets={"default": PrintTarget(printer="Test")}
                    ),
                )
            }
        )

        with patch("pdfmill.pipeline.printing.print_pdf") as mock_print:
            mock_print.return_value = True
            process(config, source_pdf, output_dir)

        # Output should be cleaned up
        outputs = list(output_dir.glob("*.pdf"))
        assert len(outputs) == 0


class TestSortFiles:
    """Test file sorting functionality."""

    def test_sort_name_asc(self, temp_dir):
        from pypdf import PdfWriter

        from pdfmill.processor import sort_files

        # Create files with specific names
        for name in ["charlie.pdf", "alpha.pdf", "bravo.pdf"]:
            pdf = temp_dir / name
            writer = PdfWriter()
            writer.add_blank_page(612, 792)
            with open(pdf, "wb") as f:
                writer.write(f)

        files = list(temp_dir.glob("*.pdf"))
        sorted_files = sort_files(files, SortOrder.NAME_ASC)

        assert [f.name for f in sorted_files] == ["alpha.pdf", "bravo.pdf", "charlie.pdf"]

    def test_sort_name_desc(self, temp_dir):
        from pypdf import PdfWriter

        from pdfmill.processor import sort_files

        for name in ["alpha.pdf", "charlie.pdf", "bravo.pdf"]:
            pdf = temp_dir / name
            writer = PdfWriter()
            writer.add_blank_page(612, 792)
            with open(pdf, "wb") as f:
                writer.write(f)

        files = list(temp_dir.glob("*.pdf"))
        sorted_files = sort_files(files, SortOrder.NAME_DESC)

        assert [f.name for f in sorted_files] == ["charlie.pdf", "bravo.pdf", "alpha.pdf"]

    def test_sort_time_asc(self, temp_dir):
        import os

        from pypdf import PdfWriter

        from pdfmill.processor import sort_files

        # Create files with different mtimes
        for i, name in enumerate(["first.pdf", "second.pdf", "third.pdf"]):
            pdf = temp_dir / name
            writer = PdfWriter()
            writer.add_blank_page(612, 792)
            with open(pdf, "wb") as f:
                writer.write(f)
            # Set modification time (older first)
            os.utime(pdf, (1000000 + i * 1000, 1000000 + i * 1000))

        files = list(temp_dir.glob("*.pdf"))
        sorted_files = sort_files(files, SortOrder.TIME_ASC)

        assert [f.name for f in sorted_files] == ["first.pdf", "second.pdf", "third.pdf"]

    def test_sort_with_enum(self, temp_dir):
        """Test that sort_files works with SortOrder enum."""
        from pdfmill.processor import sort_files

        # Create test files
        for name in ["a.pdf", "b.pdf", "c.pdf"]:
            (temp_dir / name).touch()

        files = list(temp_dir.glob("*.pdf"))
        sorted_files = sort_files(files, SortOrder.NAME_ASC)
        assert [f.name for f in sorted_files] == ["a.pdf", "b.pdf", "c.pdf"]

        sorted_files = sort_files(files, SortOrder.NAME_DESC)
        assert [f.name for f in sorted_files] == ["c.pdf", "b.pdf", "a.pdf"]


class TestSplitPagesByWeight:
    """Test page splitting across printer targets."""

    def test_split_two_printers_equal_weight(self, temp_dir):
        from pypdf import PdfReader, PdfWriter

        from pdfmill.pipeline import PrintPipeline

        # Create 10-page PDF
        pdf_path = temp_dir / "source.pdf"
        writer = PdfWriter()
        for _ in range(10):
            writer.add_blank_page(612, 792)
        with open(pdf_path, "wb") as f:
            writer.write(f)

        targets = {
            "printer_a": PrintTarget(printer="A", weight=50),
            "printer_b": PrintTarget(printer="B", weight=50),
        }

        pipeline = PrintPipeline()
        result = pipeline.split_pages_by_weight(pdf_path, targets, temp_dir, "test")

        assert len(result) == 2
        # Each should get 5 pages
        reader_a = PdfReader(str(result["printer_a"]))
        reader_b = PdfReader(str(result["printer_b"]))
        assert len(reader_a.pages) == 5
        assert len(reader_b.pages) == 5

    def test_split_unequal_weight(self, temp_dir):
        from pypdf import PdfReader, PdfWriter

        from pdfmill.pipeline import PrintPipeline

        # Create 10-page PDF
        pdf_path = temp_dir / "source.pdf"
        writer = PdfWriter()
        for _ in range(10):
            writer.add_blank_page(612, 792)
        with open(pdf_path, "wb") as f:
            writer.write(f)

        targets = {
            "fast": PrintTarget(printer="Fast", weight=100),
            "slow": PrintTarget(printer="Slow", weight=50),
        }

        pipeline = PrintPipeline()
        result = pipeline.split_pages_by_weight(pdf_path, targets, temp_dir, "test")

        # Fast (100/150 = 67%) gets ~7 pages, slow gets the rest
        reader_fast = PdfReader(str(result["fast"]))
        reader_slow = PdfReader(str(result["slow"]))
        assert len(reader_fast.pages) == 7
        assert len(reader_slow.pages) == 3

    def test_split_zero_weight_skipped(self, temp_dir):
        from pypdf import PdfWriter

        from pdfmill.pipeline import PrintPipeline

        pdf_path = temp_dir / "source.pdf"
        writer = PdfWriter()
        for _ in range(10):
            writer.add_blank_page(612, 792)
        with open(pdf_path, "wb") as f:
            writer.write(f)

        targets = {
            "active": PrintTarget(printer="Active", weight=100),
            "inactive": PrintTarget(printer="Inactive", weight=0),
        }

        pipeline = PrintPipeline()
        result = pipeline.split_pages_by_weight(pdf_path, targets, temp_dir, "test")

        assert "active" in result
        assert "inactive" not in result

    def test_split_single_page(self, temp_dir):
        from pypdf import PdfReader, PdfWriter

        from pdfmill.pipeline import PrintPipeline

        pdf_path = temp_dir / "source.pdf"
        writer = PdfWriter()
        writer.add_blank_page(612, 792)
        with open(pdf_path, "wb") as f:
            writer.write(f)

        targets = {
            "fast": PrintTarget(printer="Fast", weight=100),
            "slow": PrintTarget(printer="Slow", weight=50),
        }

        pipeline = PrintPipeline()
        result = pipeline.split_pages_by_weight(pdf_path, targets, temp_dir, "test")

        # Single page goes to highest weight
        assert "fast" in result
        reader = PdfReader(str(result["fast"]))
        assert len(reader.pages) == 1


class TestMultiPrinterIntegration:
    """Integration tests for multi-printer distribution."""

    def test_multi_target_copy_distribution(self, temp_multi_page_pdf, temp_dir):
        """Test that each target receives copies."""
        config = Config(outputs={
            "label": OutputProfile(
                pages="last",
                print=PrintConfig(
                    enabled=True,
                    targets={
                        "archive": PrintTarget(printer="Archive", copies=2),
                        "customer": PrintTarget(printer="Customer", copies=1),
                    }
                ),
            )
        })
        output_dir = temp_dir / "output"

        with patch("pdfmill.pipeline.printing.print_pdf") as mock_print:
            mock_print.return_value = True
            process(config, temp_multi_page_pdf, output_dir)

            # Should be called twice (once per target)
            assert mock_print.call_count == 2

    def test_sort_conflict_raises_error(self, temp_multi_page_pdf, temp_dir):
        """Test that having both input.sort and profile.sort raises error."""
        from pdfmill.config import ConfigError, InputConfig

        config = Config(
            input=InputConfig(sort=SortOrder.NAME_ASC),
            outputs={
                "label": OutputProfile(
                    pages="all",
                    sort=SortOrder.TIME_DESC,  # Conflicts with input.sort
                )
            }
        )
        output_dir = temp_dir / "output"

        with pytest.raises(ConfigError, match="Sort specified in both"):
            process(config, temp_multi_page_pdf, output_dir)


class TestEnabledField:
    """Test enabled field for profiles and transforms."""

    def test_disabled_transform_skipped(self):
        """Test that disabled transforms are not applied."""
        pages = [MagicMock(), MagicMock()]
        transforms = [
            Transform(type="rotate", rotate=RotateTransform(angle=90), enabled=True),
            Transform(type="rotate", rotate=RotateTransform(angle=180), enabled=False),
        ]

        mock_handler = MagicMock()
        mock_handler.apply.return_value = MagicMock(pages=pages)
        mock_handler.describe.return_value = "rotate90"

        executor = TransformExecutor()
        with patch("pdfmill.pipeline.transforms.get_transform", return_value=mock_handler):
            executor.apply(pages, transforms)
            # Only the enabled transform should be called
            mock_handler.apply.assert_called_once()

    def test_all_disabled_transforms_skipped(self):
        """Test that all disabled transforms are skipped."""
        pages = [MagicMock()]
        transforms = [
            Transform(type="rotate", rotate=RotateTransform(angle=90), enabled=False),
            Transform(type="crop", crop=CropTransform(), enabled=False),
        ]

        mock_handler = MagicMock()
        mock_handler.apply.return_value = MagicMock(pages=pages)
        mock_handler.describe.return_value = "transform"

        executor = TransformExecutor()
        with patch("pdfmill.pipeline.transforms.get_transform", return_value=mock_handler):
            executor.apply(pages, transforms)
            mock_handler.apply.assert_not_called()

    def test_mixed_enabled_disabled_transforms(self):
        """Test processing with mix of enabled and disabled transforms."""
        pages = [MagicMock()]
        transforms = [
            Transform(type="rotate", rotate=RotateTransform(angle=90), enabled=True),
            Transform(type="crop", crop=CropTransform(), enabled=False),
            Transform(type="size", size=SizeTransform(width="4in", height="6in"), enabled=True),
        ]

        mock_handler = MagicMock()
        mock_handler.apply.return_value = MagicMock(pages=pages)
        mock_handler.describe.return_value = "transform"

        executor = TransformExecutor()
        with patch("pdfmill.pipeline.transforms.get_transform", return_value=mock_handler):
            executor.apply(pages, transforms)
            # 2 enabled transforms
            assert mock_handler.apply.call_count == 2

    def test_disabled_profile_skipped(self, temp_multi_page_pdf, temp_dir, caplog):
        """Test that disabled profiles are skipped."""
        config = Config(outputs={
            "enabled": OutputProfile(pages="all", enabled=True),
            "disabled": OutputProfile(pages="all", enabled=False),
        })
        output_dir = temp_dir / "output"

        with caplog.at_level(logging.DEBUG, logger="pdfmill"):
            setup_logging(verbosity=2)
            process(config, temp_multi_page_pdf, output_dir)

        # Only one output should be created (from enabled profile)
        outputs = list(output_dir.glob("*.pdf"))
        assert len(outputs) == 1
        assert "enabled" in outputs[0].name

        # Check log message
        assert "Skipping disabled profile: disabled" in caplog.text

    def test_all_disabled_profiles_skipped(self, temp_multi_page_pdf, temp_dir, caplog):
        """Test that all disabled profiles are skipped."""
        config = Config(outputs={
            "disabled1": OutputProfile(pages="all", enabled=False),
            "disabled2": OutputProfile(pages="last", enabled=False),
        })
        output_dir = temp_dir / "output"

        with caplog.at_level(logging.DEBUG, logger="pdfmill"):
            setup_logging(verbosity=2)
            process(config, temp_multi_page_pdf, output_dir)

        # No outputs should be created
        if output_dir.exists():
            outputs = list(output_dir.glob("*.pdf"))
            assert len(outputs) == 0

        assert "Skipping disabled profile: disabled1" in caplog.text
        assert "Skipping disabled profile: disabled2" in caplog.text

    def test_disabled_profile_with_print_enabled_no_print(self, temp_multi_page_pdf, temp_dir):
        """Test that disabled profile doesn't print even if print.enabled is True."""
        config = Config(outputs={
            "disabled": OutputProfile(
                pages="all",
                enabled=False,
                print=PrintConfig(
                    enabled=True,
                    targets={"default": PrintTarget(printer="Test")}
                ),
            ),
        })
        output_dir = temp_dir / "output"

        with patch("pdfmill.pipeline.printing.print_pdf") as mock_print:
            process(config, temp_multi_page_pdf, output_dir)
            mock_print.assert_not_called()

    def test_enabled_profile_default_value(self, temp_multi_page_pdf, temp_dir):
        """Test that profile without explicit enabled defaults to True."""
        config = Config(outputs={
            "default_enabled": OutputProfile(pages="all"),  # No enabled field
        })
        output_dir = temp_dir / "output"

        process(config, temp_multi_page_pdf, output_dir)

        outputs = list(output_dir.glob("*.pdf"))
        assert len(outputs) == 1

    def test_transform_enabled_default_value(self):
        """Test that transform without explicit enabled defaults to True."""
        pages = [MagicMock()]
        transforms = [
            Transform(type="rotate", rotate=RotateTransform(angle=90)),  # No enabled field
        ]

        mock_handler = MagicMock()
        mock_handler.apply.return_value = MagicMock(pages=pages)
        mock_handler.describe.return_value = "rotate90"

        executor = TransformExecutor()
        with patch("pdfmill.pipeline.transforms.get_transform", return_value=mock_handler):
            executor.apply(pages, transforms)
            mock_handler.apply.assert_called_once()
