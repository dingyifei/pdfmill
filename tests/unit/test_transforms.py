"""Tests for page transforms. Geometry is checked through page boxes and text positions."""

import io
import shutil

import pytest
from pypdf import PdfReader, PdfWriter

from pdfmill.schema import ConfigError
from pdfmill.transforms import TRANSFORMS, apply_all, parse_transform
from pdfmill.transforms._page import TransformError, clone, normalize, set_box, size

needs_poppler = pytest.mark.skipif(shutil.which("pdftoppm") is None, reason="poppler not installed")
needs_tesseract = pytest.mark.skipif(shutil.which("tesseract") is None, reason="tesseract not installed")


def text_page(width=612, height=792, x=100, y=200, text="MARK"):
    """A page with ``text`` drawn at (x, y)."""
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(width, height))
    c.setFont("Helvetica", 12)
    c.drawString(x, y, text)
    c.showPage()
    c.save()
    buf.seek(0)
    return PdfReader(buf).pages[0]


def roundtrip(page):
    writer = PdfWriter()
    writer.add_page(page)
    buf = io.BytesIO()
    writer.write(buf)
    buf.seek(0)
    return PdfReader(buf).pages[0]


def text_positions(page) -> dict[str, tuple[float, float]]:
    """Map each text string on the page to its (x, y) origin in page space."""
    found = {}

    def mult(m, n):
        return [
            m[0] * n[0] + m[1] * n[2],
            m[0] * n[1] + m[1] * n[3],
            m[2] * n[0] + m[3] * n[2],
            m[2] * n[1] + m[3] * n[3],
            m[4] * n[0] + m[5] * n[2] + n[4],
            m[4] * n[1] + m[5] * n[3] + n[5],
        ]

    def visitor(text, cm, tm, font_dict, font_size):
        if text.strip():
            matrix = mult(tm, cm)
            found[text.strip()] = (round(matrix[4]), round(matrix[5]))

    roundtrip(page).extract_text(visitor_text=visitor)
    return found


def run(page_or_pages, *transform_dicts):
    pages = page_or_pages if isinstance(page_or_pages, list) else [page_or_pages]
    transforms = [parse_transform(t, f"t[{i}]") for i, t in enumerate(transform_dicts)]
    return apply_all(pages, transforms)


def boxes(page):
    return [[round(float(v), 2) for v in getattr(page, b)] for b in ("mediabox", "cropbox", "trimbox")]


def test_registry_has_all_transforms():
    assert set(TRANSFORMS) == {"rotate", "crop", "size", "stamp", "split", "combine", "render"}


class TestNormalize:
    def test_bakes_rotate_flag_into_content(self):
        page = text_page(x=100, y=200)
        page.rotate(90)  # viewer shows it rotated clockwise
        normalize(page)
        assert page.rotation == 0
        assert size(page) == (792, 612)
        # (x, y) on the unrotated page appears at (y, width - x) after a 90 deg clockwise turn
        assert text_positions(page)["MARK"] == (200, 512)

    def test_moves_offset_cropbox_to_origin(self):
        page = text_page(x=100, y=200)
        page.cropbox.lower_left = (50, 100)
        page.cropbox.upper_right = (550, 700)
        normalize(page)
        assert boxes(page) == [[0, 0, 500, 600]] * 3
        assert text_positions(page)["MARK"] == (50, 100)

    def test_set_box_rejects_empty(self):
        with pytest.raises(TransformError):
            set_box(text_page(), 0, 10)

    def test_clone_is_independent(self):
        page = text_page()
        copy = clone(page)
        run(copy, {"rotate": 90})
        assert size(page) == (612, 792)
        assert size(copy) == (792, 612)


class TestRotate:
    @pytest.mark.parametrize(
        "angle, new_size, position",
        [
            (90, (792, 612), (592, 100)),
            (180, (612, 792), (512, 592)),
            (270, (792, 612), (200, 512)),
            (0, (612, 792), (100, 200)),
        ],
    )
    def test_angles(self, angle, new_size, position):
        (page,) = run(text_page(x=100, y=200), {"rotate": angle})
        assert size(page) == new_size
        assert text_positions(page)["MARK"] == position
        assert boxes(page)[0] == boxes(page)[1]

    def test_orientation(self):
        (page,) = run(text_page(), {"rotate": "landscape"})
        assert size(page) == (792, 612)
        (page,) = run(page, {"rotate": "landscape"})  # already landscape: no-op
        assert size(page) == (792, 612)
        (page,) = run(page, {"rotate": "portrait"})
        assert size(page) == (612, 792)

    def test_selected_pages_only(self):
        pages = run([text_page(), text_page(), text_page()], {"rotate": {"angle": 90, "pages": [1, 7]}})
        assert [size(p) for p in pages] == [(612, 792), (792, 612), (612, 792)]

    def test_disabled_transform_skipped(self):
        (page,) = run(text_page(), {"rotate": 90, "enabled": False})
        assert size(page) == (612, 792)

    @needs_poppler
    @needs_tesseract
    @pytest.mark.parametrize("angle", [90, 180, 270])
    def test_auto_rotates_text_upright(self, angle):
        from pdfmill.transforms.rotate import detect_orientation

        lines = [f"The quick brown fox jumps over the lazy dog, line {i}." for i in range(25)]
        from reportlab.pdfgen import canvas

        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=(612, 792))
        c.setFont("Helvetica", 14)
        for i, line in enumerate(lines):
            c.drawString(50, 740 - i * 24, line)
        c.save()
        buf.seek(0)
        (page,) = run(PdfReader(buf).pages[0], {"rotate": angle}, {"rotate": "auto"})
        assert detect_orientation(page) == 0


