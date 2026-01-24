"""Tests for pdfmill.watcher module."""

import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pdfmill.watcher import (
    FileState,
    PdfWatcher,
    WatchConfig,
    WatchState,
    compute_config_hash,
)


class TestWatchConfig:
    """Test WatchConfig dataclass."""

    def test_default_values(self):
        config = WatchConfig()
        assert config.poll_interval == 2.0
        assert config.debounce_delay == 1.0
        assert config.state_file is None
        assert config.process_existing is True

    def test_custom_values(self):
        config = WatchConfig(
            poll_interval=5.0,
            debounce_delay=2.0,
            state_file=Path("/tmp/state.json"),
            process_existing=False,
        )
        assert config.poll_interval == 5.0
        assert config.debounce_delay == 2.0
        assert config.state_file == Path("/tmp/state.json")
        assert config.process_existing is False


class TestFileState:
    """Test FileState dataclass."""

    def test_file_state_creation(self):
        state = FileState(
            filename="test.pdf",
            mtime=1234567890.0,
            size=1024,
            processed_at="2024-01-01T12:00:00",
        )
        assert state.filename == "test.pdf"
        assert state.mtime == 1234567890.0
        assert state.size == 1024
        assert state.processed_at == "2024-01-01T12:00:00"


class TestWatchState:
    """Test WatchState class."""

    def test_load_creates_new_if_not_exists(self, temp_dir):
        state_file = temp_dir / ".pdfmill_watch_state.json"
        state = WatchState.load(state_file, "abc123")

        assert state.state_file == state_file
        assert state.config_hash == "abc123"
        assert len(state.processed_files) == 0

    def test_load_existing_state(self, temp_dir):
        state_file = temp_dir / ".pdfmill_watch_state.json"
        existing_data = {
            "config_hash": "abc123",
            "processed_files": {
                "test.pdf": {
                    "filename": "test.pdf",
                    "mtime": 1234567890.0,
                    "size": 1024,
                    "processed_at": "2024-01-01T12:00:00",
                }
            },
        }
        with open(state_file, "w") as f:
            json.dump(existing_data, f)

        state = WatchState.load(state_file, "abc123")
        assert len(state.processed_files) == 1
        assert "test.pdf" in state.processed_files
        assert state.processed_files["test.pdf"].size == 1024

    def test_load_resets_on_config_change(self, temp_dir):
        state_file = temp_dir / ".pdfmill_watch_state.json"
        existing_data = {
            "config_hash": "old_hash",
            "processed_files": {
                "test.pdf": {
                    "filename": "test.pdf",
                    "mtime": 1234567890.0,
                    "size": 1024,
                    "processed_at": "2024-01-01T12:00:00",
                }
            },
        }
        with open(state_file, "w") as f:
            json.dump(existing_data, f)

        state = WatchState.load(state_file, "new_hash")
        assert len(state.processed_files) == 0

    def test_save(self, temp_dir):
        state_file = temp_dir / ".pdfmill_watch_state.json"
        state = WatchState(
            state_file=state_file,
            config_hash="abc123",
            processed_files={
                "test.pdf": FileState(
                    filename="test.pdf",
                    mtime=1234567890.0,
                    size=1024,
                    processed_at="2024-01-01T12:00:00",
                )
            },
        )
        state.save()

        with open(state_file) as f:
            data = json.load(f)

        assert data["config_hash"] == "abc123"
        assert "test.pdf" in data["processed_files"]
        assert data["processed_files"]["test.pdf"]["size"] == 1024

    def test_mark_processed(self, temp_dir, temp_pdf):
        state_file = temp_dir / ".pdfmill_watch_state.json"
        state = WatchState(state_file=state_file, config_hash="abc123")

        state.mark_processed(temp_pdf)

        assert temp_pdf.name in state.processed_files
        file_state = state.processed_files[temp_pdf.name]
        assert file_state.filename == temp_pdf.name
        assert file_state.size > 0

        # Verify state file was saved
        assert state_file.exists()

    def test_is_processed_returns_false_for_new_file(self, temp_dir, temp_pdf):
        state_file = temp_dir / ".pdfmill_watch_state.json"
        state = WatchState(state_file=state_file, config_hash="abc123")

        assert state.is_processed(temp_pdf) is False

    def test_is_processed_returns_true_for_processed_file(self, temp_dir, temp_pdf):
        state_file = temp_dir / ".pdfmill_watch_state.json"
        state = WatchState(state_file=state_file, config_hash="abc123")

        state.mark_processed(temp_pdf)
        assert state.is_processed(temp_pdf) is True

    def test_is_processed_detects_changed_file(self, temp_dir):
        from pypdf import PdfWriter

        state_file = temp_dir / ".pdfmill_watch_state.json"
        state = WatchState(state_file=state_file, config_hash="abc123")

        # Create a PDF and mark it processed
        pdf_path = temp_dir / "test.pdf"
        writer = PdfWriter()
        writer.add_blank_page(width=612, height=792)
        with open(pdf_path, "wb") as f:
            writer.write(f)

        state.mark_processed(pdf_path)

        # Modify the file (append content to change size/mtime)
        time.sleep(0.1)  # Ensure mtime changes
        writer = PdfWriter()
        writer.add_blank_page(width=612, height=792)
        writer.add_blank_page(width=612, height=792)
        with open(pdf_path, "wb") as f:
            writer.write(f)

        assert state.is_processed(pdf_path) is False


