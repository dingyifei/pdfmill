"""Tests for pdfmill.config module."""

import pytest
import yaml
from pathlib import Path

from pdfmill.config import (
    load_config,
    parse_transform,
    parse_output_profile,
    ConfigError,
    Config,
    Transform,
    RotateTransform,
    CropTransform,
    SizeTransform,
    OutputProfile,
    PrintConfig,
    Settings,
)


class TestLoadConfig:
    """Test configuration file loading."""

    def test_load_minimal_config(self, temp_config_file):
        config = load_config(temp_config_file)
        assert isinstance(config, Config)
        assert "default" in config.outputs

    def test_load_full_config(self, full_config_file):
        config = load_config(full_config_file)
        assert config.version == 1
        assert config.settings.on_error == "continue"
        assert "profile1" in config.outputs
        profile = config.outputs["profile1"]
        assert profile.pages == "last"
        assert profile.filename_prefix == "pre_"
        assert len(profile.transforms) == 2
        assert profile.print.enabled is True

    def test_file_not_found(self, temp_dir):
        with pytest.raises(FileNotFoundError):
            load_config(temp_dir / "nonexistent.yaml")

    def test_invalid_yaml(self, temp_dir):
        bad_yaml = temp_dir / "bad.yaml"
        bad_yaml.write_text("{{invalid yaml: [")
        with pytest.raises(Exception):  # yaml.YAMLError
            load_config(bad_yaml)

    def test_missing_outputs_section(self, temp_dir):
        config_path = temp_dir / "no_outputs.yaml"
        with open(config_path, "w") as f:
            yaml.dump({"version": 1}, f)
        with pytest.raises(ConfigError, match="outputs"):
            load_config(config_path)

    def test_config_not_dict(self, temp_dir):
        config_path = temp_dir / "list.yaml"
        config_path.write_text("- item1\n- item2")
        with pytest.raises(ConfigError, match="dictionary"):
            load_config(config_path)

    def test_default_settings(self, temp_config_file):
        config = load_config(temp_config_file)
        assert config.settings.on_error == "continue"
        assert config.settings.cleanup_source is False
        assert config.settings.cleanup_output_after_print is False

    def test_default_input(self, temp_config_file):
        config = load_config(temp_config_file)
        assert config.input.pattern == "*.pdf"

    def test_custom_settings(self, temp_dir):
        config_dict = {
            "version": 1,
            "settings": {
                "on_error": "stop",
                "cleanup_source": True,
            },
            "outputs": {"default": {"pages": "all"}},
        }
        config_path = temp_dir / "custom.yaml"
        with open(config_path, "w") as f:
            yaml.dump(config_dict, f)
        config = load_config(config_path)
        assert config.settings.on_error == "stop"
        assert config.settings.cleanup_source is True


class TestParseTransform:
    """Test transform parsing."""

    def test_rotate_int(self):
        t = parse_transform({"rotate": 90})
        assert t.type == "rotate"
        assert t.rotate is not None
        assert t.rotate.angle == 90

    def test_rotate_string(self):
        t = parse_transform({"rotate": "landscape"})
        assert t.type == "rotate"
        assert t.rotate.angle == "landscape"

    def test_rotate_with_dict(self):
        t = parse_transform({"rotate": {"angle": 180, "pages": [1, 2]}})
        assert t.rotate.angle == 180
        assert t.rotate.pages == [1, 2]

    def test_rotate_dict_default_angle(self):
        t = parse_transform({"rotate": {}})
        assert t.rotate.angle == 0

    def test_crop_basic(self):
        t = parse_transform({
            "crop": {"lower_left": [10, 20], "upper_right": [100, 200]}
        })
        assert t.type == "crop"
        assert t.crop is not None
        assert t.crop.lower_left == (10, 20)
        assert t.crop.upper_right == (100, 200)

    def test_crop_defaults(self):
        t = parse_transform({"crop": {}})
        assert t.crop.lower_left == (0, 0)
        assert t.crop.upper_right == (612, 792)

    def test_size_basic(self):
        t = parse_transform({
            "size": {"width": "4in", "height": "6in", "fit": "contain"}
        })
        assert t.type == "size"
        assert t.size is not None
        assert t.size.width == "4in"
        assert t.size.height == "6in"
        assert t.size.fit == "contain"

    def test_size_defaults(self):
        t = parse_transform({"size": {}})
        assert t.size.width == ""
        assert t.size.height == ""
        assert t.size.fit == "contain"

    def test_unknown_transform_raises(self):
        with pytest.raises(ConfigError, match="Unknown transform"):
            parse_transform({"unknown": "value"})

    def test_empty_transform_raises(self):
        with pytest.raises(ConfigError):
            parse_transform({})


class TestParseOutputProfile:
    """Test output profile parsing."""

    def test_missing_pages_raises(self):
        with pytest.raises(ConfigError, match="pages"):
            parse_output_profile("test", {"output_dir": "./out"})

    def test_minimal_profile(self):
        profile = parse_output_profile("test", {"pages": "all"})
        assert profile.pages == "all"
        assert profile.output_dir == Path("./output")
        assert profile.filename_prefix == ""
        assert profile.filename_suffix == ""
        assert profile.transforms == []
        assert profile.print.enabled is False

    def test_full_profile(self):
        data = {
            "pages": "last",
            "output_dir": "./custom",
            "filename_prefix": "pre_",
            "filename_suffix": "_suf",
            "transforms": [{"rotate": 90}],
            "print": {
                "enabled": True,
                "printer": "My Printer",
                "copies": 2,
                "args": ["-silent"],
            },
        }
        profile = parse_output_profile("test", data)
        assert profile.pages == "last"
        assert profile.output_dir == Path("./custom")
        assert profile.filename_prefix == "pre_"
        assert profile.filename_suffix == "_suf"
        assert len(profile.transforms) == 1
        assert profile.print.enabled is True
        assert profile.print.printer == "My Printer"
        assert profile.print.copies == 2
        assert profile.print.args == ["-silent"]

    def test_list_pages(self):
        profile = parse_output_profile("test", {"pages": [1, 3, 5]})
        assert profile.pages == [1, 3, 5]

    def test_print_defaults(self):
        profile = parse_output_profile("test", {"pages": "all", "print": {}})
        assert profile.print.enabled is False
        assert profile.print.printer == ""
        assert profile.print.copies == 1
        assert profile.print.args == []


class TestDataclasses:
    """Test dataclass defaults and structure."""

    def test_config_defaults(self):
        config = Config()
        assert config.version == 1
        assert config.outputs == {}
        assert isinstance(config.settings, Settings)

    def test_settings_defaults(self):
        settings = Settings()
        assert settings.on_error == "continue"
        assert settings.cleanup_source is False
        assert settings.cleanup_output_after_print is False

    def test_print_config_defaults(self):
        pc = PrintConfig()
        assert pc.enabled is False
        assert pc.printer == ""
        assert pc.copies == 1
        assert pc.args == []

    def test_output_profile_pages_required(self):
        # pages is required, has no default
        with pytest.raises(TypeError):
            OutputProfile()

    def test_rotate_transform_defaults(self):
        rt = RotateTransform()
        assert rt.angle == 0
        assert rt.pages is None

    def test_crop_transform_defaults(self):
        ct = CropTransform()
        assert ct.lower_left == (0, 0)
        assert ct.upper_right == (612, 792)

    def test_size_transform_defaults(self):
        st = SizeTransform()
        assert st.width == ""
        assert st.height == ""
        assert st.fit == "contain"
