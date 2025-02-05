import os
import sqlite3
import subprocess
from datetime import datetime
import json
from flask import Flask, render_template, request
import argparse
import requests
import math


# 加载配置文件并处理路径
def load_config(config_file='myConfig.json'):
    with open(config_file, 'r', encoding='utf-8') as f:
        config = json.load(f)

    # 处理目录路径中的反斜杠
    config['directories'] = [directory.replace('\\', '/') for directory in config['directories']]
    return config


config = load_config()

AMAP_API_KEY = config['AMAP_API_KEY']
directories = config['directories']
batch_size = config['batch_size']

app = Flask(__name__)


# 添加命令行参数解析
def parse_args():
    parser = argparse.ArgumentParser(description='照片位置热图生成工具')
    parser.add_argument('--skip-db', action='store_true', help='跳过数据库生成')
    return parser.parse_args()


# 初始化数据库
def init_db():
    if os.path.exists('geo_data.db'):
        print("数据库已存在，跳过初始化。")
        return

    conn = sqlite3.connect('geo_data.db')
    c = conn.cursor()
    c.execute('PRAGMA journal_mode = WAL')  # 启用 WAL 模式
    c.execute('PRAGMA synchronous = NORMAL')  # 降低同步级别
    c.execute('''CREATE TABLE IF NOT EXISTS media
                 (path TEXT PRIMARY KEY,
                  lat REAL,
                  lon REAL,
                  timestamp DATETIME,
                  modified_time DATETIME)''')
    c.execute('CREATE INDEX IF NOT EXISTS timestamp_idx ON media (timestamp)')
    c.execute('CREATE INDEX IF NOT EXISTS lat_lon_idx ON media (lat, lon)')  # 添加经纬度索引
    conn.commit()
    conn.close()


# 使用exiftool批量提取元数据
def extract_metadata_batch(file_batch):
    cmd = ['exiftool', '-json', '-n', '-q',
           '-GPSLatitude', '-GPSLongitude', '-DateTimeOriginal',
           '-FileModifyDate', '-Track*']
    cmd += file_batch
    result = subprocess.run(cmd, capture_output=True, text=True)
    return json.loads(result.stdout)


def process_files(root_dir, batch_size=batch_size):  # 批次大小根据硬盘能力和文件路径长度权衡设置
    conn = sqlite3.connect('geo_data.db')
    c = conn.cursor()

    file_batch = []
    for root, dirs, files in os.walk(root_dir):
        for file in files:
            path = os.path.join(root, file)
            # 先检查数据库是否存在且未修改
            c.execute('SELECT modified_time FROM media WHERE path=?', (path,))
            row = c.fetchone()
            mtime = os.path.getmtime(path)
            if row and row[0] == mtime:
                continue

            file_batch.append(path)

            if len(file_batch) >= batch_size:
                process_batch(file_batch, conn)
                file_batch = []

    if file_batch:
        process_batch(file_batch, conn)

    conn.close()


def process_batch(file_batch, conn):
    metadata = extract_metadata_batch(file_batch)
    c = conn.cursor()
    insert_data = []

    for data in metadata:
        path = data.get('SourceFile')
        if not path:
            continue

        gps = data.get('GPSLatitude'), data.get('GPSLongitude')
        date_str = data.get('DateTimeOriginal') or data.get('FileModifyDate')

        if all(gps) and date_str:
            try:
                dt = datetime.strptime(date_str[:19], '%Y:%m:%d %H:%M:%S')
                insert_data.append((path, float(gps[0]), float(gps[1]), dt.isoformat(), os.path.getmtime(path)))
            except (ValueError, TypeError) as e:
                print(f"Error processing {path}: {e}")
        else:
            print(f"No GPS data found in {path}")

    if insert_data:
        c.executemany('''REPLACE INTO media VALUES (?,?,?,?,?)''', insert_data)
        conn.commit()
        print(f"Inserted {len(insert_data)} records")
    else:
        print("No valid records to insert")


# WGS-84 转 GCJ-02
def wgs84_to_gcj02(lat, lng):
    a = 6378245.0  # 长半轴
    ee = 0.00669342162296594323  # 扁率

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


# 获取地址信息
def get_address(lat, lng):
    # 将 WGS-84 坐标转换为 GCJ-02 坐标
    gcj_lat, gcj_lng = wgs84_to_gcj02(lat, lng)
    url = f'https://restapi.amap.com/v3/geocode/regeo?key={AMAP_API_KEY}&location={gcj_lng},{gcj_lat}'
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        if data['status'] == '1' and data['regeocode']:
            return data['regeocode']['formatted_address']
    return '未知地址'


@app.route('/data')
def get_data():
    bounds = request.args.get('bounds')
    start_time = request.args.get('start')
    end_time = request.args.get('end')

    conn = sqlite3.connect('geo_data.db')
    c = conn.cursor()

    query = '''SELECT path, lat, lon, timestamp FROM media'''
    conditions = []
    params = []

    if bounds:
        lat1, lng1, lat2, lng2 = map(float, bounds.split(','))
        conditions.append('(lat BETWEEN ? AND ? AND lon BETWEEN ? AND ?)')
        params += [min(lat1, lat2), max(lat1, lat2), min(lng1, lng2), max(lng1, lng2)]

    if start_time and end_time:
        conditions.append('(timestamp BETWEEN ? AND ?)')
        params += [start_time, end_time]

    if conditions:
        query += ' WHERE ' + ' AND '.join(conditions)

    c.execute(query, params)
    points = [{
        'path': row[0],
        'lat': row[1],
        'lng': row[2],
        'timestamp': row[3]
    } for row in c.fetchall()]
    conn.close()

    # 将地图划分为 5 个区域，每个区域选取一个典型位置
    regions = [
        (20, 110, 30, 120),  # 区域 1
        (30, 110, 40, 120),  # 区域 2
        (40, 110, 50, 120),  # 区域 3
        (20, 120, 30, 130),  # 区域 4
        (30, 120, 40, 130)  # 区域 5
    ]
    sample_points = []
    for region in regions:
        lat_min, lng_min, lat_max, lng_max = region
        points_in_region = [p for p in points if lat_min <= p['lat'] <= lat_max and lng_min <= p['lng'] <= lng_max]
        if points_in_region:
            sample_points.append(points_in_region[0])  # 选取第一个点作为典型位置

    # 获取典型位置的地址
    addresses = [get_address(p['lat'], p['lng']) for p in sample_points]

    return {
        'points': points,
        'addresses': addresses
    }


@app.route('/')
def index():
    return render_template('map.html')


if __name__ == '__main__':
    args = parse_args()

    if not args.skip_db:
        init_db()
        # 单线程顺序处理
        for directory in directories:
            process_files(directory)

    app.run(threaded=True, debug=True)
