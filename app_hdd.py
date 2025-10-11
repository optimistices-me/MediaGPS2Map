import os
import sqlite3
import subprocess
from datetime import datetime
import json
from flask import Flask, render_template, request, jsonify
import argparse
import requests
import math

# 缓存反向地理编码结果，减少外部API请求
address_cache = {}

# 加载配置文件并处理路径
def load_config(config_file='config.json'):
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
    parser.add_argument('--add-data', type=str, help='增量添加新文件目录')
    return parser.parse_args()


# 初始化数据库
def init_db():
    conn = sqlite3.connect('geo_data.db')
    c = conn.cursor()
    c.execute('PRAGMA journal_mode = WAL')  # 启用 WAL 模式
    c.execute('PRAGMA synchronous = NORMAL')  # 降低同步级别
    c.execute('''CREATE TABLE IF NOT EXISTS media
                 (path TEXT PRIMARY KEY,
                  lat REAL,
                  lon REAL,
                  altitude REAL, 
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
           '-FileModifyDate', '-GPSAltitude',
           '-Track*']
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
        altitude = data.get('GPSAltitude')
        date_str = data.get('DateTimeOriginal') or data.get('FileModifyDate')

        if all(gps) and date_str:
            try:
                dt = datetime.strptime(date_str[:19], '%Y:%m:%d %H:%M:%S')
                if altitude and str(altitude).replace('-', '').replace('.', '').isdigit():
                    altitude = float(altitude)
                else:
                    altitude = None  # 如果海拔信息无效，设为NULL
                insert_data.append((path, float(gps[0]), float(gps[1]), altitude, dt.isoformat(), os.path.getmtime(path)))
            except (ValueError, TypeError) as e:
                print(f"Error processing {path}: {e}")
        else:
            print(f"No GPS data found in {path}")

    if insert_data:
        c.executemany('''
                    INSERT OR REPLACE INTO media 
                    (path, lat, lon, altitude, timestamp, modified_time) 
                    VALUES (?,?,?,?,?,?)
                ''', insert_data)
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
    try:
        response = requests.get(url, timeout=3)
        if response.status_code == 200:
            data = response.json()
            if data['status'] == '1' and data['regeocode']:
                addr = data['regeocode']['addressComponent']
                # 组合省+市+区
                province = addr['province']
                city = addr.get('city', province)  # 处理直辖市
                district = addr['district']
                return f"{province}{city}{district}"
    except Exception as e:
        print(f"地址查询失败: {e}")
    return '未知地址'


@app.route('/data')
def get_data():
    bounds = request.args.get('bounds')
    start_time = request.args.get('start')
    end_time = request.args.get('end')

    conn = sqlite3.connect('geo_data.db')
    c = conn.cursor()

    query = '''SELECT path, lat, lon, altitude, timestamp FROM media'''
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
    query += ' ORDER BY timestamp ASC'  # 排序

    c.execute(query, params)
    points = [{
        'path': row[0],
        'lat': row[1],
        'lng': row[2],
        'altitude': row[3],  # 新增海拔
        'timestamp': row[4],
        'sort_time': row[4]
    } for row in c.fetchall()]

    # 为每个点添加 address 字段（县/区），优先使用缓存
    for point in points:
        key = f"{point['lat']},{point['lng']}"
        if key in address_cache:
            point['address'] = address_cache[key]
        else:
            addr = get_address(point['lat'], point['lng'])
            address_cache[key] = addr
            point['address'] = addr

    # 使用网格聚合查询高频位置（0.01度约1公里精度）
    grid_query = '''
        SELECT ROUND(lat, 1) as lat_grid,
               ROUND(lon, 1) as lon_grid,
               COUNT(*) as count
        FROM media
        GROUP BY lat_grid, lon_grid
        ORDER BY count DESC
        LIMIT 5
    '''
    c.execute(grid_query)
    top_grids = c.fetchall()

    # 获取每个网格的样本点
    address_points = []
    for grid in top_grids:
        point_query = '''
            SELECT lat, lon FROM media
            WHERE ROUND(lat, 1) = ? 
              AND ROUND(lon, 1) = ?
            LIMIT 1
        '''
        c.execute(point_query, (grid[0], grid[1]))
        point = c.fetchone()
        if point:
            address_points.append({'lat': point[0], 'lng': point[1]})

    # 获取县级地址（修改后的地址解析函数）
    addresses = []
    for p in address_points:
        addr = get_address(p['lat'], p['lng'])
        # 提取县级信息
        if '省' in addr and '市' in addr:
            parts = addr.split('省', 1)[1].split('市', 1)
            addresses.append(f"{parts[0]}市{parts[1].split('区', 1)[0]}区")
        elif '市' in addr:
            parts = addr.split('市', 1)
            addresses.append(f"{parts[0]}市{parts[1].split('区', 1)[0]}区")
        else:
            addresses.append(addr.split('区', 1)[0] + '区')

    return {
        'points': points,
        'addresses': addresses[:5]  # 确保最多返回5个
    }


# 新增反向代理接口
@app.route('/api/regeo')
def amap_proxy():
    lng = request.args.get('lng')
    lat = request.args.get('lat')

    # 从配置文件获取密钥
    api_key = config['AMAP_API_KEY']

    # 构造高德API请求
    url = f'https://restapi.amap.com/v3/geocode/regeo?key={api_key}&location={lng},{lat}'

    try:
        response = requests.get(url, timeout=3)
        return jsonify(response.json())
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# 确保CORS配置
from flask_cors import CORS

CORS(app)  # 允许跨域请求

@app.route('/')
def index():
    return render_template('map.html')


if __name__ == '__main__':
    args = parse_args()

    # 添加重载机制检查
    if os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
        if not args.skip_db:
            init_db()
            if args.add_data:
                print(f"正在增量添加目录：{args.add_data}")
                process_files(args.add_data)
            else:
                with sqlite3.connect('geo_data.db') as conn:
                    c = conn.cursor()
                    c.execute('SELECT COUNT(*) FROM media')
                    count = c.fetchone()[0]

                if count == 0:
                    print("检测到空数据库，开始处理初始目录...")
                    for directory in directories:
                        process_files(directory)
                else:
                    print("数据库已有数据，跳过初始目录处理")

    if not args.skip_db:
        init_db()
        if args.add_data:
            print(f"正在增量添加目录：{args.add_data}")
            process_files(args.add_data)
        else:
            # 增强型数据库检查逻辑
            with sqlite3.connect('geo_data.db') as conn:
                c = conn.cursor()
                c.execute('SELECT COUNT(*) FROM media')
                count = c.fetchone()[0]
                print(f"当前数据库记录数：{count}")  # 添加调试信息

            if count == 0:
                print("检测到空数据库，开始处理初始目录...")
                for directory in directories:
                    print(f"📁 正在扫描初始目录：{directory}")
                    process_files(directory)
            else:
                print("数据库已有数据，跳过初始目录处理")

    print("🚀 启动Flask服务器")
    # 调整服务器启动参数
    app.run(
        threaded=True,
        debug=True,
        use_reloader=False  # 关闭自动重载功能
    )