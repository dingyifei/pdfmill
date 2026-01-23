"""Watch mode for monitoring input directory and processing new PDF files."""

import hashlib
import json
import signal
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from pdfmill.config import Config
from pdfmill.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class WatchConfig:
    """Configuration for watch mode behavior."""

    poll_interval: float = 2.0
    """Polling interval in seconds (fallback for network drives)."""

    debounce_delay: float = 1.0
    """Wait time in seconds for file stability check."""

    state_file: Path | None = None
    """Path to state tracking file. If None, defaults to .pdfmill_watch_state.json in input dir."""

    process_existing: bool = True
    """Whether to process existing files on startup."""


@dataclass
class FileState:
    """State of a tracked file."""

    filename: str
    mtime: float
    size: int
    processed_at: str


@dataclass
class WatchState:
    """Tracks processed files to avoid reprocessing after restarts."""

    state_file: Path
    config_hash: str
    processed_files: dict[str, FileState] = field(default_factory=dict)

    @classmethod
    def load(cls, state_file: Path, config_hash: str) -> "WatchState":
        """Load state from file, or create new if not exists or config changed."""
        if state_file.exists():
            try:
                with open(state_file, encoding="utf-8") as f:
                    data = json.load(f)

                # Check if config hash matches
                if data.get("config_hash") == config_hash:
                    processed = {}
                    for filename, file_data in data.get("processed_files", {}).items():
                        processed[filename] = FileState(
                            filename=file_data["filename"],
                            mtime=file_data["mtime"],
                            size=file_data["size"],
                            processed_at=file_data["processed_at"],
                        )
                    state = cls(
                        state_file=state_file,
                        config_hash=config_hash,
                        processed_files=processed,
                    )
                    logger.debug("Loaded watch state with %d processed files", len(processed))
                    return state
                else:
                    logger.info("Config changed, resetting watch state")
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning("Failed to load watch state: %s", e)

        return cls(state_file=state_file, config_hash=config_hash)

    def save(self) -> None:
        """Save state to file."""
        data = {
            "config_hash": self.config_hash,
            "processed_files": {
                filename: {
                    "filename": fs.filename,
                    "mtime": fs.mtime,
                    "size": fs.size,
                    "processed_at": fs.processed_at,
                }
                for filename, fs in self.processed_files.items()
            },
        }
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        logger.debug("Saved watch state with %d processed files", len(self.processed_files))

    def mark_processed(self, pdf_path: Path) -> None:
        """Mark a file as processed."""
        stat = pdf_path.stat()
        self.processed_files[pdf_path.name] = FileState(
            filename=pdf_path.name,
            mtime=stat.st_mtime,
            size=stat.st_size,
            processed_at=datetime.now().isoformat(),
        )
        self.save()

    def is_processed(self, pdf_path: Path) -> bool:
        """Check if a file has been processed (and hasn't changed)."""
        if pdf_path.name not in self.processed_files:
            return False

        file_state = self.processed_files[pdf_path.name]
        stat = pdf_path.stat()

        # Check if file has changed since processing
        if stat.st_mtime != file_state.mtime or stat.st_size != file_state.size:
            logger.debug("File changed since last processing: %s", pdf_path.name)
            return False

        return True


def compute_config_hash(config: Config) -> str:
    """Compute a hash of the config for detecting changes."""
    # Use a simple string representation of key config fields
    config_str = json.dumps(
        {
            "input_pattern": config.input.pattern,
            "outputs": list(config.outputs.keys()),
        },
        sort_keys=True,
    )
    return hashlib.md5(config_str.encode()).hexdigest()[:12]


