"""Watch mode: poll the input directory and process each new PDF once.

A file is processed once its size and mtime have stopped changing for
``debounce_delay`` seconds. Successfully processed files are recorded (by
name, size and mtime) in a JSON state file so restarts and config edits
never reprint them. Failed files are not retried while running, because a
retry could reprint profiles that already printed; modify or re-copy the
file, or restart watch mode, to retry it.
"""

import json
import threading
import time
from collections.abc import Callable
from pathlib import Path

from pdfmill.config import Config
from pdfmill.logging_config import get_logger
from pdfmill.processor import RunResult, process

logger = get_logger(__name__)

STATE_FILENAME = ".pdfmill_watch_state.json"

Signature = tuple[int, float]  # (size, mtime)


class Watcher:
    def __init__(
        self,
        config: Config,
        input_dir: Path,
        output_dir: Path | None = None,
        dry_run: bool = False,
        state_file: Path | None = None,
        process_existing: bool | None = None,
        poll_interval: float | None = None,
        debounce_delay: float | None = None,
        process_fn: Callable[..., RunResult] = process,
    ):
        self.config = config
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.dry_run = dry_run
        self.state_file = state_file or input_dir / STATE_FILENAME
        self.process_existing = config.watch.process_existing if process_existing is None else process_existing
        self.poll_interval = poll_interval or config.watch.poll_interval
        self.debounce_delay = config.watch.debounce_delay if debounce_delay is None else debounce_delay
        self.process_fn = process_fn

        self.done: dict[str, Signature] = self._load_state()
        self.skipped: dict[str, Signature] = {}  # failed, or pre-existing with process_existing off
        self._last_seen: dict[str, Signature] = {}
        self._stop = threading.Event()

    def run(self) -> None:
        """Poll until stop() is called or Ctrl+C."""
        logger.info("Watching %s for %s (Ctrl+C to stop)", self.input_dir, self.config.input.pattern)
        if not self.process_existing:
            self.skipped.update({p.name: sig for p, sig in self._scan()})
            logger.info("Skipping %d existing file(s)", len(self.skipped))
        try:
            while not self._stop.is_set():
                self.poll()
                self._stop.wait(self.poll_interval)
        except KeyboardInterrupt:
            pass
        logger.info("Watch mode stopped")

    def stop(self) -> None:
        self._stop.set()

    def poll(self) -> list[Path]:
        """Process every file that is new and stable. Returns the files attempted."""
        attempted = []
        now = time.time()
        current = self._scan()
        for path, sig in current:
            if self.done.get(path.name) == sig or self.skipped.get(path.name) == sig:
                continue
            stable = self._last_seen.get(path.name) == sig and now - sig[1] >= self.debounce_delay
            self._last_seen[path.name] = sig
            if stable and not self._stop.is_set():
                attempted.append(path)
                self._handle(path, sig)
        names = {p.name for p, _ in current}
        self._last_seen = {n: s for n, s in self._last_seen.items() if n in names}
        return attempted

    def _handle(self, path: Path, sig: Signature) -> None:
        logger.info("New file: %s", path.name)
        try:
            result = self.process_fn(self.config, input_path=path, output_dir=self.output_dir, dry_run=self.dry_run)
            ok = result.ok
        except Exception as e:
            logger.error("Failed to process %s: %s", path.name, e)
            ok = False
        if ok:
            self.done[path.name] = sig
            self._save_state()
        else:
            self.skipped[path.name] = sig
            logger.error(
                "Not retrying %s automatically; fix the problem, then modify/re-copy the file or restart", path.name
            )

    def _scan(self) -> list[tuple[Path, Signature]]:
        found = []
        for path in sorted(self.input_dir.glob(self.config.input.pattern)):
            try:
                st = path.stat()
            except OSError:
                continue  # removed between glob and stat
            if path.is_file() and path.name != self.state_file.name:
                found.append((path, (st.st_size, st.st_mtime)))
        return found

    def _load_state(self) -> dict[str, Signature]:
        try:
            data = json.loads(self.state_file.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        except (OSError, ValueError) as e:
            logger.warning("Ignoring unreadable watch state %s: %s", self.state_file, e)
            return {}
        return {name: (sig[0], sig[1]) for name, sig in data.get("files", {}).items()}

    def _save_state(self) -> None:
        if self.dry_run:
            return
        data = {"files": self.done}
        partial = self.state_file.with_suffix(".tmp")
        partial.write_text(json.dumps(data, indent=2), encoding="utf-8")
        partial.replace(self.state_file)
