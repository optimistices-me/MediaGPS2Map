import os
import sqlite3
import subprocess
from datetime import datetime
import json
from flask import Flask, render_template, request
import argparse
import requests

app = Flask(__name__)

# 高德地图 API Key
AMAP_API_KEY = '8194eb1949ecf804aad037366e838ef1'

# 添加命令行参数解析
def parse_args():
    parser = argparse.ArgumentParser(description='照片位置热力图生成工具')
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

def process_files(root_dir, batch_size=500):  # 增加批次大小
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
                insert_data.append((
                    path,
                    float(gps[0]),
                    float(gps[1]),
                    dt.isoformat(),
                    os.path.getmtime(path)
                ))
            except (ValueError, TypeError) as e:
                print(f"Error processing {path}: {e}")
        else:
            print(f"No GPS data found in {path}")

    if insert_data:
        c.executemany('''REPLACE INTO media
                         VALUES (?,?,?,?,?)''', insert_data)
        conn.commit()
        print(f"Inserted {len(insert_data)} records")
    else:
        print("No valid records to insert")

# 获取地址信息
def get_address(lat, lng):
    url = f'https://restapi.amap.com/v3/geocode/regeo?key={AMAP_API_KEY}&location={lng},{lat}'
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        if data['status'] == '1' and data['regeocode']:
            return data['regeocode']['formatted_address']
    return '未知地址'

@app.route('/data')
def get_data():
    conn = sqlite3.connect('geo_data.db')
    c = conn.cursor()
    c.execute('SELECT path, lat, lon, timestamp FROM media')
    points = [{
        'path': row[0],
        'lat': row[1],
        'lng': row[2],
        'timestamp': row[3]
    } for row in c.fetchall()]
    conn.close()

    # 随机选取 5 个点获取地址
    sample_points = points[:5]  # 仅取前 5 个点作为示例
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
        directories = [
            r'H:\Media\K20.Camera', r'H:\Media\K20.Camera.Raw',
            r'H:\Media\Apple\iPhone2022', r'H:\Media\Apple\iPhone2023A',
            r'H:\Media\Apple\iPhone2023B', r'H:\Media\Apple\iPhone2024A',
            r'H:\Media\Apple\iPhone2024B', r'H:\Media\Apple\iPhone2024C',
            r'H:\Media\Apple\iPhone2024D', r'H:\Media\Apple\iPhone2025A',
            r'H:\Media\GoPro', r'H:\Media\Apple\iPad',
            r'H:\Media\OtherDevices', r'H:\Private\Rec'
        ]
        for directory in directories:
            process_files(directory)

    app.run(threaded=True, debug=True)