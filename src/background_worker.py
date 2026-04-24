"""Background worker that processes files from an incoming directory."""

from __future__ import annotations

import logging
import os
import re
import shutil
import time
from pathlib import Path

from dotenv import load_dotenv
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers.polling import PollingObserver

from bot.utils.logger import setup_logging

LOGGER = logging.getLogger("worker")
ALLOWED_EXTENSIONS = {".pdf", ".epub"}


def _clean_stem(stem: str) -> str:
    normalized = stem.strip().lower()
    normalized = re.sub(r"\s+", "_", normalized)
    normalized = re.sub(r"[^a-z0-9._-]", "", normalized)
    return normalized.strip("._-") or "file"


def _safe_destination(processed_dir: Path, source_name: str) -> Path:
    src_path = Path(source_name)
    clean_name = f"{_clean_stem(src_path.stem)}{src_path.suffix.lower()}"
    destination = processed_dir / clean_name
    if not destination.exists():
        return destination
    for i in range(1, 10000):
        candidate = processed_dir / f"{_clean_stem(src_path.stem)}_{i}{src_path.suffix.lower()}"
        if not candidate.exists():
            return candidate
    raise RuntimeError("No se pudo generar un nombre único para el archivo.")


def _ensure_writable_dir(path_value: str, fallback_value: str) -> Path:
    candidate = Path(path_value).expanduser().resolve()
    try:
        candidate.mkdir(parents=True, exist_ok=True)
        return candidate
    except OSError:
        fallback = Path(fallback_value).expanduser().resolve()
        fallback.mkdir(parents=True, exist_ok=True)
        LOGGER.warning(
            "Ruta no escribible (%s). Usando fallback local: %s",
            candidate,
            fallback,
        )
        return fallback


def process_file(file_path: Path, processed_dir: Path) -> None:
    if not file_path.exists() or not file_path.is_file():
        LOGGER.debug("Ignorando ruta no válida: %s", file_path)
        return

    extension = file_path.suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        LOGGER.info("Archivo ignorado por tipo no permitido: %s", file_path.name)
        return

    destination = _safe_destination(processed_dir, file_path.name)
    shutil.move(str(file_path), str(destination))
    LOGGER.info("Archivo procesado: %s -> %s", file_path, destination)


class IncomingFileHandler(FileSystemEventHandler):
    def __init__(self, processed_dir: Path) -> None:
        self.processed_dir = processed_dir

    def on_created(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        file_path = Path(event.src_path)
        try:
            process_file(file_path, self.processed_dir)
        except Exception:
            LOGGER.exception("Error procesando archivo creado: %s", file_path)

    def on_moved(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        file_path = Path(event.dest_path)
        try:
            process_file(file_path, self.processed_dir)
        except Exception:
            LOGGER.exception("Error procesando archivo movido: %s", file_path)


def main() -> None:
    load_dotenv()
    log_level = os.environ.get("LOG_LEVEL", "INFO").strip() or "INFO"
    setup_logging(log_level)

    incoming_dir = _ensure_writable_dir(
        os.environ.get("INCOMING_FILES_PATH", "/data/incoming").strip() or "/data/incoming",
        "./data/incoming",
    )
    processed_dir = _ensure_writable_dir(
        os.environ.get("PROCESSED_FILES_PATH", "/data/processed").strip() or "/data/processed",
        "./data/processed",
    )
    poll_interval = float(os.environ.get("WORKER_POLL_INTERVAL_SEC", "1.0").strip() or "1.0")

    LOGGER.info("Worker iniciado. incoming=%s processed=%s", incoming_dir, processed_dir)
    observer = PollingObserver(timeout=max(0.2, poll_interval))
    observer.schedule(IncomingFileHandler(processed_dir), str(incoming_dir), recursive=False)
    observer.start()

    try:
        while True:
            time.sleep(max(0.1, poll_interval))
    except KeyboardInterrupt:
        LOGGER.info("Deteniendo worker por interrupción de teclado.")
    except Exception:
        LOGGER.exception("Error inesperado en loop principal del worker.")
    finally:
        observer.stop()
        observer.join(timeout=10)
        LOGGER.info("Worker detenido.")


if __name__ == "__main__":
    main()
