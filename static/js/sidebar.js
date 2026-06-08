let isTrackLocked = false;
let freqLocationsTimeout = null;

function updateSidebar(data) {
    if (freqLocationsTimeout) {
        clearTimeout(freqLocationsTimeout);
    }
    freqLocationsTimeout = setTimeout(() => {
        const points = data.points;
        const fileCount = points.length;
        const timestamps = points.map(p => new Date(p.timestamp).getTime());
        let minTimestamp = Infinity;
        let maxTimestamp = -Infinity;
        for (let t of timestamps) {
            if (t < minTimestamp) minTimestamp = t;
            if (t > maxTimestamp) maxTimestamp = t;
        }
        const minTime = new Date(minTimestamp).toLocaleString();
        const maxTime = new Date(maxTimestamp).toLocaleString();
        document.getElementById('file-count').textContent = fileCount;
        document.getElementById('time-range').textContent = `${minTime} - ${maxTime}`;

        analyzeFrequentLocations(points);
    }, 300);
}

function analyzeFrequentLocations(points) {
    if (points.length === 0) {
        document.getElementById('sample-locations').innerHTML = '<li>当前区域无数据</li>';
        return;
    }

    const bounds = map.getBounds();

    const visiblePoints = points.filter(point =>
        bounds.contains([point.lat, point.lng])
    );

    if (visiblePoints.length === 0) {
        document.getElementById('sample-locations').innerHTML = '<li>当前显示区域无数据</li>';
        return;
    }

    const gridSize = 0.005;
    const locationClusters = {};

    visiblePoints.forEach(point => {
        const latKey = Math.floor(point.lat / gridSize) * gridSize;
        const lngKey = Math.floor(point.lng / gridSize) * gridSize;
        const key = `${latKey.toFixed(6)},${lngKey.toFixed(6)}`;

        if (!locationClusters[key]) {
            locationClusters[key] = {
                lat: latKey + gridSize / 2,
                lng: lngKey + gridSize / 2,
                count: 0,
                points: []
            };
        }
        locationClusters[key].count++;
        locationClusters[key].points.push(point);
    });

    const topLocations = Object.values(locationClusters)
        .sort((a, b) => b.count - a.count)
        .slice(0, 5);

    const sampleLocations = document.getElementById('sample-locations');
    sampleLocations.innerHTML = '<li>正在分析常去位置...</li>';

    Promise.all(topLocations.map(async (location, index) => {
        try {
            const [gcjLat, gcjLng] = wgs84ToGcj02(location.lat, location.lng);
            const response = await fetch(`/api/regeo?lng=${gcjLng}&lat=${gcjLat}`);
            const data = await response.json();

            let address = `位置 ${index + 1}`;
            if (data.status === '1' && data.regeocode) {
                address = data.regeocode.formatted_address || `经纬度: ${location.lat.toFixed(4)}, ${location.lng.toFixed(4)}`;
                if (address.length > 30) {
                    const parts = address.split(/[区县市]/);
                    address = parts.length > 1 ? parts[parts.length - 1] : address.substring(0, 30) + '...';
                }
            }

            return {
                address: address,
                count: location.count,
                index: index
            };
        } catch (error) {
            console.error('地址查询失败:', error);
            return {
                address: `经纬度: ${location.lat.toFixed(4)}, ${location.lng.toFixed(4)}`,
                count: location.count,
                index: index
            };
        }
    })).then(results => {
        results.sort((a, b) => a.index - b.index);

        const locationHtml = results.map(result =>
            `<li>${result.address} <span style="color: #666;">(${result.count}次)</span></li>`
        ).join('');

        sampleLocations.innerHTML = locationHtml || '<li>未找到常去位置</li>';
    }).catch(error => {
        console.error('常去位置分析失败:', error);
        sampleLocations.innerHTML = '<li>常去位置分析失败</li>';
    });
}

function initSidebar() {
    document.getElementById('lockTrackSwitch').addEventListener('change', function (e) {
        isTrackLocked = e.target.checked;
    });

    document.getElementById('animationSwitch').addEventListener('change', function (e) {
        isAnimationPlaying = e.target.checked;
        if (isAnimationPlaying) {
            startAnimation();
        } else {
            stopAnimation();
        }
    });

    document.getElementById('animationSpeed').addEventListener('input', function (e) {
        document.getElementById('animationSpeed-value').value = e.target.value;
        if (isAnimationPlaying) {
            stopAnimation();
            startAnimation();
        }
    });

    document.getElementById('animationSpeed-value').addEventListener('input', function (e) {
        document.getElementById('animationSpeed').value = e.target.value;
        if (isAnimationPlaying) {
            stopAnimation();
            startAnimation();
        }
    });
}
