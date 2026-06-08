let currentPoints = [];
let debounceTimeout = null;
let map;

function aggregatePoints(points, gridSize) {
    const aggregated = {};
    points.forEach(point => {
        const latKey = Math.floor(point.lat / gridSize) * gridSize;
        const lngKey = Math.floor(point.lng / gridSize) * gridSize;
        const key = `${latKey},${lngKey}`;

        if (!aggregated[key]) {
            aggregated[key] = { lat: point.lat, lng: point.lng, count: 0 };
        }
        aggregated[key].count++;
    });
    return Object.values(aggregated);
}

function loadDataForBounds(bounds, shouldUpdateTimeRange) {
    if (isTrackLocked) return;

    const params = new URLSearchParams({
        bounds: `${bounds.getSouth()},${bounds.getWest()},${bounds.getNorth()},${bounds.getEast()}`,
        start: document.getElementById('start-time').value,
        end: document.getElementById('end-time').value
    });

    fetch(`/data?${params}`)
        .then(response => response.json())
        .then(data => {
            currentPoints = data.points;
            if (shouldUpdateTimeRange) {
                initTimeRange();
            }
            refreshAllLayers(currentPoints);
            updateSidebar(data);
        });
}

map = L.map('map').setView([30, 120], 3);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);

map.on('moveend', function () {
    if (debounceTimeout) {
        clearTimeout(debounceTimeout);
    }
    debounceTimeout = setTimeout(() => {
        if (!isTrackLocked) {
            const bounds = map.getBounds();
            loadDataForBounds(bounds, false);
        }
    }, 200);
});

map.on('click', function (e) {
    const lat = e.latlng.lat;
    const lng = e.latlng.lng;

    let closestPoint = null;
    let minDistance = Infinity;
    currentPoints.forEach(p => {
        const distance = Math.sqrt(Math.pow(p.lat - lat, 2) + Math.pow(p.lng - lng, 2));
        if (distance < minDistance) {
            minDistance = distance;
            closestPoint = p;
        }
    });

    if (closestPoint) {
        const [gcjLat, gcjLng] = wgs84ToGcj02(closestPoint.lat, closestPoint.lng);
        fetch(`/api/regeo?lng=${gcjLng}&lat=${gcjLat}`)
            .then(response => response.json())
            .then(data => {
                if (data.status === '1' && data.regeocode) {
                    const address = data.regeocode.formatted_address;
                    L.popup()
                        .setLatLng([closestPoint.lat, closestPoint.lng])
                        .setContent(`
                            <b>文件路径:</b> ${closestPoint.path}<br>
                            <b>拍摄时间:</b> ${closestPoint.timestamp}<br>
                            ${closestPoint.altitude ? `<b>海拔:</b> ${closestPoint.altitude}米<br>` : ''}
                            <b>地址:</b> ${address}
                        `)
                        .openOn(map);
                }
            })
            .catch(error => console.error('地址请求失败:', error));
    }
});

initHeatmap();
initTimeline();
initAnimation();
initSidebar();
initHoliday();

document.getElementById('displayModeSwitch').addEventListener('change', function (e) {
    showMode = e.target.checked ? 'heatmap' : 'trajectory';
    const labels = document.querySelectorAll('.mode-toggle .mode-label');
    labels[0].style.fontWeight = showMode === 'trajectory' ? 'bold' : 'normal';
    labels[1].style.fontWeight = showMode === 'heatmap' ? 'bold' : 'normal';
    renderTracks(currentPoints);
});
document.querySelectorAll('.mode-toggle .mode-label')[0].style.fontWeight = 'bold';

const initialBounds = map.getBounds();
loadDataForBounds(initialBounds, true);
