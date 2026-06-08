import argparse
import requests
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS

from config import load_config
from database import init_db, count_records, get_points, get_top_grids
from exif_utils import process_files
from holiday_utils import detect_holiday_periods

config = load_config()

app = Flask(__name__)
CORS(app)


def parse_args():
    parser = argparse.ArgumentParser(description='照片位置热图生成工具')
    parser.add_argument('--skip-db', action='store_true', help='跳过数据库生成')
    parser.add_argument('--add-data', type=str, nargs='+', help='增量添加新文件目录（可多个）')
    return parser.parse_args()


@app.route('/data')
def get_data():
    bounds = request.args.get('bounds')
    start_time = request.args.get('start')
    end_time = request.args.get('end')

    points = get_points(bounds=bounds, start_time=start_time, end_time=end_time)
    addresses = get_top_grids(bounds=bounds, start_time=start_time, end_time=end_time)

    return {
        'points': points,
        'addresses': addresses
    }


@app.route('/api/regeo')
def amap_proxy():
    lng = request.args.get('lng')
    lat = request.args.get('lat')

    api_key = config['AMAP_API_KEY']
    url = f'https://restapi.amap.com/v3/geocode/regeo?key={api_key}&location={lng},{lat}'

    try:
        response = requests.get(url, timeout=3)
        return jsonify(response.json())
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/holidays')
def api_holidays():
    holidays = detect_holiday_periods()
    return jsonify({'holidays': holidays})


@app.route('/')
def index():
    return render_template('map.html')


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
