"""Tests for pdfmill.transforms module."""

import pytest
from unittest.mock import MagicMock, patch

from pdfmill.transforms import (
    parse_dimension,
    get_page_dimensions,
    is_landscape,
    rotate_page,
    crop_page,
    resize_page,
    render_page,
    detect_page_orientation,
    TransformError,
    UNIT_TO_POINTS,
)


class TestParseDimension:
    """Test dimension string parsing."""

    def test_millimeters(self):
        result = parse_dimension("100mm")
        expected = 100 * UNIT_TO_POINTS["mm"]
        assert abs(result - expected) < 0.01

    def test_inches(self):
        assert parse_dimension("4in") == 288.0  # 4 * 72

    def test_points(self):
        assert parse_dimension("72pt") == 72.0

    def test_centimeters(self):
        result = parse_dimension("2.54cm")
        expected = 2.54 * UNIT_TO_POINTS["cm"]
        assert abs(result - expected) < 0.01

    def test_case_insensitive(self):
        assert parse_dimension("4IN") == 288.0
        assert parse_dimension("100MM") == parse_dimension("100mm")

    def test_with_whitespace(self):
        assert parse_dimension("  4in  ") == 288.0

    def test_decimal_value(self):
        assert parse_dimension("1.5in") == 108.0  # 1.5 * 72

    def test_zero_value(self):
        assert parse_dimension("0in") == 0.0

    def test_empty_string_raises(self):
        with pytest.raises(TransformError, match="Empty"):
            parse_dimension("")

    def test_no_unit_raises(self):
        with pytest.raises(TransformError, match="Invalid dimension"):
            parse_dimension("100")

    def test_invalid_unit_raises(self):
        with pytest.raises(TransformError, match="Invalid dimension"):
            parse_dimension("100px")

    def test_only_unit_raises(self):
        with pytest.raises(TransformError, match="Invalid dimension"):
            parse_dimension("mm")

    def test_negative_value_raises(self):
        with pytest.raises(TransformError, match="Invalid dimension"):
            parse_dimension("-10mm")


class TestGetPageDimensions:
    """Test page dimension extraction."""

    def test_letter_page(self, mock_page):
        width, height = get_page_dimensions(mock_page)
        assert width == 612.0
        assert height == 792.0

    def test_landscape_page(self, mock_landscape_page):
        width, height = get_page_dimensions(mock_landscape_page)
        assert width == 792.0
        assert height == 612.0


class TestIsLandscape:
    """Test landscape detection."""

    def test_portrait_is_not_landscape(self, mock_page):
        assert is_landscape(mock_page) is False

    def test_landscape_is_landscape(self, mock_landscape_page):
        assert is_landscape(mock_landscape_page) is True

    def test_square_is_not_landscape(self):
        page = MagicMock()
        mediabox = MagicMock()
        mediabox.width = 500.0
        mediabox.height = 500.0
        page.mediabox = mediabox
        assert is_landscape(page) is False


class TestRotatePage:
    """Test page rotation.

    Note: rotate_page now performs real geometric rotation using
    add_transformation() instead of just setting the /Rotate flag.
    """

    def test_rotate_90(self, mock_page):
        rotate_page(mock_page, 90)
        mock_page.add_transformation.assert_called_once()
        # Mediabox should be updated to swapped dimensions (portrait -> landscape)
        assert mock_page.mediabox.lower_left == (0, 0)
        assert mock_page.mediabox.upper_right == (792.0, 612.0)

    def test_rotate_180(self, mock_page):
        rotate_page(mock_page, 180)
        mock_page.add_transformation.assert_called_once()
        # Mediabox dimensions stay the same for 180° rotation
        assert mock_page.mediabox.lower_left == (0, 0)
        assert mock_page.mediabox.upper_right == (612.0, 792.0)

    def test_rotate_270(self, mock_page):
        rotate_page(mock_page, 270)
        mock_page.add_transformation.assert_called_once()
        # Mediabox should be updated to swapped dimensions
        assert mock_page.mediabox.lower_left == (0, 0)
        assert mock_page.mediabox.upper_right == (792.0, 612.0)

    def test_rotate_0_no_call(self, mock_page):
        rotate_page(mock_page, 0)
        mock_page.add_transformation.assert_not_called()

    def test_rotate_invalid_angle_raises(self, mock_page):
        with pytest.raises(TransformError, match="must be 0, 90, 180, or 270"):
            rotate_page(mock_page, 45)

    def test_rotate_to_landscape_from_portrait(self, mock_page):
        rotate_page(mock_page, "landscape")
        mock_page.add_transformation.assert_called_once()

    def test_rotate_to_landscape_already_landscape(self, mock_landscape_page):
        rotate_page(mock_landscape_page, "landscape")
        mock_landscape_page.add_transformation.assert_not_called()

    def test_rotate_to_portrait_from_landscape(self, mock_landscape_page):
        rotate_page(mock_landscape_page, "portrait")
        mock_landscape_page.add_transformation.assert_called_once()

    def test_rotate_to_portrait_already_portrait(self, mock_page):
        rotate_page(mock_page, "portrait")
        mock_page.add_transformation.assert_not_called()

    def test_auto_requires_pdf_path(self, mock_page):
        with pytest.raises(TransformError, match="pdf_path and page_num are required"):
            rotate_page(mock_page, "auto")

    def test_auto_requires_page_num(self, mock_page):
        with pytest.raises(TransformError, match="pdf_path and page_num are required"):
            rotate_page(mock_page, "auto", pdf_path="test.pdf")

    def test_auto_with_ocr_no_rotation_needed(self, mock_page):
        with patch("pdfmill.transforms.detect_page_orientation", return_value=0):
            rotate_page(mock_page, "auto", pdf_path="test.pdf", page_num=0)
            mock_page.add_transformation.assert_not_called()

    def test_auto_with_ocr_rotation_detected(self, mock_page):
        with patch("pdfmill.transforms.detect_page_orientation", return_value=90):
            rotate_page(mock_page, "auto", pdf_path="test.pdf", page_num=0)
            mock_page.add_transformation.assert_called_once()

    def test_unknown_orientation_raises(self, mock_page):
        with pytest.raises(TransformError, match="Unknown rotation"):
            rotate_page(mock_page, "diagonal")

    def test_returns_page(self, mock_page):
        result = rotate_page(mock_page, 90)
        assert result is mock_page