class TestComputeConfigHash:
    """Test config hash computation."""

    def test_same_config_same_hash(self, temp_config_file):
        from pdfmill.config import load_config

        config1 = load_config(temp_config_file)
        config2 = load_config(temp_config_file)

        hash1 = compute_config_hash(config1)
        hash2 = compute_config_hash(config2)

        assert hash1 == hash2

    def test_different_outputs_different_hash(self, temp_dir, minimal_config_dict):
        import yaml

        from pdfmill.config import load_config

        # Create first config
        config_path1 = temp_dir / "config1.yaml"
        with open(config_path1, "w") as f:
            yaml.dump(minimal_config_dict, f)
        config1 = load_config(config_path1)

        # Create second config with additional output
        minimal_config_dict["outputs"]["another"] = {"pages": "first"}
        config_path2 = temp_dir / "config2.yaml"
        with open(config_path2, "w") as f:
            yaml.dump(minimal_config_dict, f)
        config2 = load_config(config_path2)

        hash1 = compute_config_hash(config1)
        hash2 = compute_config_hash(config2)

        assert hash1 != hash2


class TestPdfWatcher:
    """Test PdfWatcher class."""

    @pytest.fixture
    def mock_config(self, temp_config_file):
        from pdfmill.config import load_config

        return load_config(temp_config_file)

    @pytest.fixture
    def mock_process(self):
        return MagicMock()

    def test_init_creates_state(self, mock_config, temp_dir, mock_process):
        watcher = PdfWatcher(
            config=mock_config,
            input_path=temp_dir,
            process_fn=mock_process,
        )

        assert watcher.config == mock_config
        assert watcher.input_path == temp_dir
        assert watcher.state is not None

    def test_init_with_custom_watch_config(self, mock_config, temp_dir, mock_process):
        watch_config = WatchConfig(
            poll_interval=5.0,
            debounce_delay=3.0,
            process_existing=False,
        )

        watcher = PdfWatcher(
            config=mock_config,
            input_path=temp_dir,
            watch_config=watch_config,
            process_fn=mock_process,
        )

        assert watcher.watch_config.poll_interval == 5.0
        assert watcher.watch_config.debounce_delay == 3.0
        assert watcher.watch_config.process_existing is False

    def test_get_pending_files_empty(self, mock_config, temp_dir, mock_process):
        watcher = PdfWatcher(
            config=mock_config,
            input_path=temp_dir,
            process_fn=mock_process,
        )

        pending = watcher._get_pending_files()
        assert len(pending) == 0

    def test_get_pending_files_with_pdfs(self, mock_config, temp_dir, mock_process):
        from pypdf import PdfWriter

        # Create test PDFs
        for name in ["a.pdf", "b.pdf"]:
            writer = PdfWriter()
            writer.add_blank_page(width=612, height=792)
            with open(temp_dir / name, "wb") as f:
                writer.write(f)

        watcher = PdfWatcher(
            config=mock_config,
            input_path=temp_dir,
            process_fn=mock_process,
        )

        pending = watcher._get_pending_files()
        assert len(pending) == 2

    def test_get_pending_files_excludes_processed(self, mock_config, temp_dir, mock_process):
        from pypdf import PdfWriter

        # Create test PDF
        pdf_path = temp_dir / "test.pdf"
        writer = PdfWriter()
        writer.add_blank_page(width=612, height=792)
        with open(pdf_path, "wb") as f:
            writer.write(f)

        watcher = PdfWatcher(
            config=mock_config,
            input_path=temp_dir,
            process_fn=mock_process,
        )

        # Mark as processed
        watcher.state.mark_processed(pdf_path)

        pending = watcher._get_pending_files()
        assert len(pending) == 0

    def test_is_file_stable_stable_file(self, mock_config, temp_dir, mock_process, temp_pdf):
        watch_config = WatchConfig(debounce_delay=0.1)
        watcher = PdfWatcher(
            config=mock_config,
            input_path=temp_dir,
            watch_config=watch_config,
            process_fn=mock_process,
        )

        assert watcher._is_file_stable(temp_pdf) is True

    def test_is_file_stable_deleted_during_check(self, mock_config, temp_dir, mock_process):
        from pypdf import PdfWriter

        # Create test PDF
        pdf_path = temp_dir / "temp.pdf"
        writer = PdfWriter()
        writer.add_blank_page(width=612, height=792)
        with open(pdf_path, "wb") as f:
            writer.write(f)

        watch_config = WatchConfig(debounce_delay=0.2)
        watcher = PdfWatcher(
            config=mock_config,
            input_path=temp_dir,
            watch_config=watch_config,
            process_fn=mock_process,
        )

        # Delete file during stability check
        def delete_file(*args, **kwargs):
            pdf_path.unlink()
            return time.sleep(*args, **kwargs)

        with patch("time.sleep", side_effect=delete_file):
            assert watcher._is_file_stable(pdf_path) is False

    def test_process_file_success(self, mock_config, temp_dir, mock_process, temp_pdf):
        watch_config = WatchConfig(debounce_delay=0.1)
        watcher = PdfWatcher(
            config=mock_config,
            input_path=temp_dir,
            watch_config=watch_config,
            process_fn=mock_process,
        )

        result = watcher._process_file(temp_pdf)

        assert result is True
        mock_process.assert_called_once()
        assert watcher.state.is_processed(temp_pdf)

    def test_process_file_failure(self, mock_config, temp_dir, temp_pdf):
        mock_process = MagicMock(side_effect=Exception("Processing failed"))
        watch_config = WatchConfig(debounce_delay=0.1)
        watcher = PdfWatcher(
            config=mock_config,
            input_path=temp_dir,
            watch_config=watch_config,
            process_fn=mock_process,
        )

        result = watcher._process_file(temp_pdf)

        assert result is False
        assert not watcher.state.is_processed(temp_pdf)

    def test_is_network_path_local(self, mock_config, temp_dir, mock_process):
        watcher = PdfWatcher(
            config=mock_config,
            input_path=temp_dir,
            process_fn=mock_process,
        )

        assert watcher._is_network_path(temp_dir) is False

    def test_is_network_path_unc(self, mock_config, temp_dir, mock_process):
        watcher = PdfWatcher(
            config=mock_config,
            input_path=temp_dir,
            process_fn=mock_process,
        )

        # Mock path resolution to return UNC path
        with patch.object(Path, "resolve", return_value=Path("\\\\server\\share\\folder")):
            assert watcher._is_network_path(Path("Z:\\folder")) is True


