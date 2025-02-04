# 照片视频地理位置热图制作 MediaGPS2Map  🌍📸


[![Python](https://img.shields.io/badge/Python-3.8%2B-blue)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-2.0%2B-lightgrey)](https://flask.palletsprojects.com/)
[![Leaflet](https://img.shields.io/badge/Leaflet-1.7.1-brightgreen)](https://leafletjs.com/)

可视化您的照片和视频地理位置数据的交互式热图工具，支持大规模数据集处理和高性能渲染。

## 主要功能

✅ 支持多种媒体格式：HEIC/HEIF, JPG, PNG, MP4, MOV等主流照片视频格式  
✅ 智能GPS数据解析（照片+视频位置）  
✅ 高德地图API地址解析（自动坐标纠偏）  
✅ 动态热图渲染（测试支持10万+数据点）  
✅ 响应式侧边栏统计面板  
✅ 自定义热图样式调节  
✅ 时空过滤（按时间和地图区域筛选）  
✅ 高效机械硬盘存储优化

## 快速开始

### 前置要求
- Python 3.8+
- ExifTool ([安装指南](https://exiftool.org/install.html))
- 高德地图API密钥 ([申请地址](https://lbs.amap.com/))

### 安装步骤

1. 克隆仓库：
bash
git clone https://github.com/optimistices-me/MediaGPS2Map.git
cd MediaGPS2Map

2. 安装依赖：
bash
pip install flask requests

3. 配置config.json：

json
{
    "AMAP_API_KEY": "您的高德API密钥",
    "directories": [
        "目录1",
        "目录2"
    ],
    "batch_size": 200
}

### 运行程序
1. 初始化数据库（首次运行）：

bash
python app_hdd.py

2. 启动服务（后续运行可加--skip-db跳过数据库初始化）：

bash
python app_hdd.py --skip-db

3. 访问网页： 

打开浏览器访问 http://localhost:5000

## 使用指南
1. 热图交互

- 拖动时间轴筛选日期范围

- 缩放地图查看不同层级的热力分布

- 点击热点查看媒体文件详细信息

2. 侧边栏功能

- 实时统计当前视图内的数据

- 显示典型地理位置分布

- 调节热图参数（半径/模糊度/透明度）

3. 性能优化

- 使用机械硬盘时建议设置batch_size=200-1000

- 缩放至合适层级自动聚合数据点

- 采用WAL模式提升数据库并发性能

## 技术栈
- 后端: Python + Flask + SQLite

- 前端: Leaflet + Leaflet.heat

- 地理服务: 高德地图API

- 元数据解析: ExifTool

## 配置参数
| 参数项          | 默认值 | 说明                      |
|--------------|-----|-------------------------|
| batch_size   | 500 | 文件处理批次大小（机械硬盘建议200-500） |
| AMAP_API_KEY | 必填  | 高德地图Web服务API密钥          |
|directories| 必填| 媒体文件存储路径列表              |
## 注意事项
❗ 请勿公开config.json中的API密钥

❗ 首次处理大量文件可能需要较长时间（建议后台运行）

❗ Windows系统需要单独安装ExifTool并添加PATH

## 许可证
MIT License © 2025 Optimistices-Me