class TestCropPage:
    """Test page cropping."""

    def test_crop_updates_mediabox(self, mock_page):
        crop_page(mock_page, (10, 20), (100, 200))
        assert mock_page.mediabox.lower_left == (10, 20)
        assert mock_page.mediabox.upper_right == (100, 200)

    def test_crop_returns_page(self, mock_page):
        result = crop_page(mock_page, (0, 0), (100, 100))
        assert result is mock_page

    def test_crop_with_floats(self, mock_page):
        crop_page(mock_page, (10.5, 20.5), (100.5, 200.5))
        assert mock_page.mediabox.lower_left == (10.5, 20.5)

    def test_crop_invalid_left_greater_than_right(self, mock_page):
        with pytest.raises(TransformError, match="left.*must be less than right"):
            crop_page(mock_page, (100, 20), (50, 200))

    def test_crop_invalid_bottom_greater_than_top(self, mock_page):
        with pytest.raises(TransformError, match="bottom.*must be less than top"):
            crop_page(mock_page, (10, 200), (100, 50))

    def test_crop_invalid_equal_left_right(self, mock_page):
        with pytest.raises(TransformError, match="left.*must be less than right"):
            crop_page(mock_page, (50, 20), (50, 200))

    def test_crop_invalid_equal_bottom_top(self, mock_page):
        with pytest.raises(TransformError, match="bottom.*must be less than top"):
            crop_page(mock_page, (10, 100), (100, 100))


class TestResizePage:
    """Test page resizing."""

    def test_resize_contain_calls_add_transformation(self, mock_page):
        resize_page(mock_page, "4in", "6in", "contain")
        # Contain mode now uses add_transformation for centering
        mock_page.add_transformation.assert_called_once()

    def test_resize_cover_calls_add_transformation(self, mock_page):
        resize_page(mock_page, "4in", "6in", "cover")
        # Cover mode now uses add_transformation for centering
        mock_page.add_transformation.assert_called_once()

    def test_resize_stretch_calls_add_transformation(self, mock_page):
        resize_page(mock_page, "4in", "6in", "stretch")
        mock_page.add_transformation.assert_called_once()

    def test_resize_invalid_fit_raises(self, mock_page):
        with pytest.raises(TransformError, match="fit mode"):
            resize_page(mock_page, "4in", "6in", "invalid")

    def test_resize_updates_mediabox(self, mock_page):
        resize_page(mock_page, "4in", "6in", "contain")
        # After resize, mediabox should be set to target dimensions
        assert mock_page.mediabox.lower_left == (0, 0)
        assert mock_page.mediabox.upper_right == (288.0, 432.0)  # 4in x 6in

    def test_resize_returns_page(self, mock_page):
        result = resize_page(mock_page, "4in", "6in", "contain")
        assert result is mock_page

    def test_resize_with_different_units(self, mock_page):
        # Mix mm and in
        resize_page(mock_page, "100mm", "6in", "contain")
        mock_page.add_transformation.assert_called_once()


class TestResizePageCalculations:
    """Test resize scaling calculations."""

    def test_contain_uses_min_scale(self, mock_page):
        # Letter page: 612x792
        # Target: 306x396 (half size)
        # scale_x = 306/612 = 0.5, scale_y = 396/792 = 0.5
        # With centering, both should use min scale (0.5)
        resize_page(mock_page, "306pt", "396pt", "contain")
        # Verify add_transformation was called
        mock_page.add_transformation.assert_called_once()

    def test_cover_uses_max_scale(self, mock_page):
        # Letter page: 612x792
        # Target: 306x500
        # scale_x = 306/612 = 0.5, scale_y = 500/792 = 0.631
        # cover should use max (0.631)
        resize_page(mock_page, "306pt", "500pt", "cover")
        # Verify add_transformation was called
        mock_page.add_transformation.assert_called_once()

    def test_contain_centers_content(self, mock_page):
        # Letter page: 612x792, Target: 612x792 (same size)
        # scale = 1.0, offset should be (0, 0)
        resize_page(mock_page, "612pt", "792pt", "contain")
        mock_page.add_transformation.assert_called_once()
        # Mediabox should be set correctly
        assert mock_page.mediabox.lower_left == (0, 0)
        assert mock_page.mediabox.upper_right == (612.0, 792.0)


