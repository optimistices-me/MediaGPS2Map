"""Coordinate conversion and reverse-geocoding helpers.

Provides WGS-84 → GCJ-02 transformation (required by Chinese map
services) and AMap reverse-geocoding with a local JSON cache.
"""

import json
import logging
import math
import os
from typing import Any

import requests

from config import load_config

logger = logging.getLogger(__name__)

CACHE_FILE = "address_cache.json"
_cache: dict[str, Any] = {}

config = load_config()
AMAP_API_KEY: str | None = config.get("AMAP_API_KEY")

# ---------------------------------------------------------------------------
# Cache persistence
# ---------------------------------------------------------------------------


def _load_cache() -> None:
    global _cache
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                _cache = json.load(f)
        except (json.JSONDecodeError, OSError):
            _cache = {}


def _save_cache() -> None:
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(_cache, f, ensure_ascii=False)
    except OSError as e:
        logger.warning("Failed to write address cache: %s", e)


_load_cache()


# ---------------------------------------------------------------------------
# WGS-84 → GCJ-02
# ---------------------------------------------------------------------------

_A: float = 6378245.0
_EE: float = 0.00669342162296594323


def wgs84_to_gcj02(lat: float, lng: float) -> tuple[float, float]:
    """Convert WGS-84 coordinates to GCJ-02 (Chinese coordinate system)."""

    def _transform_lat(x: float, y: float) -> float:
        ret = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * math.sqrt(abs(x))
        ret += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
        ret += (20.0 * math.sin(y * math.pi) + 40.0 * math.sin(y / 3.0 * math.pi)) * 2.0 / 3.0
        ret += (160.0 * math.sin(y / 12.0 * math.pi) + 320 * math.sin(y * math.pi / 30.0)) * 2.0 / 3.0
        return ret

    def _transform_lng(x: float, y: float) -> float:
        ret = 300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * math.sqrt(abs(x))
        ret += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
        ret += (20.0 * math.sin(x * math.pi) + 40.0 * math.sin(x / 3.0 * math.pi)) * 2.0 / 3.0
        ret += (150.0 * math.sin(x / 12.0 * math.pi) + 300.0 * math.sin(x / 30.0 * math.pi)) * 2.0 / 3.0
        return ret

    d_lat = _transform_lat(lng - 105.0, lat - 35.0)
    d_lng = _transform_lng(lng - 105.0, lat - 35.0)
    rad_lat = lat / 180.0 * math.pi
    magic = math.sin(rad_lat)
    magic = 1 - _EE * magic * magic
    sqrt_magic = math.sqrt(magic)

    d_lat = (d_lat * 180.0) / ((_A * (1 - _EE)) / (magic * sqrt_magic) * math.pi)
    d_lng = (d_lng * 180.0) / (_A / sqrt_magic * math.cos(rad_lat) * math.pi)

    return lat + d_lat, lng + d_lng


# ---------------------------------------------------------------------------
# Reverse geocoding via AMap API
# ---------------------------------------------------------------------------


def _amap_regeo(lng: float, lat: float) -> dict[str, Any] | None:
    """Call AMap reverse-geocode API and return the raw response."""
    if not AMAP_API_KEY:
        logger.warning("AMAP_API_KEY not configured — cannot reverse-geocode")
        return None

    gcj_lat, gcj_lng = wgs84_to_gcj02(lat, lng)
    url = (
        f"https://restapi.amap.com/v3/geocode/regeo"
        f"?key={AMAP_API_KEY}&location={gcj_lng},{gcj_lat}"
    )
    try:
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") == "1" and data.get("regeocode"):
            return data["regeocode"]
    except requests.RequestException as e:
        logger.warning("AMap regeo failed: %s", e)
    return None


def get_cached_address(lng: float, lat: float) -> Any:
    """Return cached address for (lng, lat), or fetch and cache it."""
    key = f"{float(lat):.4f},{float(lng):.4f}"
    cached = _cache.get(key)
    if cached is not None:
        return cached

    result = _amap_regeo(lng, lat)
    if result is not None:
        _cache[key] = result
        if len(_cache) % 20 == 0:
            _save_cache()
    return result


def get_address(lat: float, lng: float) -> str:
    """Return a compact address string, e.g. '北京市海淀区'."""
    key = f"{lat:.4f},{lng:.4f}"
    cached = _cache.get(key)
    if cached is not None and isinstance(cached, str):
        return cached

    regeo = _amap_regeo(lng, lat)
    if regeo:
        comp = regeo.get("addressComponent", {})
        province = comp.get("province", "")
        city = comp.get("city") or province
        district = comp.get("district", "")
        address = f"{province}{city}{district}"
        _cache[key] = address
        return address

    return "未知地址"