class TestCliWatchArguments:
    """Test CLI argument parsing for watch mode."""

    def test_watch_flag(self):
        from pdfmill.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["--watch"])
        assert args.watch is True

    def test_watch_interval_default(self):
        from pdfmill.cli import create_parser

        parser = create_parser()
        args = parser.parse_args([])
        assert args.watch_interval == 2.0

    def test_watch_interval_custom(self):
        from pdfmill.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["--watch-interval", "5.0"])
        assert args.watch_interval == 5.0

    def test_watch_debounce_default(self):
        from pdfmill.cli import create_parser

        parser = create_parser()
        args = parser.parse_args([])
        assert args.watch_debounce == 1.0

    def test_watch_debounce_custom(self):
        from pdfmill.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["--watch-debounce", "3.0"])
        assert args.watch_debounce == 3.0

    def test_watch_state_path(self):
        from pdfmill.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["--watch-state", "/tmp/state.json"])
        assert args.watch_state == Path("/tmp/state.json")

    def test_no_process_existing_flag(self):
        from pdfmill.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["--no-process-existing"])
        assert args.no_process_existing is True


class TestCliWatchMode:
    """Test CLI watch mode handling."""

    def test_watch_requires_directory(self, temp_config_file, temp_pdf):
        from pdfmill.cli import main

        result = main(["-c", str(temp_config_file), "-i", str(temp_pdf), "--watch"])
        assert result == 1

    def test_watch_mode_starts(self, temp_config_file, temp_dir):
        from pdfmill.cli import main

        with patch("pdfmill.watcher.PdfWatcher") as mock_watcher_class:
            mock_watcher = MagicMock()
            mock_watcher_class.return_value = mock_watcher

            result = main(["-c", str(temp_config_file), "-i", str(temp_dir), "--watch"])

            mock_watcher.run.assert_called_once()
            assert result == 0

    def test_watch_mode_passes_config(self, temp_config_file, temp_dir):
        from pdfmill.cli import main

        with patch("pdfmill.watcher.PdfWatcher") as mock_watcher_class:
            mock_watcher = MagicMock()
            mock_watcher_class.return_value = mock_watcher

            main([
                "-c", str(temp_config_file),
                "-i", str(temp_dir),
                "--watch",
                "--watch-interval", "5.0",
                "--watch-debounce", "2.0",
                "--no-process-existing",
            ])

            call_kwargs = mock_watcher_class.call_args.kwargs
            assert call_kwargs["watch_config"].poll_interval == 5.0
            assert call_kwargs["watch_config"].debounce_delay == 2.0
            assert call_kwargs["watch_config"].process_existing is False

    def test_watch_mode_with_dry_run(self, temp_config_file, temp_dir):
        from pdfmill.cli import main

        with patch("pdfmill.watcher.PdfWatcher") as mock_watcher_class:
            mock_watcher = MagicMock()
            mock_watcher_class.return_value = mock_watcher

            main(["-c", str(temp_config_file), "-i", str(temp_dir), "--watch", "--dry-run"])

            call_kwargs = mock_watcher_class.call_args.kwargs
            assert call_kwargs["dry_run"] is True