class TestUnitToPoints:
    """Test unit conversion constants."""

    def test_points_factor(self):
        assert UNIT_TO_POINTS["pt"] == 1.0

    def test_inches_factor(self):
        assert UNIT_TO_POINTS["in"] == 72.0

    def test_mm_factor(self):
        # 72 / 25.4 ≈ 2.834
        assert abs(UNIT_TO_POINTS["mm"] - 2.834) < 0.01

    def test_cm_factor(self):
        # 72 / 2.54 ≈ 28.346
        assert abs(UNIT_TO_POINTS["cm"] - 28.346) < 0.01


class TestDetectPageOrientation:
    """Test OCR-based orientation detection."""

    def test_missing_pymupdf_raises(self):
        # Test that missing pymupdf is handled gracefully
        with patch("pdfmill.transforms.detect_page_orientation") as mock_detect:
            mock_detect.side_effect = TransformError("pymupdf is required for auto rotation")
            with pytest.raises(TransformError, match="pymupdf is required"):
                mock_detect("test.pdf", 0)

    def test_missing_tesseract_raises(self):
        # Test that missing Tesseract is handled gracefully
        with patch("pdfmill.transforms.detect_page_orientation") as mock_detect:
            mock_detect.side_effect = TransformError("Tesseract OCR is not installed")
            with pytest.raises(TransformError, match="Tesseract"):
                mock_detect("test.pdf", 0)

    def test_ocr_detection_failure_raises(self):
        # Test that OCR failures are wrapped in TransformError
        with patch("pdfmill.transforms.detect_page_orientation") as mock_detect:
            mock_detect.side_effect = TransformError("OCR orientation detection failed: some error")
            with pytest.raises(TransformError, match="OCR orientation detection failed"):
                mock_detect("test.pdf", 0)

    def test_successful_detection_returns_angle(self):
        # Test that successful detection returns the detected angle
        with patch("pdfmill.transforms.detect_page_orientation") as mock_detect:
            mock_detect.return_value = 90
            result = mock_detect("test.pdf", 0)
            assert result == 90

    def test_no_rotation_needed_returns_zero(self):
        # Test that correctly oriented pages return 0
        with patch("pdfmill.transforms.detect_page_orientation") as mock_detect:
            mock_detect.return_value = 0
            result = mock_detect("test.pdf", 0)
            assert result == 0


class TestRenderPage:
    """Test page rasterization."""

    def test_missing_pdf2image_raises(self):
        """Test that missing pdf2image raises TransformError."""
        mock_page = MagicMock()
        with patch.dict("sys.modules", {"pdf2image": None}):
            with patch("pdfmill.transforms.render_page") as mock_render:
                mock_render.side_effect = TransformError(
                    "pdf2image is required for render transform"
                )
                with pytest.raises(TransformError, match="pdf2image is required"):
                    mock_render(mock_page, 150)

    def test_missing_pillow_raises(self):
        """Test that missing Pillow raises TransformError."""
        mock_page = MagicMock()
        with patch("pdfmill.transforms.render_page") as mock_render:
            mock_render.side_effect = TransformError(
                "Pillow is required for render transform"
            )
            with pytest.raises(TransformError, match="Pillow is required"):
                mock_render(mock_page, 150)

    def test_render_returns_page_object(self):
        """Test that render_page returns a PageObject."""
        mock_page = MagicMock()
        mock_result_page = MagicMock()

        with patch("pdfmill.transforms.render_page") as mock_render:
            mock_render.return_value = mock_result_page
            result = mock_render(mock_page, 300)
            assert result is mock_result_page

    def test_render_default_dpi(self):
        """Test that render_page accepts default DPI."""
        mock_page = MagicMock()
        mock_result_page = MagicMock()

        with patch("pdfmill.transforms.render_page") as mock_render:
            mock_render.return_value = mock_result_page
            result = mock_render(mock_page)
            mock_render.assert_called_once_with(mock_page)

    def test_render_custom_dpi(self):
        """Test that render_page accepts custom DPI."""
        mock_page = MagicMock()
        mock_result_page = MagicMock()

        with patch("pdfmill.transforms.render_page") as mock_render:
            mock_render.return_value = mock_result_page
            result = mock_render(mock_page, dpi=600)
            mock_render.assert_called_once_with(mock_page, dpi=600)

    def test_render_failed_raises(self):
        """Test that render failure raises TransformError."""
        mock_page = MagicMock()
        with patch("pdfmill.transforms.render_page") as mock_render:
            mock_render.side_effect = TransformError("Failed to render page to image")
            with pytest.raises(TransformError, match="Failed to render"):
                mock_render(mock_page, 150)