class PdfWatcher:
    """Watches input directory for new PDF files and processes them."""

    def __init__(
        self,
        config: Config,
        input_path: Path,
        output_dir: Path | None = None,
        dry_run: bool = False,
        watch_config: WatchConfig | None = None,
        process_fn: Callable[[Config, Path, Path | None, bool], None] | None = None,
    ):
        """Initialize the watcher.

        Args:
            config: Pipeline configuration
            input_path: Path to input directory to watch
            output_dir: Override output directory (uses profile dirs if None)
            dry_run: If True, only describe what would be done
            watch_config: Watch mode configuration
            process_fn: Processing function (defaults to pdfmill.processor.process)
        """
        self.config = config
        self.input_path = input_path
        self.output_dir = output_dir
        self.dry_run = dry_run
        self.watch_config = watch_config or WatchConfig()

        # Import here to avoid circular imports
        if process_fn is None:
            from pdfmill.processor import process

            self.process_fn = process
        else:
            self.process_fn = process_fn

        # Initialize state tracking
        state_file = self.watch_config.state_file
        if state_file is None:
            state_file = input_path / ".pdfmill_watch_state.json"
        config_hash = compute_config_hash(config)
        self.state = WatchState.load(state_file, config_hash)

        # Shutdown flag
        self._shutdown = False

        # Heartbeat counter for logging
        self._check_count = 0

    def _is_file_stable(self, pdf_path: Path) -> bool:
        """Check if file has stopped being written to."""
        try:
            stat1 = pdf_path.stat()
            time.sleep(self.watch_config.debounce_delay)
            if not pdf_path.exists():
                return False
            stat2 = pdf_path.stat()
            return stat1.st_size == stat2.st_size and stat1.st_mtime == stat2.st_mtime
        except OSError:
            return False

    def _process_file(self, pdf_path: Path) -> bool:
        """Process a single PDF file.

        Returns:
            True if processing succeeded, False otherwise
        """
        logger.info("Detected new file: %s", pdf_path.name)

        if not self._is_file_stable(pdf_path):
            logger.debug("File not stable yet, skipping: %s", pdf_path.name)
            return False

        try:
            self.process_fn(
                config=self.config,
                input_path=pdf_path,
                output_dir=self.output_dir,
                dry_run=self.dry_run,
            )
            self.state.mark_processed(pdf_path)
            return True
        except Exception as e:
            logger.error("Failed to process %s: %s", pdf_path.name, e)
            return False

    def _get_pending_files(self) -> list[Path]:
        """Get list of PDF files that need processing."""
        pattern = self.config.input.pattern
        pdf_files = sorted(self.input_path.glob(pattern))
        return [f for f in pdf_files if not self.state.is_processed(f)]

    def _setup_signals(self) -> None:
        """Setup signal handlers for graceful shutdown.

        Only works when called from the main thread. When running from GUI
        (background thread), signal handlers are not needed since the GUI
        controls shutdown via the _shutdown flag.
        """
        try:

            def handle_shutdown(signum: int, frame) -> None:
                logger.info("\nShutdown signal received, stopping watch...")
                self._shutdown = True

            signal.signal(signal.SIGINT, handle_shutdown)
            # SIGTERM doesn't exist on Windows
            if hasattr(signal, "SIGTERM"):
                signal.signal(signal.SIGTERM, handle_shutdown)
        except ValueError:
            # "signal only works in main thread" - skip when running from GUI thread
            logger.debug("Skipping signal handler setup (not in main thread)")

    def _is_network_path(self, path: Path) -> bool:
        """Check if path is on a network drive."""
        try:
            # On Windows, network paths start with \\
            path_str = str(path.resolve())
            return path_str.startswith("\\\\")
        except OSError:
            return False

    def run(self) -> None:
        """Start watching the input directory."""
        self._setup_signals()

        logger.info("Starting watch mode for: %s", self.input_path)
        logger.info("Pattern: %s", self.config.input.pattern)
        logger.info("Press Ctrl+C to stop watching")

        # Process existing files if configured
        if self.watch_config.process_existing:
            pending = self._get_pending_files()
            if pending:
                logger.info("Processing %d existing file(s)...", len(pending))
                for pdf_path in pending:
                    if self._shutdown:
                        break
                    self._process_file(pdf_path)

        # Determine if we should use polling or native events
        use_polling = self._is_network_path(self.input_path)

        try:
            # Try to use watchdog for native file events
            from watchdog.events import FileSystemEventHandler
            from watchdog.observers import Observer
            from watchdog.observers.polling import PollingObserver

            watcher = self

            class PdfHandler(FileSystemEventHandler):
                def on_created(self, event):
                    if event.is_directory:
                        return
                    path = Path(event.src_path)
                    if (
                        path.suffix.lower() == ".pdf"
                        and path.match(watcher.config.input.pattern)
                        and not watcher.state.is_processed(path)
                    ):
                        watcher._process_file(path)

                def on_modified(self, event):
                    if event.is_directory:
                        return
                    path = Path(event.src_path)
                    if (
                        path.suffix.lower() == ".pdf"
                        and path.match(watcher.config.input.pattern)
                        and not watcher.state.is_processed(path)
                    ):
                        watcher._process_file(path)

            handler = PdfHandler()

            if use_polling:
                logger.info("Using polling observer (network drive detected)")
                observer = PollingObserver(timeout=self.watch_config.poll_interval)
            else:
                logger.debug("Using native file system observer")
                observer = Observer()

            observer.schedule(handler, str(self.input_path), recursive=False)
            observer.start()

            try:
                while not self._shutdown:
                    time.sleep(0.5)
                    self._check_count += 1
                    if self._check_count % 10 == 0:
                        logger.info("Watching... (check #%d)", self._check_count)
            finally:
                observer.stop()
                observer.join()

        except ImportError:
            # Fallback to simple polling if watchdog is not available
            logger.warning("watchdog not installed, using simple polling")
            self._run_polling()

        logger.info("Watch mode stopped")

    def _run_polling(self) -> None:
        """Fallback polling implementation."""
        while not self._shutdown:
            pending = self._get_pending_files()
            for pdf_path in pending:
                if self._shutdown:
                    break
                self._process_file(pdf_path)

            time.sleep(self.watch_config.poll_interval)
            self._check_count += 1
            if self._check_count % 10 == 0:
                logger.info("Watching... (check #%d)", self._check_count)
