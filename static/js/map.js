let currentPoints = [];
let debounceTimeout = null;
let map;
let osmLayer = null;
let amapLayer = null;

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
osmLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);
amapLayer = L.tileLayer('https://webrd0{s}.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}', {
    subdomains: ['1', '2', '3', '4'],
    maxZoom: 18
});

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

    const range = getActiveTimeRange();
    let searchPoints = currentPoints;
    if (range) {
        const start = new Date(range.start);
        const end = new Date(range.end);
        searchPoints = currentPoints.filter(point => {
            const t = new Date(point.timestamp);
            return t >= start && t <= end;
        });
    }

    let closestPoint = null;
    let minDistance = Infinity;
    searchPoints.forEach(p => {
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
                            <b>拍摄时间:</b> ${toUTC8(closestPoint.timestamp)}<br>
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

const modeLabels = document.querySelectorAll('.mode-toggle .mode-label');
const modeSwitch = document.getElementById('displayModeSwitch');

function setDisplayMode(mode) {
    showMode = mode;
    modeSwitch.checked = (mode === 'heatmap');
    modeLabels.forEach(l => l.classList.toggle('active', l.dataset.mode === mode));
    document.getElementById('trajectory-card').style.display = mode === 'trajectory' ? 'block' : 'none';
    renderTracks(currentPoints);
}

modeLabels.forEach(label => {
    label.addEventListener('click', function () {
        setDisplayMode(this.dataset.mode);
    });
});

setDisplayMode('heatmap');

const tabOsm = document.querySelector('.map-source-tabs .speed-tab[for="mapOSM"]');
const tabAmap = document.querySelector('.map-source-tabs .speed-tab[for="mapAmap"]');

document.getElementById('mapOSM').addEventListener('change', function () {
    tabOsm.classList.add('active');
    tabAmap.classList.remove('active');
    map.removeLayer(amapLayer);
    map.addLayer(osmLayer);
});

document.getElementById('mapAmap').addEventListener('change', function () {
    tabAmap.classList.add('active');
    tabOsm.classList.remove('active');
    map.removeLayer(osmLayer);
    map.addLayer(amapLayer);
});

const sb = document.getElementById('sidebar');
const handle = document.getElementById('resizeHandle');
let resizing = false;
let startX, startWidth;

handle.addEventListener('mousedown', function (e) {
    resizing = true;
    startX = e.clientX;
    startWidth = sb.offsetWidth;
    handle.classList.add('active');
    document.body.style.userSelect = 'none';
    document.body.style.cursor = 'ew-resize';
    e.preventDefault();
});

document.addEventListener('mousemove', function (e) {
    if (!resizing) return;
    const delta = startX - e.clientX;
    const newWidth = startWidth + delta;
    sb.style.width = Math.min(520, Math.max(280, newWidth)) + 'px';
});

document.addEventListener('mouseup', function () {
    if (!resizing) return;
    resizing = false;
    handle.classList.remove('active');
    document.body.style.userSelect = '';
    document.body.style.cursor = '';
    map.invalidateSize();
});

const initialBounds = map.getBounds();
loadDataForBounds(initialBounds, true);
