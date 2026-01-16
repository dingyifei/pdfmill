"""Integration tests for pdfmill pipeline processing."""

import logging

import pytest
from pypdf import PdfReader, PdfWriter

from pdfmill.config import (
    Config,
    CropTransform,
    OutputProfile,
    RotateTransform,
    Settings,
    Transform,
    load_config,
)
from pdfmill.logging_config import setup_logging
from pdfmill.processor import process


@pytest.mark.integration
class TestPipelineIntegration:
    """End-to-end pipeline tests with real PDF processing."""

    def test_extract_last_page(self, temp_multi_page_pdf, temp_dir):
        """Test extracting last page from multi-page PDF."""
        config = Config(outputs={"last_page": OutputProfile(pages="last")})
        output_dir = temp_dir / "output"

        process(config, temp_multi_page_pdf, output_dir)

        outputs = list(output_dir.glob("*.pdf"))
        assert len(outputs) == 1

        reader = PdfReader(str(outputs[0]))
        assert len(reader.pages) == 1

    def test_extract_first_page(self, temp_multi_page_pdf, temp_dir):
        """Test extracting first page from multi-page PDF."""
        config = Config(outputs={"first_page": OutputProfile(pages="first")})
        output_dir = temp_dir / "output"

        process(config, temp_multi_page_pdf, output_dir)

        outputs = list(output_dir.glob("*.pdf"))
        assert len(outputs) == 1

        reader = PdfReader(str(outputs[0]))
        assert len(reader.pages) == 1

    def test_extract_page_range(self, temp_multi_page_pdf, temp_dir):
        """Test extracting a range of pages."""
        config = Config(outputs={"range": OutputProfile(pages="2-4")})
        output_dir = temp_dir / "output"

        process(config, temp_multi_page_pdf, output_dir)

        outputs = list(output_dir.glob("*.pdf"))
        assert len(outputs) == 1
        reader = PdfReader(str(outputs[0]))
        assert len(reader.pages) == 3

    def test_extract_odd_pages(self, temp_multi_page_pdf, temp_dir):
        """Test extracting odd pages (1, 3, 5)."""
        config = Config(outputs={"odd": OutputProfile(pages="odd")})
        output_dir = temp_dir / "output"

        process(config, temp_multi_page_pdf, output_dir)

        outputs = list(output_dir.glob("*.pdf"))
        assert len(outputs) == 1
        reader = PdfReader(str(outputs[0]))
        assert len(reader.pages) == 3  # Pages 1, 3, 5 from 6-page PDF

    def test_process_with_rotation(self, temp_pdf, temp_dir):
        """Test processing with rotation transform."""
        config = Config(outputs={
            "rotated": OutputProfile(
                pages="all",
                transforms=[Transform(type="rotate", rotate=RotateTransform(angle=90))]
            )
        })
        output_dir = temp_dir / "output"

        process(config, temp_pdf, output_dir)

        outputs = list(output_dir.glob("*.pdf"))
        assert len(outputs) == 1
        # Verify the output file is valid
        reader = PdfReader(str(outputs[0]))
        assert len(reader.pages) == 1

    def test_process_with_crop(self, temp_pdf, temp_dir):
        """Test processing with crop transform."""
        config = Config(outputs={
            "cropped": OutputProfile(
                pages="all",
                transforms=[Transform(
                    type="crop",
                    crop=CropTransform(lower_left=(50, 50), upper_right=(300, 400))
                )]
            )
        })
        output_dir = temp_dir / "output"

        process(config, temp_pdf, output_dir)

        outputs = list(output_dir.glob("*.pdf"))
        assert len(outputs) == 1

        reader = PdfReader(str(outputs[0]))
        page = reader.pages[0]
        # Verify crop was applied (mediabox should be at origin with cropped dimensions)
        # The crop translates content so cropped region starts at (0, 0)
        assert float(page.mediabox.lower_left[0]) == 0
        assert float(page.mediabox.lower_left[1]) == 0
        # Cropped size: (300-50) x (400-50) = 250 x 350
        assert float(page.mediabox.upper_right[0]) == 250
        assert float(page.mediabox.upper_right[1]) == 350

    def test_process_multiple_profiles(self, temp_multi_page_pdf, temp_dir):
        """Test processing with multiple output profiles."""
        config = Config(outputs={
            "first": OutputProfile(pages="first"),
            "last": OutputProfile(pages="last"),
            "all": OutputProfile(pages="all"),
        })
        output_dir = temp_dir / "output"

        process(config, temp_multi_page_pdf, output_dir)

        outputs = list(output_dir.glob("*.pdf"))
        assert len(outputs) == 3

        # Verify each output
        output_pages = {}
        for output in outputs:
            reader = PdfReader(str(output))
            output_pages[output.stem] = len(reader.pages)

        # Check that we have outputs with 1, 1, and 6 pages
        page_counts = sorted(output_pages.values())
        assert page_counts == [1, 1, 6]

    def test_process_directory_input(self, temp_dir):
        """Test processing a directory of PDFs."""
        # Create input directory with multiple PDFs
        input_dir = temp_dir / "input"
        input_dir.mkdir()

        for i, name in enumerate(["doc1.pdf", "doc2.pdf", "doc3.pdf"]):
            writer = PdfWriter()
            # Give each PDF a different number of pages
            for _ in range(i + 1):
                writer.add_blank_page(612, 792)
            with open(input_dir / name, "wb") as f:
                writer.write(f)

        output_dir = temp_dir / "output"
        config = Config(outputs={"extracted": OutputProfile(pages="last")})

        process(config, input_dir, output_dir)

        outputs = list(output_dir.glob("*.pdf"))
        assert len(outputs) == 3

        # Each output should have exactly 1 page (last page)
        for output in outputs:
            reader = PdfReader(str(output))
            assert len(reader.pages) == 1

    def test_process_with_prefix_suffix(self, temp_pdf, temp_dir):
        """Test output filename with prefix and suffix."""
        config = Config(outputs={
            "label": OutputProfile(
                pages="all",
                filename_prefix="shipping_",
                filename_suffix="_final",
            )
        })
        output_dir = temp_dir / "output"

        process(config, temp_pdf, output_dir)

        outputs = list(output_dir.glob("*.pdf"))
        assert len(outputs) == 1

        output_name = outputs[0].name
        assert output_name.startswith("shipping_")
        assert "_final_" in output_name

    def test_chained_transforms(self, temp_pdf, temp_dir):
        """Test applying multiple transforms in sequence."""
        config = Config(outputs={
            "processed": OutputProfile(
                pages="all",
                transforms=[
                    Transform(type="rotate", rotate=RotateTransform(angle=90)),
                    Transform(type="crop", crop=CropTransform(
                        lower_left=(10, 10),
                        upper_right=(500, 700)
                    )),
                ]
            )
        })
        output_dir = temp_dir / "output"

        process(config, temp_pdf, output_dir)

        outputs = list(output_dir.glob("*.pdf"))
        assert len(outputs) == 1

        reader = PdfReader(str(outputs[0]))
        assert len(reader.pages) == 1

    def test_process_single_page_from_multipage(self, temp_multi_page_pdf, temp_dir):
        """Test extracting specific single page."""
        config = Config(outputs={"page3": OutputProfile(pages="3")})
        output_dir = temp_dir / "output"

        process(config, temp_multi_page_pdf, output_dir)

        outputs = list(output_dir.glob("*.pdf"))
        assert len(outputs) == 1
        reader = PdfReader(str(outputs[0]))
        assert len(reader.pages) == 1


