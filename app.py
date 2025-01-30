import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor
import subprocess
from datetime import datetime
import json
from flask import Flask, render_template, request

app = Flask(__name__)


# 初始化数据库
def init_db():
    conn = sqlite3.connect('geo_data.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS media
                 (path TEXT PRIMARY KEY,
                  lat REAL,
                  lon REAL,
                  timestamp DATETIME,
                  modified_time DATETIME)''')
    c.execute('CREATE INDEX IF NOT EXISTS timestamp_idx ON media (timestamp)')
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


def process_files(root_dir, batch_size=100):
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


@app.route('/data')
def get_data():
    start = request.args.get('start')
    end = request.args.get('end')

    conn = sqlite3.connect('geo_data.db')
    c = conn.cursor()

    if start and end:
        # 如果有时间范围参数，筛选数据
        query = '''SELECT lat, lon FROM media
                   WHERE timestamp BETWEEN ? AND ?'''
        params = (start, end)
    else:
        # 如果没有时间范围参数，返回所有数据
        query = 'SELECT lat, lon FROM media'
        params = ()

    c.execute(query, params)
    points = [{'lat': row[0], 'lng': row[1]} for row in c.fetchall()]
    conn.close()

    # 调试输出
    print(f"Query: start={start}, end={end}, points found: {len(points)}")

    return {'points': points}


@app.route('/')
def index():
    return render_template('map.html')


if __name__ == '__main__':
    init_db()

    # 使用线程池并行处理目录
    with ThreadPoolExecutor(max_workers=4) as executor:  # 机械硬盘建议4线程
        # 假设需要扫描的目录列表
        directories = ['test', 'test2']
        for directory in directories:
            executor.submit(process_files, directory)

    app.run(threaded=True)
    app.run(debug=True)