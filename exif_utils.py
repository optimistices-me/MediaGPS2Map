"""Batch EXIF metadata extraction via ExifTool.

Walks configured directories, skips files whose mtime has not changed,
and processes in configurable batch sizes.
"""

import json
import logging
import os
import subprocess
from datetime import datetime
from typing import Any

from database import get_modified_time, upsert_media

logger = logging.getLogger(__name__)

DEFAULT_BATCH_SIZE: int = 200
EXIFTOOL_ARGS: list[str] = [
    "exiftool",
    "-json",
    "-n",
    "-q",
    "-GPSLatitude",
    "-GPSLongitude",
    "-DateTimeOriginal",
    "-FileModifyDate",
    "-GPSAltitude",
    "-Track*",
]


def extract_metadata_batch(file_paths: list[str]) -> list[dict[str, Any]]:
    """Run ExifTool on *file_paths* and return parsed JSON output."""
    try:
        result = subprocess.run(
            EXIFTOOL_ARGS + file_paths,
            capture_output=True,
            text=True,
            timeout=120,
        )
        result.check_returncode()
        return json.loads(result.stdout)
    except FileNotFoundError:
        logger.error("ExifTool not found. Make sure it is installed and on PATH.")
        raise
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, json.JSONDecodeError) as e:
        logger.error("ExifTool batch failed: %s", e)
        return []


def _parse_timestamp(date_str: str) -> str | None:
    """Try to parse an ExifTool timestamp into ISO-8601 string."""
    try:
        dt = datetime.strptime(date_str[:19], "%Y:%m:%d %H:%M:%S")
        return dt.isoformat()
    except (ValueError, TypeError):
        return None


def process_batch(
    file_batch: list[str], batch_size: int = DEFAULT_BATCH_SIZE
) -> None:
    """Run ExifTool on *file_batch* and upsert results into the database."""
    metadata = extract_metadata_batch(file_batch)
    insert_data: list[tuple[Any, ...]] = []

    for entry in metadata:
        path = entry.get("SourceFile")
        if not path:
            continue

        gps = (entry.get("GPSLatitude"), entry.get("GPSLongitude"))
        altitude = entry.get("GPSAltitude")
        date_str = entry.get("DateTimeOriginal") or entry.get("FileModifyDate")

        if not (all(gps) and date_str):
            logger.debug("Skipping %s: missing GPS or timestamp", path)
            continue

        timestamp = _parse_timestamp(date_str)
        if not timestamp:
            continue

        alt: float | None = None
        if altitude is not None:
            try:
                alt = float(str(altitude).replace(",", "."))
            except ValueError:
                pass

        try:
            mtime = os.path.getmtime(path)
        except OSError:
            mtime = 0.0

        insert_data.append((path, float(gps[0]), float(gps[1]), alt, timestamp, mtime))

    if insert_data:
        upsert_media(insert_data)
        logger.info("Inserted %d records", len(insert_data))
    else:
        logger.info("No valid records in batch (%d files scanned)", len(file_batch))


def process_files(root_dir: str, batch_size: int = DEFAULT_BATCH_SIZE) -> None:
    """Walk *root_dir* and process media files that have changed since last run."""
    file_batch: list[str] = []
    processed = 0
    skipped = 0

    for root, _dirs, files in os.walk(root_dir):
        for name in files:
            path = os.path.join(root, name)
            try:
                mtime = os.path.getmtime(path)
            except OSError:
                continue

            stored_mtime = get_modified_time(path)
            if stored_mtime == mtime:
                skipped += 1
                continue

            file_batch.append(path)
            processed += 1

            if len(file_batch) >= batch_size:
                process_batch(file_batch, batch_size)
                file_batch.clear()

    if file_batch:
        process_batch(file_batch, batch_size)

    logger.info(
        "Directory scan complete: %d processed, %d skipped (unchanged)",
        processed,
        skipped,
    )
