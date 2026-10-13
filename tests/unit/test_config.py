"""Tests for config loading and validation."""

from pathlib import Path

import pytest

from pdfmill.config import ConfigError, load_config, parse_config
from pdfmill.units import to_points

REPO = Path(__file__).resolve().parents[2]


def minimal(**profile):
    return {"outputs": {"p": {"pages": "all", **profile}}}


@pytest.mark.parametrize("name", ["label_packing", "lecture_a", "multi_printer", "six_page"])
def test_example_configs_load(name):
    config = load_config(REPO / "configs" / f"{name}.yaml")
    assert config.outputs


def test_defaults():
    config = parse_config(minimal())
    profile = config.outputs["p"]
    assert config.settings.on_error == "continue"
    assert config.settings.print_backend == "auto"
    assert config.input.path == Path("input")
    assert config.input.pattern == "*.pdf"
    assert profile.enabled and not profile.print.enabled
    assert profile.output_dir == Path("output")
    assert profile.output_name(Path("a/order.pdf")) == "order_p.pdf"


def test_output_name_prefix_suffix():
    profile = parse_config(minimal(filename_prefix="x_", filename_suffix="_2")).outputs["p"]
    assert profile.output_name(Path("order.pdf")) == "x_order_2_p.pdf"


@pytest.mark.parametrize(
    "data, message",
    [
        ({"outputs": {"p": {"pages": "all", "tranforms": []}}}, "did you mean 'transforms'"),
        ({"outputs": {"p": {"pages": "all"}}, "setings": {}}, "did you mean 'settings'"),
        ({"outputs": {}}, "at least one output profile"),
        ({"outputs": {"p": {}}}, "missing required 'pages'"),
        ({"outputs": {"p": {"pages": "1-2-3"}}}, "outputs.p.pages"),
        ({"outputs": {"p": {"pages": "all"}}, "version": 2}, "unsupported config version"),
        ({"outputs": {"p": {"pages": "all"}}, "settings": {"on_error": "explode"}}, "settings.on_error"),
        ({"outputs": {"p": {"pages": "all"}}, "settings": {"cleanup_source": "yes"}}, "expected bool"),
        ({"outputs": {"p": {"pages": "all", "sort": "random"}}}, "outputs.p.sort"),
        ({"outputs": {"p": {"pages": "all"}}, "input": {"filter": {"keywords": "ship"}}}, "list of strings"),
        ({"outputs": {"p": {"pages": "all"}}, "watch": {"poll_interval": 0}}, "poll_interval"),
        ("not a mapping", "expected a mapping"),
    ],
)
def test_invalid_configs(data, message):
    with pytest.raises(ConfigError, match=message):
        parse_config(data)


