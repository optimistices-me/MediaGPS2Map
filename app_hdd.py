import argparse
import time
import atexit
import requests
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from flask_compress import Compress

from config import load_config
from database import init_db, count_records, get_data
from exif_utils import process_files
from holiday_utils import detect_holiday_periods
from geo_utils import get_cached_address, address_cache, _save_cache

config = load_config()

app = Flask(__name__)
CORS(app)
Compress(app)

data_cache = {}
DATA_CACHE_TTL = 5


def _get_data_cached(bounds, start_time, end_time, zoom):
    cache_key = f"{bounds}|{start_time}|{end_time}|{zoom}"
    now = time.time()
    if cache_key in data_cache:
        ts, result = data_cache[cache_key]
        if now - ts < DATA_CACHE_TTL:
            return result
    skip_simplify = int(zoom) >= 9 if zoom else False
    points, addresses, total_count = get_data(bounds=bounds, start_time=start_time, end_time=end_time, skip_simplify=skip_simplify)
    result = {'points': points, 'addresses': addresses, 'total_count': total_count}
    data_cache[cache_key] = (now, result)
    if len(data_cache) > 64:
        oldest = min(data_cache, key=lambda k: data_cache[k][0])
        del data_cache[oldest]
    return result


holiday_cache = {}
holiday_cache_hash = None


def _get_holidays_cached():
    global holiday_cache, holiday_cache_hash
    from database import get_daily_counts
    daily_counts = get_daily_counts()
    current_hash = hash(frozenset(daily_counts.items()))
    if current_hash == holiday_cache_hash:
        return holiday_cache
    result = detect_holiday_periods(daily_counts)
    holiday_cache = result
    holiday_cache_hash = current_hash
    return result


def parse_args():
    parser = argparse.ArgumentParser(description='照片位置热图生成工具')
    parser.add_argument('--skip-db', action='store_true', help='跳过数据库生成')
    parser.add_argument('--add-data', type=str, nargs='+', help='增量添加新文件目录（可多个）')
    return parser.parse_args()


@app.route('/data')
def route_data():
    bounds = request.args.get('bounds')
    start_time = request.args.get('start')
    end_time = request.args.get('end')
    zoom = request.args.get('zoom')
    return _get_data_cached(bounds, start_time, end_time, zoom)


@app.route('/api/regeo')
def amap_proxy():
    lng = request.args.get('lng')
    lat = request.args.get('lat')

    cached = get_cached_address(lng, lat)
    if cached is not None:
        return jsonify({'status': '1', 'regeocode': cached})

    api_key = config['AMAP_API_KEY']
    url = f'https://restapi.amap.com/v3/geocode/regeo?key={api_key}&location={lng},{lat}'

    try:
        response = requests.get(url, timeout=3)
        return jsonify(response.json())
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/holidays')
def api_holidays():
    return jsonify({'holidays': _get_holidays_cached()})


@app.route('/')
def index():
    return render_template('map.html')


atexit.register(_save_cache)


if __name__ == '__main__':
    args = parse_args()

    if not args.skip_db:
        init_db()

    if args.add_data:
        for directory in args.add_data:
            print(f"正在增量添加目录：{directory}")
            process_files(directory)
    else:
        current_count = count_records()
        print(f"当前数据库记录数：{current_count}")

        if current_count == 0:
            print("检测到空数据库，开始处理初始目录...")
            for directory in config['directories']:
                print(f"正在扫描初始目录：{directory}")
                process_files(directory)
        else:
            print("数据库已有数据，跳过初始目录处理")

    print("启动Flask服务器")
    app.run(
        threaded=True,
        debug=True,
        use_reloader=False
    )
