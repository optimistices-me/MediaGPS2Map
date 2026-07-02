#!/usr/bin/env python3
"""GPS2Map — Interactive photo/video GPS heatmap and trajectory viewer.

Usage
-----
    python app.py              # Init DB, scan configured dirs, start server
    python app.py --skip-db    # Skip DB init and media scanning
    python app.py --add-data <dir>  # Incrementally process new media

Then open http://localhost:5000
"""

import argparse
import logging
import time
from typing import Any

import requests
from flask import Flask, jsonify, render_template, request
from flask_compress import Compress
from flask_cors import CORS

from config import load_config
from database import count_records, get_data, init_db
from exif_utils import process_files
from geo_utils import get_cached_address, _save_cache
from holiday_utils import detect_holiday_periods

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("gps2map")

# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

config = load_config()

app = Flask(__name__)
CORS(app)
Compress(app)

# ---------------------------------------------------------------------------
# Caches
# ---------------------------------------------------------------------------

DATA_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
DATA_CACHE_TTL: int = 5
MAX_CACHE_ENTRIES: int = 64

holiday_cache: list[dict[str, Any]] = []
holiday_cache_hash: int | None = None


def _get_data_cached(
    bounds: str,
    start_time: str,
    end_time: str,
    zoom: str,
) -> dict[str, Any]:
    """Data endpoint with simple time-based cache."""
    key = f"{bounds}|{start_time}|{end_time}|{zoom}"
    now = time.time()

    cached = DATA_CACHE.get(key)
    if cached and now - cached[0] < DATA_CACHE_TTL:
        return cached[1]

    skip_simplify = int(zoom) >= 9 if zoom else False
    points, addresses, total_count = get_data(
        bounds=bounds,
        start_time=start_time,
        end_time=end_time,
        skip_simplify=skip_simplify,
    )

    result = {"points": points, "addresses": addresses, "total_count": total_count}
    DATA_CACHE[key] = (now, result)

    # Evict oldest entry if cache is too large
    if len(DATA_CACHE) > MAX_CACHE_ENTRIES:
        oldest = min(DATA_CACHE, key=lambda k: DATA_CACHE[k][0])
        del DATA_CACHE[oldest]

    return result


def _get_holidays_cached() -> list[dict[str, Any]]:
    """Holiday endpoint with hash-based cache."""
    global holiday_cache, holiday_cache_hash
    from database import get_daily_counts

    daily = get_daily_counts()
    current_hash = hash(frozenset(daily.items()))
    if current_hash == holiday_cache_hash:
        return holiday_cache

    holiday_cache = detect_holiday_periods(daily)
    holiday_cache_hash = current_hash
    return holiday_cache


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="GPS2Map — 照片位置热图生成工具")
    parser.add_argument(
        "--skip-db", action="store_true", help="跳过数据库生成与媒体扫描，仅启动服务"
    )
    parser.add_argument(
        "--add-data",
        type=str,
        nargs="+",
        help="增量添加新文件目录（可指定多个）",
    )
    return parser.parse_args(argv)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.route("/data")
def route_data() -> dict[str, Any]:
    """Return GPS points for the current viewport / time range."""
    bounds = request.args.get("bounds", "")
    start_time = request.args.get("start", "")
    end_time = request.args.get("end", "")
    zoom = request.args.get("zoom", "0")
    return _get_data_cached(bounds, start_time, end_time, zoom)


@app.route("/api/regeo")
def amap_proxy() -> Any:
    """Reverse-geocode a single (lng, lat) via AMap."""
    lng = request.args.get("lng")
    lat = request.args.get("lat")
    if not lng or not lat:
        return jsonify({"status": "error", "message": "Missing lng/lat"}), 400

    cached = get_cached_address(float(lng), float(lat))
    if cached is not None:
        return jsonify({"status": "1", "regeocode": cached})

    # Fallback – direct API call (cached address will handle it now,
    # but keep this path for the first-uncached case)
    api_key = config.get("AMAP_API_KEY")
    if not api_key:
        return jsonify({"status": "error", "message": "API key not configured"}), 500

    gcj_url = (
        f"https://restapi.amap.com/v3/geocode/regeo"
        f"?key={api_key}&location={lng},{lat}"
    )
    try:
        resp = requests.get(gcj_url, timeout=5)
        return jsonify(resp.json())
    except requests.RequestException as e:
        logger.warning("AMap regeo proxy failed: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/holidays")
def api_holidays() -> dict[str, Any]:
    """Return detected holiday periods."""
    return {"holidays": _get_holidays_cached()}


@app.route("/")
def index() -> str:
    return render_template("map.html")


# ---------------------------------------------------------------------------
# Shutdown
# ---------------------------------------------------------------------------

import atexit

atexit.register(_save_cache)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    args = parse_args()

    if not args.skip_db:
        init_db()

    if args.add_data:
        for directory in args.add_data:
            logger.info("增量添加目录: %s", directory)
            process_files(directory)
    else:
        total = count_records()
        logger.info("当前数据库记录数: %d", total)

        if total == 0:
            logger.info("数据库为空，开始处理初始目录...")
            for directory in config.get("directories", []):
                logger.info("扫描: %s", directory)
                process_files(directory)
        else:
            logger.info("数据库已有数据，跳过扫描")

    logger.info("启动 Flask 服务器 → http://localhost:5000")
    app.run(threaded=True, debug=True, use_reloader=False)