class TestCropAndSize:
    def test_crop_moves_region_to_origin(self):
        (page,) = run(text_page(x=100, y=200), {"crop": {"lower_left": [50, 150], "upper_right": [300, 400]}})
        assert boxes(page) == [[0, 0, 250, 250]] * 3
        assert text_positions(page)["MARK"] == (50, 50)

    def test_label_pipeline_produces_exact_4x6(self):
        (page,) = run(
            text_page(),
            {"rotate": 90},
            {"crop": {"lower_left": ["90mm", "33mm"], "upper_right": ["190mm", "183mm"]}},
            {"size": {"width": "100mm", "height": "150mm", "fit": "stretch"}},
        )
        assert boxes(page) == [[0, 0, 283.46, 425.2]] * 3
        assert page.rotation == 0

    @pytest.mark.parametrize("fit, expected", [("stretch", (25, 25)), ("contain", (25, 37)), ("cover", (0, 25))])
    def test_fit_modes(self, fit, expected):
        # 200x100 page with text at (50, 25), scaled into a 100x100 box
        page = text_page(width=200, height=100, x=50, y=25)
        (page,) = run(page, {"size": {"width": 100, "height": 100, "fit": fit}})
        assert size(page) == (100, 100)
        assert text_positions(page)["MARK"] == pytest.approx(expected, abs=1)


class TestSplitCombine:
    def test_split_creates_independent_regions(self):
        page = text_page(x=100, y=200, text="LEFT")
        pages = run(
            page,
            {
                "split": {
                    "regions": [
                        {"lower_left": [0, 0], "upper_right": [306, 792]},
                        {"lower_left": [306, 0], "upper_right": [612, 792]},
                    ]
                }
            },
        )
        assert [size(p) for p in pages] == [(306, 792), (306, 792)]
        assert text_positions(pages[0])["LEFT"] == (100, 200)
        assert text_positions(pages[1])["LEFT"] == (-206, 200)

    def test_combine_batches_pages(self):
        pages = [text_page(text=f"P{i}") for i in range(3)]
        out = run(
            pages,
            {
                "combine": {
                    "page_size": ["8.5in", "11in"],
                    "pages_per_output": 2,
                    "layout": [
                        {"page": 0, "position": [0, "5.5in"], "scale": 0.5},
                        {"page": 1, "position": [0, 0], "scale": 0.5},
                    ],
                }
            },
        )
        assert len(out) == 2
        assert boxes(out[0])[0] == [0, 0, 612, 792]
        positions = text_positions(out[0])
        assert positions["P0"] == (50, 496)
        assert positions["P1"] == (50, 100)
        assert set(text_positions(out[1])) == {"P2"}  # short last batch

    def test_combine_same_page_twice(self):
        out = run(
            [text_page(text="A")],
            {
                "combine": {
                    "pages_per_output": 1,
                    "layout": [{"page": 0, "position": [0, 0]}, {"page": 0, "position": [300, 0]}],
                }
            },
        )
        text = out[0].extract_text()
        assert text.count("A") == 2


class TestStamp:
    def test_page_numbers(self):
        pages = run(
            [text_page(), text_page()], {"stamp": {"text": "{page}/{total}", "position": "bottom-left", "margin": 10}}
        )
        assert text_positions(pages[0])["1/2"] == (10, 10)
        assert "2/2" in text_positions(pages[1])

    def test_custom_position_and_color(self):
        (page,) = run(
            text_page(), {"stamp": {"text": "X", "position": "custom", "x": "1in", "y": 36, "font_color": "#00ff00"}}
        )
        assert text_positions(page)["X"] == (72, 36)

    def test_format_text(self):
        from datetime import datetime

        from pdfmill.transforms.stamp import format_text

        now = datetime(2026, 1, 2, 3, 4, 5)
        assert (
            format_text("{page}/{total} {date} {time} {datetime}", 1, 3, "%d.%m", now)
            == "1/3 2026-01-02 03:04:05 02.01"
        )

    @pytest.mark.parametrize(
        "opts, message", [({"font_color": "notacolor"}, "Unknown color"), ({"font_color": "#zz"}, "hex color")]
    )
    def test_bad_color(self, opts, message):
        with pytest.raises(TransformError, match=message):
            run(text_page(), {"stamp": {"text": "x", **opts}})

    def test_bad_font(self):
        with pytest.raises(TransformError, match="Unknown font"):
            run(text_page(), {"stamp": {"text": "x", "font_name": "Comic"}})


class TestRender:
    @needs_poppler
    def test_render_keeps_size(self):
        (page,) = run(text_page(width=288, height=432), {"render": 72})
        assert boxes(page)[0] == [0, 0, 288, 432]
        assert "/XObject" in page["/Resources"]


class TestDebugOutput:
    def test_saves_each_step(self, tmp_path):
        transforms = [parse_transform({"rotate": 90}, "t"), parse_transform({"rotate": 90, "enabled": False}, "t")]
        apply_all([text_page()], transforms, debug_prefix=tmp_path / "doc_label")
        assert sorted(p.name for p in tmp_path.iterdir()) == [
            "doc_label_step0_selected.pdf",
            "doc_label_step1_rotate90.pdf",
        ]


def test_parse_transform_error_has_path():
    with pytest.raises(ConfigError, match=r"outputs.x.transforms\[0\].crop"):
        parse_transform({"crop": {"lower_left": [0, 0]}}, "outputs.x.transforms[0]")
