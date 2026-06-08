import math
import requests
from config import load_config

config = load_config()
AMAP_API_KEY = config['AMAP_API_KEY']

address_cache = {}


def wgs84_to_gcj02(lat, lng):
    a = 6378245.0
    ee = 0.00669342162296594323

    def transform_lat(x, y):
        ret = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * math.sqrt(abs(x))
        ret += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
        ret += (20.0 * math.sin(y * math.pi) + 40.0 * math.sin(y / 3.0 * math.pi)) * 2.0 / 3.0
        ret += (160.0 * math.sin(y / 12.0 * math.pi) + 320 * math.sin(y * math.pi / 30.0)) * 2.0 / 3.0
        return ret

    def transform_lng(x, y):
        ret = 300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * math.sqrt(abs(x))
        ret += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
        ret += (20.0 * math.sin(x * math.pi) + 40.0 * math.sin(x / 3.0 * math.pi)) * 2.0 / 3.0
        ret += (150.0 * math.sin(x / 12.0 * math.pi) + 300.0 * math.sin(x / 30.0 * math.pi)) * 2.0 / 3.0
        return ret

    d_lat = transform_lat(lng - 105.0, lat - 35.0)
    d_lng = transform_lng(lng - 105.0, lat - 35.0)
    rad_lat = lat / 180.0 * math.pi
    magic = math.sin(rad_lat)
    magic = 1 - ee * magic * magic
    sqrt_magic = math.sqrt(magic)
    d_lat = (d_lat * 180.0) / ((a * (1 - ee)) / (magic * sqrt_magic) * math.pi)
    d_lng = (d_lng * 180.0) / (a / sqrt_magic * math.cos(rad_lat) * math.pi)
    gcj_lat = lat + d_lat
    gcj_lng = lng + d_lng
    return gcj_lat, gcj_lng


def get_address(lat, lng):
    cache_key = f"{lat:.4f},{lng:.4f}"
    if cache_key in address_cache:
        return address_cache[cache_key]

    gcj_lat, gcj_lng = wgs84_to_gcj02(lat, lng)
    url = f'https://restapi.amap.com/v3/geocode/regeo?key={AMAP_API_KEY}&location={gcj_lng},{gcj_lat}'
    try:
        response = requests.get(url, timeout=8)
        response.raise_for_status()
        data = response.json()

        if data.get('status') == '1' and data.get('regeocode'):
            addr = data['regeocode'].get('addressComponent', {})
            province = addr.get('province', '')
            city = addr.get('city') or province
            district = addr.get('district', '')
            result = f"{province}{city}{district}"
            address_cache[cache_key] = result
            return result
    except Exception as e:
        print(f"地址查询失败: {e}")

    return '未知地址'
