"""Chinese holiday period detection.

Uses the ``chinese_calendar`` library when available, with a fallback
heuristic based on date proximity.  Holiday periods are extended or
trimmed based on photo-count patterns in the dataset.
"""

import logging
from datetime import date, timedelta
from typing import Any

from database import get_daily_counts

logger = logging.getLogger(__name__)

# Try to load chinese_calendar; fall back gracefully
try:
    from chinese_calendar import get_holiday_detail, get_holidays  # noqa: F811

    _HAS_CHINESE_CALENDAR = True
except ImportError:
    _HAS_CHINESE_CALENDAR = False
    logger.info("chinese_calendar not installed; using heuristic holiday detection")

    def get_holidays(start: date, end: date, **kwargs: Any) -> list[date]:  # type: ignore[misc]
        return []

    def get_holiday_detail(dt: date) -> tuple[bool, str | None]:  # type: ignore[misc]
        return False, None


NAME_MAP: dict[str, str] = {
    "New Year's Day": "元旦",
    "Spring Festival": "春节",
    "Tomb-sweeping Day": "清明节",
    "Tomb Sweeping Day": "清明节",
    "Labour Day": "劳动节",
    "Labor Day": "劳动节",
    "Dragon Boat Festival": "端午节",
    "Mid-autumn Festival": "中秋节",
    "Mid-Autumn Festival": "中秋节",
    "National Day": "国庆节",
    "New Year's Eve": "除夕",
    "Chinese New Year's Eve": "除夕",
}


def _get_chinese_holidays_by_year(year: int) -> list[tuple[date, date]]:
    """Return official holiday periods for *year* as (start, end) pairs."""
    if not _HAS_CHINESE_CALENDAR:
        return []

    try:
        holidays = get_holidays(date(year, 1, 1), date(year, 12, 31), include_weekends=False)
    except Exception as e:
        logger.warning("chinese_calendar failed for %d: %s", year, e)
        return []

    periods: list[tuple[date, date]] = []
    i = 0
    while i < len(holidays):
        start = holidays[i]
        end = start
        j = i + 1
        while j < len(holidays) and (holidays[j] - holidays[j - 1]) == timedelta(days=1):
            end = holidays[j]
            j += 1
        periods.append((start, end))
        i = j
    return periods


def _get_holiday_name(start: date, end: date) -> str:
    """Derive a Chinese holiday name, falling back to heuristics."""
    # Try official name from chinese_calendar
    if _HAS_CHINESE_CALENDAR:
        try:
            current = start
            while current <= end:
                is_hol, name = get_holiday_detail(current)
                if is_hol and name:
                    return NAME_MAP.get(name, name)
                current += timedelta(days=1)
        except Exception:
            pass

    # Fallback: guess from date range
    mid = start + (end - start) // 2
    m, d = mid.month, mid.day
    if (m == 1 and d <= 3) or (m == 12 and d >= 28):
        return "元旦"
    if (m == 1 and d >= 20) or m == 2:
        return "春节"
    if m == 4 and d <= 7:
        return "清明节"
    if m == 5 and d <= 5:
        return "劳动节"
    if m in (5, 6):
        return "端午节"
    if m == 9 and d >= 5:
        return "中秋节"
    if m == 10 and d <= 7:
        return "国庆节"
    return f"{m}月假期"


def detect_holiday_periods(
    daily_counts: dict[str, int] | None = None,
) -> list[dict[str, Any]]:
    """Detect holiday periods from photo-count data.

    Cross-references official Chinese holidays with daily photo volume
    to adjust start/end boundaries based on travel patterns.
    """
    if daily_counts is None:
        daily_counts = get_daily_counts()

    if not daily_counts:
        return []

    dates_sorted = sorted(daily_counts.keys())
    min_date = date.fromisoformat(dates_sorted[0])
    max_date = date.fromisoformat(dates_sorted[-1])

    # Gather official holiday periods for the data range
    all_periods: list[tuple[date, date]] = []
    for year in range(min_date.year, max_date.year + 1):
        all_periods.extend(_get_chinese_holidays_by_year(year))

    results: list[dict[str, Any]] = []

    for official_start, official_end in all_periods:
        # Adjust start: walk backwards while photo count is rising (travel outward)
        adj_start = official_start
        prev = daily_counts.get(official_start.isoformat(), 0)
        for d in range(1, 8):
            check = official_start - timedelta(days=d)
            check_str = check.isoformat()
            if check_str in daily_counts:
                cnt = daily_counts[check_str]
                if prev > 0 and cnt >= prev * 3:
                    adj_start = check
                    break
                prev = cnt

        # Adjust end: walk forwards while photo count is dropping (travel home)
        adj_end = official_end
        prev = daily_counts.get(official_end.isoformat(), 0)
        for d in range(1, 8):
            check = official_end + timedelta(days=d)
            check_str = check.isoformat()
            if check_str in daily_counts:
                cnt = daily_counts[check_str]
                if prev > 0 and cnt <= prev / 3:
                    adj_end = check - timedelta(days=1)
                    break
                prev = cnt

        # Sum photos in adjusted period
        photo_count = 0
        current = adj_start
        while current <= adj_end:
            photo_count += daily_counts.get(current.isoformat(), 0)
            current += timedelta(days=1)

        if photo_count > 0:
            name = _get_holiday_name(official_start, official_end)
            results.append(
                {
                    "name": name,
                    "start": adj_start.isoformat(),
                    "end": adj_end.isoformat(),
                    "photo_count": photo_count,
                    "official_start": official_start.isoformat(),
                    "official_end": official_end.isoformat(),
                }
            )

    results.sort(key=lambda x: x["start"])
    return results