def test_invalid_yaml(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text("outputs: [unclosed")
    with pytest.raises(ConfigError, match="invalid YAML"):
        load_config(path)


def test_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_config(tmp_path / "nope.yaml")


class TestPrint:
    def test_legacy_single_printer(self):
        cfg = (
            parse_config(
                minimal(print={"enabled": True, "printer": "PL80E-BT", "copies": 2, "options": {"media": "w284h426"}})
            )
            .outputs["p"]
            .print
        )
        target = cfg.targets["default"]
        assert (target.printer, target.copies, target.options) == ("PL80E-BT", 2, {"media": "w284h426"})

    def test_targets(self):
        cfg = (
            parse_config(
                minimal(
                    print={
                        "enabled": True,
                        "merge": True,
                        "targets": {
                            "fast": {"printer": "A", "weight": 100, "args": ["-o sides=two-sided-long-edge"]},
                            "slow": {"printer": "B", "weight": 50, "options": {"fit-to-page": True}},
                        },
                    }
                )
            )
            .outputs["p"]
            .print
        )
        assert cfg.merge
        assert cfg.targets["fast"].args == ["-o", "sides=two-sided-long-edge"]
        assert cfg.targets["slow"].options == {"fit-to-page": "true"}

    def test_safety_limits_parsed_to_points(self):
        cfg = (
            parse_config(
                minimal(print={"printer": "A", "max_pages": 5, "max_page_size": ["4in", "6in"], "action": "warn"})
            )
            .outputs["p"]
            .print
        )
        assert cfg.max_pages == 5
        assert cfg.max_page_size == (288, 432)
        assert cfg.action == "warn"

    @pytest.mark.parametrize(
        "print_cfg, message",
        [
            ({"enabled": True}, "no 'printer' or 'targets'"),
            ({"printer": "A", "targets": {"x": {"printer": "B"}}}, "either 'targets' or a single 'printer'"),
            ({"targets": {"x": {"weight": 1}}}, "'printer' is required"),
            ({"printer": "A", "copies": 0}, "copies >= 1"),
            ({"printer": "A", "max_pages": 0}, "max_pages"),
            ({"printer": "A", "max_page_size": ["4in"]}, "two values"),
            ({"printer": "A", "action": "explode"}, "action"),
            ({"printer": "A", "options": {"media": ["a", "b"]}}, "single value"),
            ({"printer": "A", "args": {"a": 1}}, "list of strings"),
            ({"printer": "A", "colour": "red"}, "unknown key 'colour'"),
        ],
    )
    def test_invalid(self, print_cfg, message):
        with pytest.raises(ConfigError, match=message):
            parse_config(minimal(print=print_cfg))


class TestTransforms:
    def parse(self, *transforms):
        return parse_config(minimal(transforms=list(transforms))).outputs["p"].transforms

    def test_all_kinds(self):
        transforms = self.parse(
            {"rotate": 90},
            {"rotate": {"angle": "landscape", "pages": [0]}, "enabled": False},
            {"crop": {"lower_left": ["10mm", 0], "upper_right": ["4in", "6in"]}},
            {"size": {"width": "100mm", "height": "150mm", "fit": "stretch"}},
            {"stamp": {"text": "{page}", "font_color": "#ff0000", "opacity": 0.5}},
            {"split": {"regions": [{"lower_left": [0, 0], "upper_right": [100, 100]}]}},
            {"combine": {"layout": [{"page": 1, "position": ["1in", 0], "scale": 0.5}]}},
            {"render": 300},
        )
        names = [t.name for t in transforms]
        assert names == ["rotate", "rotate", "crop", "size", "stamp", "split", "combine", "render"]
        assert transforms[1].enabled is False
        assert transforms[2].options.x0 == pytest.approx(to_points("10mm"))
        assert transforms[4].options.font_color == "#ff0000"  # used to be silently dropped
        assert transforms[4].options.opacity == 0.5
        assert transforms[6].options.layout[0].x == 72
        assert transforms[7].options.dpi == 300
        assert [t.describe() for t in transforms][:3] == ["rotate90", "rotatelandscape", "crop"]

    def test_render_forms(self):
        assert [t.options.dpi for t in self.parse({"render": True}, {"render": {"dpi": 200}})] == [150, 200]

    @pytest.mark.parametrize(
        "transform, message",
        [
            ({"rotate": 45}, "multiple of 90"),
            ({"rotate": "sideways"}, "invalid rotation"),
            ({"rotate": 90, "pages": [0]}, "expected exactly one transform"),
            ({"rotate": {"angle": 90, "pages": "1"}}, "0-indexed page numbers"),
            ({"spin": 90}, "expected exactly one transform"),
            ("rotate", "expected a mapping"),
            ({"rotate": 90, "enabled": "no"}, "enabled"),
            ({"crop": {"lower_left": [0, 0]}}, "missing 'upper_right'"),
            ({"crop": {"lower_left": [10, 10], "upper_right": [5, 20]}}, "lower_left must be below"),
            ({"crop": {"lower_left": ["1 inch", 0], "upper_right": [5, 20]}}, "invalid length"),
            ({"size": {"width": "4in"}}, "missing 'height'"),
            ({"size": {"width": "4in", "height": "6in", "fit": "fill"}}, "fit"),
            ({"size": {"width": "0in", "height": "6in"}}, "positive"),
            ({"stamp": {"text": "x", "colour": "red"}}, "did you mean 'font_color'"),
            ({"stamp": {"position": "middle"}}, "position"),
            ({"stamp": {"opacity": 2}}, "opacity"),
            ({"stamp": 5}, "expected text or a mapping"),
            ({"split": {"regions": []}}, "non-empty list"),
            ({"combine": {"layout": []}}, "non-empty list"),
            ({"combine": {"layout": [{"page": 2}]}}, "between 0 and pages_per_output"),
            ({"combine": {"pages_per_output": 0, "layout": [{}]}}, "at least 1"),
            ({"render": 5}, "between 36 and 1200"),
            ({"render": {"dpi": 150, "color": True}}, "unknown key"),
        ],
    )
    def test_invalid(self, transform, message):
        with pytest.raises(ConfigError, match=message):
            self.parse(transform)


class TestUnits:
    @pytest.mark.parametrize(
        "value, points",
        [
            (72, 72.0),
            (1.5, 1.5),
            ("72pt", 72.0),
            ("1in", 72.0),
            ("25.4mm", 72.0),
            ("2.54cm", 72.0),
            ("10", 10.0),
            (" 2 IN ", 144.0),
            ("-1in", -72.0),
            (".5in", 36.0),
        ],
    )
    def test_to_points(self, value, points):
        assert to_points(value) == pytest.approx(points)

    @pytest.mark.parametrize("value", ["", "abc", "4 inches", True, None, [1]])
    def test_invalid(self, value):
        with pytest.raises(ConfigError):
            to_points(value)
