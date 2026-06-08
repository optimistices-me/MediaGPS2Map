import os
import subprocess
from datetime import datetime
import json
from database import get_modified_time, upsert_media

DEFAULT_BATCH_SIZE = 200


def extract_metadata_batch(file_batch):
    cmd = ['exiftool', '-json', '-n', '-q',
           '-GPSLatitude', '-GPSLongitude', '-DateTimeOriginal',
           '-FileModifyDate', '-GPSAltitude',
           '-Track*']
    cmd += file_batch
    result = subprocess.run(cmd, capture_output=True, text=True)
    return json.loads(result.stdout)


def process_batch(file_batch, batch_size=DEFAULT_BATCH_SIZE):
    metadata = extract_metadata_batch(file_batch)
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
                    altitude = None
                insert_data.append((path, float(gps[0]), float(gps[1]), altitude, dt.isoformat(), os.path.getmtime(path)))
            except (ValueError, TypeError) as e:
                print(f"Error processing {path}: {e}")
        else:
            print(f"No GPS data found in {path}")

    if insert_data:
        upsert_media(insert_data)
        print(f"Inserted {len(insert_data)} records")
    else:
        print("No valid records to insert")


def process_files(root_dir, batch_size=DEFAULT_BATCH_SIZE):
    file_batch = []
    for root, dirs, files in os.walk(root_dir):
        for file in files:
            path = os.path.join(root, file)
            mtime = os.path.getmtime(path)
            stored_mtime = get_modified_time(path)
            if stored_mtime == mtime:
                continue

            file_batch.append(path)

            if len(file_batch) >= batch_size:
                process_batch(file_batch, batch_size)
                file_batch = []

    if file_batch:
        process_batch(file_batch, batch_size)
