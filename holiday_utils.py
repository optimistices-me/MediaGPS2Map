from datetime import date, timedelta
from database import get_daily_counts


def _get_chinese_holidays_by_year(year):
    try:
        from chinese_calendar import get_holidays
        holidays = get_holidays(date(year, 1, 1), date(year, 12, 31), include_weekends=False)
    except Exception as e:
        print(f"Failed to get holidays for {year}: {e}")
        return []

    holiday_periods = []
    i = 0
    while i < len(holidays):
        start = holidays[i]
        end = start
        j = i + 1
        while j < len(holidays) and (holidays[j] - holidays[j - 1]) == timedelta(days=1):
            end = holidays[j]
            j += 1
        holiday_periods.append((start, end))
        i = j

    return holiday_periods


def detect_holiday_periods(daily_counts=None):
    if daily_counts is None:
        daily_counts = get_daily_counts()
    if not daily_counts:
        return []

    dates = sorted(daily_counts.keys())
    min_date = date.fromisoformat(dates[0])
    max_date = date.fromisoformat(dates[-1])

    all_holiday_periods = []
    for year in range(min_date.year, max_date.year + 1):
        all_holiday_periods.extend(_get_chinese_holidays_by_year(year))

    results = []
    for official_start, official_end in all_holiday_periods:
        adjusted_start = official_start
        adjusted_end = official_end

        prev_count = daily_counts.get(official_start.isoformat(), 0)
        for d in range(1, 8):
            check_date = official_start - timedelta(days=d)
            check_str = check_date.isoformat()
            if check_str in daily_counts:
                day_count = daily_counts[check_str]
                if prev_count > 0 and day_count >= prev_count * 3:
                    adjusted_start = check_date
                    break
                prev_count = day_count

        prev_count = daily_counts.get(official_end.isoformat(), 0)
        for d in range(1, 8):
            check_date = official_end + timedelta(days=d)
            check_str = check_date.isoformat()
            if check_str in daily_counts:
                day_count = daily_counts[check_str]
                if prev_count > 0 and day_count <= prev_count / 3:
                    adjusted_end = check_date - timedelta(days=1)
                    break
                prev_count = day_count

        photo_count = 0
        current = adjusted_start
        while current <= adjusted_end:
            current_str = current.isoformat()
            photo_count += daily_counts.get(current_str, 0)
            current += timedelta(days=1)

        if photo_count > 0:
            name = _get_holiday_name(official_start, official_end)
            results.append({
                'name': name,
                'start': adjusted_start.isoformat(),
                'end': adjusted_end.isoformat(),
                'photo_count': photo_count,
                'official_start': official_start.isoformat(),
                'official_end': official_end.isoformat(),
            })

    results.sort(key=lambda x: x['start'])
    return results


NAME_TRANSLATION = {
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


def _get_holiday_name(start, end):
    try:
        from chinese_calendar import get_holiday_detail
        current = start
        while current <= end:
            is_hol, name = get_holiday_detail(current)
            if is_hol and name:
                return NAME_TRANSLATION.get(name, name)
            current += timedelta(days=1)
    except Exception:
        pass

    mid = start + (end - start) // 2
    m = mid.month
    d = mid.day

    if m == 1 and d <= 3:
        return "元旦"
    if (m == 1 and d >= 20) or (m == 2):
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
    if m == 12 and d >= 28:
        return "元旦"

    return f"{m}月假期"
