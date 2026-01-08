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
    PrintTarget,
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
        # Legacy printer config is converted to "default" target
        assert "default" in profile.print.targets
        assert profile.print.targets["default"].printer == "My Printer"
        assert profile.print.targets["default"].copies == 2
        assert profile.print.targets["default"].args == ["-silent"]

    def test_list_pages(self):
        profile = parse_output_profile("test", {"pages": [1, 3, 5]})
        assert profile.pages == [1, 3, 5]

    def test_print_defaults(self):
        profile = parse_output_profile("test", {"pages": "all", "print": {}})
        assert profile.print.enabled is False
        assert profile.print.targets == {}  # No targets when no printer specified
        assert profile.print.merge is False


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
        assert pc.merge is False
        assert pc.targets == {}

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


class TestPrintTargets:
    """Test new multi-printer targets configuration."""

    def test_parse_targets_config(self):
        data = {
            "pages": "all",
            "print": {
                "enabled": True,
                "merge": True,
                "targets": {
                    "fast": {
                        "printer": "HP LaserJet",
                        "weight": 100,
                        "copies": 2,
                        "args": ["-silent"],
                    },
                    "slow": {
                        "printer": "Brother",
                        "weight": 50,
                    },
                },
            },
        }
        profile = parse_output_profile("test", data)

        assert profile.print.enabled is True
        assert profile.print.merge is True
        assert len(profile.print.targets) == 2
        assert "fast" in profile.print.targets
        assert "slow" in profile.print.targets
        assert profile.print.targets["fast"].printer == "HP LaserJet"
        assert profile.print.targets["fast"].weight == 100
        assert profile.print.targets["fast"].copies == 2
        assert profile.print.targets["fast"].args == ["-silent"]
        assert profile.print.targets["slow"].printer == "Brother"
        assert profile.print.targets["slow"].weight == 50
        assert profile.print.targets["slow"].copies == 1  # default

    def test_parse_sort_option(self):
        data = {
            "pages": "all",
            "sort": "name_asc",
        }
        profile = parse_output_profile("test", data)
        assert profile.sort == "name_asc"

    def test_print_target_defaults(self):
        target = PrintTarget(printer="Test")
        assert target.weight == 1
        assert target.copies == 1
        assert target.args == []


class TestInputSort:
    """Test input sorting configuration."""

    def test_input_config_with_sort(self, tmp_path):
        config_content = """
version: 1
input:
  path: ./input
  sort: time_desc
outputs:
  test:
    pages: all
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_content)

        config = load_config(config_file)
        assert config.input.sort == "time_desc"

    def test_input_config_sort_default(self, tmp_path):
        config_content = """
version: 1
input:
  path: ./input
outputs:
  test:
    pages: all
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_content)

        config = load_config(config_file)
        assert config.input.sort is None


class TestEnabledField:
    """Test enabled field for profiles and transforms."""

    def test_transform_enabled_default_true(self):
        """Transform enabled should default to True."""
        t = parse_transform({"rotate": 90})
        assert t.enabled is True

    def test_transform_enabled_explicit_true(self):
        """Transform with explicit enabled=True."""
        t = parse_transform({"rotate": 90, "enabled": True})
        assert t.enabled is True

    def test_transform_enabled_false(self):
        """Transform with enabled=False should be disabled."""
        t = parse_transform({"rotate": 90, "enabled": False})
        assert t.enabled is False

    def test_crop_transform_enabled_false(self):
        """Crop transform with enabled=False."""
        t = parse_transform({
            "crop": {"lower_left": [0, 0], "upper_right": [100, 100]},
            "enabled": False
        })
        assert t.type == "crop"
        assert t.enabled is False

    def test_size_transform_enabled_false(self):
        """Size transform with enabled=False."""
        t = parse_transform({
            "size": {"width": "4in", "height": "6in"},
            "enabled": False
        })
        assert t.type == "size"
        assert t.enabled is False

    def test_profile_enabled_default_true(self):
        """Profile enabled should default to True."""
        profile = parse_output_profile("test", {"pages": "all"})
        assert profile.enabled is True

    def test_profile_enabled_explicit_true(self):
        """Profile with explicit enabled=True."""
        profile = parse_output_profile("test", {"pages": "all", "enabled": True})
        assert profile.enabled is True

    def test_profile_enabled_false(self):
        """Profile with enabled=False should be disabled."""
        profile = parse_output_profile("test", {"pages": "all", "enabled": False})
        assert profile.enabled is False

    def test_profile_with_disabled_transforms(self):
        """Profile with some disabled transforms."""
        data = {
            "pages": "all",
            "transforms": [
                {"rotate": 90, "enabled": True},
                {"rotate": 180, "enabled": False},
                {"crop": {"lower_left": [0, 0], "upper_right": [100, 100]}},
            ]
        }
        profile = parse_output_profile("test", data)
        assert len(profile.transforms) == 3
        assert profile.transforms[0].enabled is True
        assert profile.transforms[1].enabled is False
        assert profile.transforms[2].enabled is True  # default

    def test_transform_dataclass_enabled_default(self):
        """Transform dataclass enabled field defaults to True."""
        t = Transform(type="rotate", rotate=RotateTransform(angle=90))
        assert t.enabled is True

    def test_transform_dataclass_enabled_false(self):
        """Transform dataclass can be created with enabled=False."""
        t = Transform(type="rotate", rotate=RotateTransform(angle=90), enabled=False)
        assert t.enabled is False

    def test_output_profile_dataclass_enabled_default(self):
        """OutputProfile dataclass enabled field defaults to True."""
        profile = OutputProfile(pages="all")
        assert profile.enabled is True

    def test_output_profile_dataclass_enabled_false(self):
        """OutputProfile dataclass can be created with enabled=False."""
        profile = OutputProfile(pages="all", enabled=False)
        assert profile.enabled is False

    def test_load_config_with_disabled_profile(self, tmp_path):
        """Test loading a config file with a disabled profile."""
        config_content = """
version: 1
outputs:
  enabled_profile:
    pages: all
  disabled_profile:
    enabled: false
    pages: last
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_content)

        config = load_config(config_file)
        assert config.outputs["enabled_profile"].enabled is True
        assert config.outputs["disabled_profile"].enabled is False

    def test_load_config_with_disabled_transform(self, tmp_path):
        """Test loading a config file with a disabled transform."""
        config_content = """
version: 1
outputs:
  test:
    pages: all
    transforms:
      - rotate: 90
      - rotate: 180
        enabled: false
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_content)

        config = load_config(config_file)
        transforms = config.outputs["test"].transforms
        assert len(transforms) == 2
        assert transforms[0].enabled is True
        assert transforms[1].enabled is False