@pytest.mark.integration
class TestConfigFileIntegration:
    """Test loading and using config files."""

    def test_load_and_process(self, temp_config_file, temp_multi_page_pdf, temp_dir):
        """Test loading config from file and processing."""
        config = load_config(temp_config_file)
        output_dir = temp_dir / "output"

        process(config, temp_multi_page_pdf, output_dir)

        outputs = list(output_dir.glob("*.pdf"))
        assert len(outputs) >= 1

    def test_full_config_processing(self, full_config_file, temp_multi_page_pdf, temp_dir):
        """Test processing with full config including transforms."""
        config = load_config(full_config_file)
        output_dir = temp_dir / "output"

        process(config, temp_multi_page_pdf, output_dir)

        outputs = list(output_dir.glob("*.pdf"))
        assert len(outputs) >= 1


@pytest.mark.integration
class TestErrorHandling:
    """Test error handling in the pipeline."""

    def test_invalid_page_spec_continues(self, temp_pdf, temp_dir, caplog):
        """Test that invalid page spec doesn't crash with on_error=continue."""
        config = Config(
            settings=Settings(on_error="continue"),
            outputs={
                "invalid": OutputProfile(pages="100"),  # Invalid for 1-page PDF
                "valid": OutputProfile(pages="1"),
            }
        )
        output_dir = temp_dir / "output"

        with caplog.at_level(logging.ERROR, logger="pdfmill"):
            setup_logging()
            process(config, temp_pdf, output_dir)

        # Valid profile should still produce output
        outputs = list(output_dir.glob("*.pdf"))
        assert len(outputs) == 1

        assert "Error" in caplog.text

    def test_empty_directory_handled(self, temp_dir, caplog):
        """Test handling of empty input directory."""
        config = Config(outputs={"default": OutputProfile(pages="all")})
        input_dir = temp_dir / "input"
        input_dir.mkdir()
        output_dir = temp_dir / "output"

        with caplog.at_level(logging.INFO, logger="pdfmill"):
            setup_logging()
            process(config, input_dir, output_dir)

        assert "No PDF files found" in caplog.text
