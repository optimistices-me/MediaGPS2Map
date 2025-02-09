
# MediaGPS2Map 🌍📸

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-2.0%2B-lightgrey)](https://flask.palletsprojects.com/)
[![Leaflet](https://img.shields.io/badge/Leaflet-1.7.1-brightgreen)](https://leafletjs.com/)

An interactive heatmap tool to visualize your photo and video geolocation data, supporting large datasets and high-performance rendering.

## Translation
[中文文档：README_zh.md](https://github.com/optimistices-me/MediaGPS2Map/blob/main/README_zh.md)

## Key Features

✅ Supports multiple media formats: HEIC/HEIF, JPG, PNG, MP4, MOV, and other mainstream photo and video formats  
✅ Intelligent GPS data parsing (photo + video location)  
✅ AMap API address parsing (automatic coordinate correction)  
✅ Dynamic heatmap rendering (supports testing with 100,000+ data points)  
✅ Responsive sidebar statistics panel  
✅ Customizable heatmap style adjustment  
✅ Spatiotemporal filtering (filter by time and map area)  
✅ Efficient mechanical hard drive storage optimization

## Quick Start

### Prerequisites
- Python 3.8+
- ExifTool ([Installation Guide](https://exiftool.org/install.html))
- AMap API Key ([Apply Here](https://lbs.amap.com/))

### Installation Steps

1. Clone the repository:
```bash
git clone https://github.com/optimistices-me/MediaGPS2Map.git
cd MediaGPS2Map
```
2. Install dependencies:
```bash
pip install flask requests
```
3. Configure `config.json`:

```json
{
    "AMAP_API_KEY": "Your AMap API key",
    "directories": [
        "Directory 1",
        "Directory 2"
    ],
    "batch_size": 200
}
```

### Running the Program
1. Initialize the database (first-time run):

```bash
python app_hdd.py
```
2. Start the service (for subsequent runs, use `--skip-db` to skip database initialization):

```bash
python app_hdd.py --skip-db
```
3. Access the webpage:

Open your browser and go to http://localhost:5000

## User Guide
1. Heatmap Interaction

- Drag the timeline to filter the date range
- Zoom the map to view heat distribution at different levels
- Click on a hotspot to view detailed media file information

2. Sidebar Features

- Real-time statistics of the data in the current view
- Display typical geographic location distribution
- Adjust heatmap parameters (radius/blurriness/opacity)

3. Performance Optimization

- When using mechanical hard drives, it is recommended to set `batch_size=200-1000`
- Zoom to the appropriate level to automatically aggregate data points
- Use WAL mode to enhance database concurrency performance

## Tech Stack
- Backend: Python + Flask + SQLite
- Frontend: Leaflet + Leaflet.heat
- Geoservices: AMap API
- Metadata Parsing: ExifTool

## Configuration Parameters
| Parameter      | Default Value | Description                           |
|----------------|---------------|---------------------------------------|
| batch_size     | 500           | File processing batch size (recommended 200-500 for mechanical hard drives) |
| AMAP_API_KEY   | Required      | AMap Web Service API Key              |
| directories    | Required      | List of media file storage paths     |

## Notes
❗ Do not expose the API key in `config.json`

❗ Processing a large number of files for the first time may take a long time (recommended to run in the background)

❗ Windows systems require ExifTool to be installed separately and added to the PATH

## License
MIT License © 2025 Optimistices-Me
