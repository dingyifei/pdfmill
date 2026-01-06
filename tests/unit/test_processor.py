"""Tests for pdfmill.processor module."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from pdfmill.processor import (
    get_input_files,
    generate_output_filename,
    apply_transforms,
    process_single_pdf,
    process,
    ProcessingError,
)
from pdfmill.config import (
    Config,
    OutputProfile,
    Transform,
    RotateTransform,
    CropTransform,
    SizeTransform,
    Settings,
    PrintConfig,
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
    """Test transform application."""

    def test_rotate_transform(self):
        pages = [MagicMock(), MagicMock()]
        transforms = [Transform(type="rotate", rotate=RotateTransform(angle=90))]

        with patch("pdfmill.processor.rotate_page") as mock_rotate:
            apply_transforms(pages, transforms)
            assert mock_rotate.call_count == 2

    def test_rotate_specific_pages(self):
        pages = [MagicMock(), MagicMock(), MagicMock()]
        transforms = [Transform(type="rotate", rotate=RotateTransform(angle=90, pages=[0, 2]))]

        with patch("pdfmill.processor.rotate_page") as mock_rotate:
            apply_transforms(pages, transforms)
            assert mock_rotate.call_count == 2

    def test_crop_transform(self):
        pages = [MagicMock(), MagicMock()]
        transforms = [Transform(type="crop", crop=CropTransform(lower_left=(10, 20), upper_right=(100, 200)))]

        with patch("pdfmill.processor.crop_page") as mock_crop:
            apply_transforms(pages, transforms)
            assert mock_crop.call_count == 2

    def test_size_transform(self):
        pages = [MagicMock()]
        transforms = [Transform(type="size", size=SizeTransform(width="4in", height="6in", fit="contain"))]

        with patch("pdfmill.processor.resize_page") as mock_resize:
            apply_transforms(pages, transforms)
            mock_resize.assert_called_once()

    def test_dry_run_no_transform(self, capsys):
        pages = [MagicMock()]
        transforms = [Transform(type="rotate", rotate=RotateTransform(angle=90))]

        with patch("pdfmill.processor.rotate_page") as mock_rotate:
            apply_transforms(pages, transforms, dry_run=True)
            mock_rotate.assert_not_called()

        captured = capsys.readouterr()
        assert "[dry-run]" in captured.out

    def test_multiple_transforms(self):
        pages = [MagicMock()]
        transforms = [
            Transform(type="rotate", rotate=RotateTransform(angle=90)),
            Transform(type="crop", crop=CropTransform()),
        ]

        with patch("pdfmill.processor.rotate_page") as mock_rotate:
            with patch("pdfmill.processor.crop_page") as mock_crop:
                apply_transforms(pages, transforms)
                mock_rotate.assert_called_once()
                mock_crop.assert_called_once()

    def test_returns_pages(self):
        pages = [MagicMock()]
        result = apply_transforms(pages, [])
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

    def test_dry_run_returns_none(self, temp_multi_page_pdf, temp_dir, capsys):
        profile = OutputProfile(pages="last")

        output = process_single_pdf(
            temp_multi_page_pdf,
            "test_profile",
            profile,
            temp_dir,
            dry_run=True,
        )

        assert output is None
        captured = capsys.readouterr()
        assert "[dry-run]" in captured.out

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

    def test_no_files_found(self, temp_dir, capsys):
        config = Config(outputs={"default": OutputProfile(pages="all")})

        process(config, temp_dir, temp_dir)

        captured = capsys.readouterr()
        assert "No PDF files found" in captured.out

    def test_multiple_profiles(self, temp_multi_page_pdf, temp_dir):
        config = Config(outputs={
            "first": OutputProfile(pages="first"),
            "last": OutputProfile(pages="last"),
        })
        output_dir = temp_dir / "output"

        process(config, temp_multi_page_pdf, output_dir)

        outputs = list(output_dir.glob("*.pdf"))
        assert len(outputs) == 2

    def test_on_error_continue(self, temp_pdf, temp_dir, capsys):
        config = Config(
            settings=Settings(on_error="continue"),
            outputs={
                "bad": OutputProfile(pages="10"),  # Will fail
                "good": OutputProfile(pages="1"),  # Will succeed
            }
        )
        output_dir = temp_dir / "output"

        # Should not raise, should continue to good profile
        process(config, temp_pdf, output_dir)

        captured = capsys.readouterr()
        assert "Error" in captured.out

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

    def test_dry_run(self, temp_multi_page_pdf, temp_dir, capsys):
        config = Config(outputs={"default": OutputProfile(pages="all")})
        output_dir = temp_dir / "output"

        process(config, temp_multi_page_pdf, output_dir, dry_run=True)

        captured = capsys.readouterr()
        assert "[dry-run]" in captured.out

        # No actual output should be created (output_dir may not even exist)
        if output_dir.exists():
            outputs = list(output_dir.glob("*.pdf"))
            assert len(outputs) == 0

    def test_print_enabled(self, temp_multi_page_pdf, temp_dir):
        config = Config(outputs={
            "label": OutputProfile(
                pages="last",
                print=PrintConfig(enabled=True, printer="Test Printer"),
            )
        })
        output_dir = temp_dir / "output"

        with patch("pdfmill.processor.print_pdf") as mock_print:
            mock_print.return_value = True
            process(config, temp_multi_page_pdf, output_dir)
            mock_print.assert_called_once()

    def test_print_error_continues(self, temp_multi_page_pdf, temp_dir, capsys):
        from pdfmill.printer import PrinterError

        config = Config(
            settings=Settings(on_error="continue"),
            outputs={
                "label": OutputProfile(
                    pages="last",
                    print=PrintConfig(enabled=True, printer="Fake Printer"),
                )
            }
        )
        output_dir = temp_dir / "output"

        with patch("pdfmill.processor.print_pdf") as mock_print:
            mock_print.side_effect = PrinterError("Print failed")
            process(config, temp_multi_page_pdf, output_dir)

        captured = capsys.readouterr()
        assert "Print error" in captured.out


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
                    print=PrintConfig(enabled=True, printer="Test"),
                )
            }
        )

        with patch("pdfmill.processor.print_pdf") as mock_print:
            mock_print.return_value = True
            process(config, source_pdf, output_dir)

        # Output should be cleaned up
        outputs = list(output_dir.glob("*.pdf"))
        assert len(outputs) == 0
