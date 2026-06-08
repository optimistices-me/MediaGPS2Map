let trackLayers = [];
let showMode = 'trajectory';

function getColorForDate(dateStr) {
    const hash = dateStr.split('-').reduce((acc, cur) => acc + parseInt(cur), 0);
    return `hsl(${hash * 137 % 360}, 70%, 50%)`;
}

function clearTracks() {
    trackLayers.forEach(layer => map.removeLayer(layer));
    trackLayers = [];
}

function renderTracks(points) {
    clearTracks();

    if (showMode !== 'trajectory') return;

    const bounds = map.getBounds();

    const dailyGroups = (points || currentPoints).reduce((acc, point) => {
        if (bounds.contains([point.lat, point.lng])) {
            const date = point.timestamp.split('T')[0];
            if (!acc[date]) acc[date] = [];
            acc[date].push(point);
        }
        return acc;
    }, {});

    Object.entries(dailyGroups).forEach(([date, pts]) => {
        if (pts.length < 2) return;

        const sortedPoints = pts.sort((a, b) =>
            new Date(a.timestamp) - new Date(b.timestamp)
        );

        const polyline = L.polyline(
            sortedPoints.map(p => [p.lat, p.lng]),
            {
                color: getColorForDate(date),
                weight: 3,
                arrowheads: {
                    frequency: '50px',
                    size: '15px',
                    fill: true,
                    yawn: 60
                }
            }
        );

        polyline.addTo(map);
        trackLayers.push(polyline);
    });
}

function updateTracks() {
    renderTracks(currentPoints);
}
