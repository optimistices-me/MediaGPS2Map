import sqlite3
import os

DB_PATH = 'geo_data.db'
_max_points = 5000


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.execute('PRAGMA journal_mode = WAL')
    conn.execute('PRAGMA synchronous = NORMAL')
    conn.execute('PRAGMA cache_size = -8000')
    return conn


def init_db():
    conn = get_connection()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS media
                 (path TEXT PRIMARY KEY,
                  lat REAL,
                  lon REAL,
                  altitude REAL,
                  timestamp DATETIME,
                  modified_time DATETIME)''')
    c.execute('CREATE INDEX IF NOT EXISTS timestamp_idx ON media (timestamp)')
    c.execute('CREATE INDEX IF NOT EXISTS lat_lon_idx ON media (lat, lon)')
    conn.commit()
    conn.close()


def count_records():
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM media')
    count = c.fetchone()[0]
    conn.close()
    return count


def get_data(bounds=None, start_time=None, end_time=None, skip_simplify=False):
    conn = get_connection()
    c = conn.cursor()

    conditions = []
    params = []

    if bounds:
        lat1, lng1, lat2, lng2 = map(float, bounds.split(','))
        conditions.append('(lat BETWEEN ? AND ? AND lon BETWEEN ? AND ?)')
        params += [min(lat1, lat2), max(lat1, lat2), min(lng1, lng2), max(lng1, lng2)]

    if start_time and end_time:
        conditions.append('(timestamp BETWEEN ? AND ?)')
        params += [start_time, end_time]

    where_clause = ''
    if conditions:
        where_clause = ' WHERE ' + ' AND '.join(conditions)

    query = f'SELECT path, lat, lon, altitude, timestamp FROM media{where_clause} ORDER BY timestamp ASC'
    c.execute(query, params)
    rows = c.fetchall()

    total_count = len(rows)

    if not skip_simplify and total_count > _max_points:
        step = max(1, total_count // _max_points)
        rows = rows[::step]

    points = [{
        'path': row[0],
        'lat': row[1],
        'lng': row[2],
        'altitude': row[3],
        'timestamp': row[4],
        'sort_time': row[4]
    } for row in rows]

    grid_query = f'''
        SELECT ROUND(lat, 1) as lat_grid,
            ROUND(lon, 1) as lon_grid,
            COUNT(*) as count
        FROM media{where_clause}
        GROUP BY lat_grid, lon_grid
        ORDER BY count DESC
        LIMIT 5
    '''
    c.execute(grid_query, params)
    top_grids = c.fetchall()

    addresses = [{
        'lat': row[0],
        'lng': row[1],
        'count': row[2]
    } for row in top_grids]

    conn.close()
    return points, addresses, total_count


def get_modified_time(path):
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT modified_time FROM media WHERE path=?', (path,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None


def upsert_media(insert_data):
    conn = get_connection()
    c = conn.cursor()
    c.executemany('''
        INSERT OR REPLACE INTO media
        (path, lat, lon, altitude, timestamp, modified_time)
        VALUES (?,?,?,?,?,?)
    ''', insert_data)
    conn.commit()
    conn.close()


def get_all_timestamps():
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT DISTINCT DATE(timestamp) as d FROM media ORDER BY d')
    result = [row[0] for row in c.fetchall()]
    conn.close()
    return result


def get_daily_counts():
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        SELECT DATE(timestamp) as d, COUNT(*) as cnt
        FROM media
        GROUP BY d
        ORDER BY d
    ''')
    result = {row[0]: row[1] for row in c.fetchall()}
    conn.close()
    return result
